"""
tabs/tab_ideias.py — Aba de Geração de Ideias de Carrossel.

Mudanças P0-2: ideias geradas são auto-selecionadas.
"""

import hashlib
import json

import streamlit as st

from config import CORES, EIXOS
from gemini import call_gemini_json, invalidate_cache
from parser_nlm import extract_ideas_from_text, is_guideline_noise
from persistence import (
    load_ideias_estado,
    load_metricas,
    save_geracao,
    update_idea_status,
)
from prompts import (
    TEMPERATURAS,
    get_prompt_ideias,
    validate_idea_diversity,
)
from tabs._ui import api_key_ok, esc, seletor_tom

_esc = esc  # alias used in card rendering
from datetime import datetime

from templates import TEMPLATES


def _ensure_idea_ids(ideias: list[dict], origem: str = "") -> list[dict]:
    """Garante IDs estáveis para ideias vindas do LLM ou do NotebookLM."""
    for idx, ideia in enumerate(ideias):
        if ideia.get("id"):
            continue
        identidade = json.dumps(
            {
                "titulo": ideia.get("titulo", ""),
                "tema": ideia.get("tema", ""),
                "eixo": ideia.get("eixo", ""),
                "slides": ideia.get("slides_sugeridos", []),
                "origem": origem,
                "indice": idx,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        digest = hashlib.sha256(identidade.encode("utf-8")).hexdigest()[:16]
        ideia["id"] = f"ideia_{digest}"
    return ideias


def _render_idea_card(idea: dict, idx: int) -> None:
    """Renderiza um card de ideia com badges estratégicos e ciclo de vida."""
    eixo = idea.get("eixo", "Didático")
    color = EIXOS.get(eixo, {}).get("cor", CORES["destaque"])
    persona = idea.get("persona_alvo", "")
    tipo_hook = idea.get("tipo_hook", "")
    score = idea.get("score")
    score_just = idea.get("score_justificativa", "")
    idea_id = idea.get("id", f"ideia_{idx}")

    estados = load_ideias_estado()
    estado = estados.get(idea_id, {})
    status = estado.get("status", "rascunho")

    badges_html = [
        f'<span style="background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.12); color:{color}; padding:3px 12px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.25); white-space:nowrap;">{esc(eixo)}</span>'
    ]
    if persona:
        badges_html.append(
            f'<span style="background:rgba(255,209,102,0.12); color:#FFD166; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(255,209,102,0.25); white-space:nowrap;">🎯 {esc(persona)}</span>'
        )
    if tipo_hook:
        badges_html.append(
            f'<span style="background:rgba(52,211,153,0.12); color:#34D399; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(52,211,153,0.25); white-space:nowrap;">⚡ {esc(tipo_hook)}</span>'
        )
    if score:
        badges_html.append(
            f'<span style="background:rgba(129,140,248,0.12); color:#818CF8; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(129,140,248,0.25); white-space:nowrap;">⭐ {esc(score)}/10 Retenção</span>'
        )

    status_colors = {
        "rascunho": CORES["texto_sec"],
        "aprovado": CORES["secundaria"],
        "agendado": CORES["destaque"],
        "publicado": CORES["primaria"],
    }
    status_color = status_colors.get(status, CORES["texto_sec"])
    status_emoji = {"rascunho": "📝", "aprovado": "✅", "agendado": "📅", "publicado": "🚀"}.get(status, "📄")
    badges_html.append(
        f'<span style="background:rgba(255,255,255,0.05); color:{status_color}; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(255,255,255,0.15); white-space:nowrap;">{status_emoji} {esc(status)}</span>'
    )

    badges_str = "".join(badges_html)

    score_html = ""
    if score_just:
        score_html = f'<div style="margin-top:10px; padding:6px 12px; background:rgba(255,255,255,0.03); border-left:2px solid {CORES["primaria"]}; font-size:0.78em; color:{CORES["texto_sec"]}; border-radius:0 4px 4px 0;"><strong>Estratégia de Retenção:</strong> {esc(score_just)}</div>'

    st.markdown(f"""
    <div class="idea-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
            <h3 style="margin:0; font-size:1.1rem; color:{CORES['primaria']};">{esc(idea.get('titulo','Sem título'))}</h3>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">{badges_str}</div>
        </div>
        <p style="color:{CORES['texto_sec']}; margin-bottom:10px; font-size:0.88em; line-height:1.5;">{esc(idea.get('tema',''))}</p>
        <div style="display:flex; flex-wrap:wrap; gap:20px;">
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">Público</div>
                <div style="color:{CORES['texto']}; font-size:0.88em;">{esc(idea.get('publico_alvo',''))}</div>
            </div>
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">KPI Alvo</div>
                <div style="color:{color}; font-weight:600; font-size:0.88em;">{esc(idea.get('kpi_alvo',''))}</div>
            </div>
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">CTA</div>
                <div style="color:{CORES['primaria']}; font-weight:600; font-size:0.88em;">
                    Comente "{esc(idea.get('cta',''))}"
                </div>
            </div>
        </div>
        {score_html}
    </div>
    """, unsafe_allow_html=True)

    # Ciclo de vida da ideia
    with st.container(border=True):
        st.caption("Ciclo de vida da publicação")
        if status == "rascunho":
            if st.button("✅ Aprovar ideia", key=f"status_aprovar_{idea_id}", width="stretch"):
                if update_idea_status(idea_id, "aprovado", titulo=idea.get("titulo", "")):
                    st.rerun()
        elif status == "aprovado":
            if st.button("📅 Marcar como agendada", key=f"status_agendar_{idea_id}", width="stretch"):
                if update_idea_status(idea_id, "agendado", titulo=idea.get("titulo", "")):
                    st.rerun()
        elif status == "agendado":
            try:
                data_default = datetime.fromisoformat(str(estado.get("data_publicacao", ""))).date()
            except ValueError:
                data_default = datetime.now().date()

            data_publicacao = st.date_input(
                "Data da publicação", value=data_default, key=f"status_data_{idea_id}",
            )

            legendas_ideia = []
            for item in st.session_state.get("legendas_lote", []):
                item_ideia = item.get("ideia", {})
                if item_ideia.get("id") == idea_id or item.get("titulo") == idea.get("titulo", ""):
                    legendas_ideia.extend(item.get("legendas", []))

            legenda_texto = None
            if legendas_ideia:
                opcoes_legenda = {
                    f"Opção {leg.get('opcao', idx + 1)}": leg.get("legenda_completa", "")
                    for idx, leg in enumerate(legendas_ideia)
                    if leg.get("legenda_completa")
                }
                if opcoes_legenda:
                    legenda_label = st.selectbox("Legenda usada", list(opcoes_legenda), key=f"status_legenda_{idea_id}")
                    legenda_texto = opcoes_legenda[legenda_label]

            with st.container(horizontal=True):
                if st.button("🚀 Registrar publicação", key=f"status_publicar_{idea_id}", type="primary", width="stretch"):
                    if update_idea_status(idea_id, "publicado", legenda_texto=legenda_texto, data_publicacao=str(data_publicacao), titulo=idea.get("titulo", "")):
                        st.rerun()
                if st.button("↩️ Reverter", key=f"status_reverter_agendado_{idea_id}", width="stretch"):
                    if update_idea_status(idea_id, "aprovado", titulo=idea.get("titulo", "")):
                        st.rerun()
        elif status == "publicado":
            data_publicada = estado.get("data_publicacao") or "data não registrada"
            st.caption(f"Publicado em {data_publicada}")
            if estado.get("legenda_texto"):
                st.caption("Legenda usada registrada no histórico.")
            if st.button("↩️ Reabrir como agendada", key=f"status_reverter_publicado_{idea_id}", width="stretch"):
                if update_idea_status(idea_id, "agendado", titulo=idea.get("titulo", "")):
                    st.rerun()

    slides = idea.get("slides_sugeridos", [])
    if slides:
        with st.expander(f"📄 Ver Roteiro ({len(slides)} slides)", expanded=False):
            for slide in slides:
                st.markdown(f"**Slide {slide.get('slide','?')} — {slide.get('tipo','')}**")
                st.markdown(f"_{slide.get('texto','')}_")
                st.divider()


def render():
    """Renderiza a aba de Ideias."""
    st.markdown("## 💡 Gerador de Ideias de Carrossel")
    tom = seletor_tom("tom_selecionado_ideias")

    # Templates pré-definidos
    st.markdown("### 📋 Templates Pré-definidos")
    tcols = st.columns(3)
    for i, (tkey, tval) in enumerate(TEMPLATES.items()):
        with tcols[i]:
            if st.button(f"{tval['icone']} {tval['nome']}", key=f"tpl_{tkey}", width="stretch"):
                st.session_state["template_selecionado"] = tkey
                st.session_state["template_info"] = tval

    if "template_info" in st.session_state:
        tpl = st.session_state["template_info"]
        st.info(f"**Template:** {tpl['nome']} — {tpl['descricao']}")
        c1, c2 = st.columns(2)
        with c1:
            custom_tema = st.text_input("Tema específico:", key="custom_tema")
        with c2:
            custom_cta = st.text_input("Palavra-chave CTA:", value=tpl["cta_padrao"], key="custom_cta")

        if st.button("🎲 Gerar com Template", type="primary", width="stretch"):
            if not api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ctx = f"Template: {tpl['nome']}\nEixo: {tpl['eixo']}\nTema: {custom_tema}\nCTA: {custom_cta}"
                with st.spinner("🤖 Gerando ideias com template…"):
                    dados = call_gemini_json(get_prompt_ideias(tom), ctx, temperature=TEMPERATURAS["ideias"])
                    if dados:
                        _ensure_idea_ids(dados.get("ideias", []), "template")
                        st.session_state["ideias"] = dados
                        save_geracao("ideias", dados)
                        # P0-2: auto-selecionar ideias geradas
                        st.session_state["ideias_selecionadas"] = dados.get("ideias", [])
                        st.success(f"✅ {len(dados.get('ideias', []))} ideias geradas e selecionadas!")
                        st.rerun()

    st.divider()

    # Usar ideias do NotebookLM diretamente
    if "nb_result" in st.session_state and st.session_state.get("nb_result"):
        st.markdown("### 📋 Usar Ideias do NotebookLM")
        st.info("💡 Você tem ideias prontas do NotebookLM. Use-as diretamente sem precisar gerar novas ideias.")

        if st.button("📤 Usar Ideias do NotebookLM", type="primary", width="stretch"):
            nb_result = st.session_state["nb_result"]
            ideias_formatadas = extract_ideas_from_text(nb_result)

            if not ideias_formatadas and api_key_ok() and len(nb_result.strip()) > 100:
                with st.spinner("🤖 Estruturando ideias do notebook com Gemini..."):
                    ctx = f"Estruture as seguintes notas e ideias vindas do NotebookLM em carrosséis completos de 8 slides para o Instagram da unidade:\n\n{nb_result}"
                    dados = call_gemini_json(get_prompt_ideias(tom), ctx, temperature=TEMPERATURAS["ideias"])
                    if dados and isinstance(dados, dict) and "ideias" in dados:
                        ideias_formatadas = [i for i in dados["ideias"] if not is_guideline_noise(i.get("titulo", ""))]

            ideias_validas = []
            for ideia in ideias_formatadas:
                tit = ideia.get("titulo", "")
                if is_guideline_noise(tit):
                    continue
                for campo, default in [
                    ("palavras_chave_seo", ["apoio escolar Tatuapé"]),
                    ("kpi_alvo", "Salvamentos/Envios/Leads"),
                    ("publico_alvo", "Pais de classes A/B do Tatuapé"),
                    ("slides_sugeridos", [{"slide": 1, "tipo": "Capa", "texto": tit}]),
                ]:
                    if not ideia.get(campo):
                        ideia[campo] = default
                ideias_validas.append(ideia)

            _ensure_idea_ids(ideias_validas, "notebooklm")

            if ideias_validas:
                st.session_state["ideias"] = {"ideias": ideias_validas}
                # P0-2: auto-selecionar
                st.session_state["ideias_selecionadas"] = ideias_validas
                save_geracao("ideias", {"ideias": ideias_validas})
                st.success(f"✅ {len(ideias_validas)} ideias do NotebookLM carregadas e selecionadas!")
                st.rerun()
            else:
                st.warning("⚠️ Não foi possível identificar ideias estruturadas no texto do notebook.")

        st.divider()

    # Semáforo do feedback loop
    _metricas_uteis = [
        m for m in load_metricas()
        if m.get("alcance", 0) > 0 and str(m.get("titulo", "")).strip()
    ]
    if _metricas_uteis:
        st.success(
            f"🟢 **Feedback loop ATIVO** — {len(_metricas_uteis)} post(s) com métricas reais "
            "alimentando a geração de ideias."
        )
    else:
        st.info(
            "🔴 **Feedback loop INATIVO** — nenhuma métrica útil registrada. "
            "Registre métricas na aba 📅 Cronograma & Métricas para que as novas ideias "
            "aprendam com o que performou melhor."
        )

    c1, c2 = st.columns([3, 1])
    with c1:
        foco = st.selectbox(
            "Filtrar por eixo:",
            ["Todos", "Didático (Salvamentos)", "Comportamental (Envios DM)", "Diagnóstico (Leads WhatsApp)"],
        )
    with c2:
        col_gerar, col_nova = st.columns(2)
        with col_gerar:
            gerar_ideias_btn = st.button("🎲 Gerar Ideias", type="primary", width="stretch")
        with col_nova:
            if st.button("🔄 Forçar novas", width="stretch", help="Ignora o cache e gera ideias novas"):
                invalidate_cache(get_prompt_ideias(tom))
                st.session_state.pop("ideias", None)
                st.rerun()

    if gerar_ideias_btn:
        if not api_key_ok():
            st.warning("⚠️ Configure a chave API Gemini.")
        else:
            invalidate_cache(get_prompt_ideias(tom))
            ctx = st.session_state.get("nb_contexto_para_ideias", "")
            if not ctx:
                ctx = st.session_state.get(
                    "tendencias_texto",
                    "Sem dados de tendências. Gere ideias gerais para Tatuapé, SP.",
                )
            with st.spinner("🤖 Gerando 6 ideias estratégicas de alta retenção…"):
                dados = call_gemini_json(get_prompt_ideias(tom), f"Tendências:\n{ctx}", temperature=TEMPERATURAS["ideias"])
                if dados:
                    _ensure_idea_ids(dados.get("ideias", []), "gemini")
                    st.session_state["ideias"] = dados
                    save_geracao("ideias", dados)
                    # P0-2: auto-selecionar todas as ideias geradas
                    st.session_state["ideias_selecionadas"] = dados.get("ideias", [])
                    st.success(f"✅ {len(dados.get('ideias', []))} ideias geradas e automaticamente selecionadas!")
                    st.rerun()

    if st.session_state.get("ideias"):
        dados_ideias = st.session_state["ideias"]
        ideias = dados_ideias.get("ideias", [])

        meta_analise = dados_ideias.get("meta_analise")
        if meta_analise:
            st.info(f"🧭 **Visão Geral Estratégica:** {meta_analise}")

        warnings_diversidade = validate_idea_diversity(ideias)
        if warnings_diversidade:
            with st.expander("⚠️ Alertas de Qualidade & Diversidade do Lote", expanded=False):
                for w in warnings_diversidade:
                    st.caption(w)

        eixo_map = {
            "Didático (Salvamentos)": "Didático",
            "Comportamental (Envios DM)": "Comportamental",
            "Diagnóstico (Leads WhatsApp)": "Diagnóstico",
        }
        if foco != "Todos":
            ideias = [i for i in ideias if i.get("eixo") == eixo_map.get(foco)]

        st.markdown(f"### {len(ideias)} ideia(s) encontrada(s)")
        for idx, idea in enumerate(ideias):
            _render_idea_card(idea, idx)

        st.divider()
        st.markdown("### ✅ Selecionar para Prompts e Cronograma")
        todas_ideias = st.session_state["ideias"].get("ideias", [])
        opcoes = {
            f"{i.get('eixo','?')} — {i.get('titulo','Sem título')}": i
            for i in todas_ideias
        }
        # P0-2: multiselect já vem pré-preenchido com as ideias auto-selecionadas
        selecionadas_atuais = st.session_state.get("ideias_selecionadas", [])
        opcoes_previas = [
            f"{i.get('eixo','?')} — {i.get('titulo','Sem título')}"
            for i in selecionadas_atuais
            if f"{i.get('eixo','?')} — {i.get('titulo','Sem título')}" in opcoes
        ]
        selecionadas = st.multiselect(
            "Escolha as ideias:",
            options=list(opcoes.keys()),
            default=opcoes_previas,
            key="selecao_ideias",
        )
        if selecionadas:
            st.session_state["ideias_selecionadas"] = [opcoes[s] for s in selecionadas]
            st.success(f"✅ {len(selecionadas)} ideia(s) selecionada(s). Continue nas abas ao lado.")
