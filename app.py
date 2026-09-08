"""
Motor de Carrosséis — Ensina Mais Tatuapé
Gerador inteligente de carrosséis para Instagram com análise de tendências,
ideias estratégicas, prompts para Google Flow, geração de imagens e cronograma.
"""

# ─── Imports (todos no topo) ──────────────────────────────────────────────────
import json
import zipfile
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import CORES, EIXOS, FORMATO, KPIS, UNIDADE
from gemini import call_gemini, extract_json, invalidate_cache
from image_utils import add_text_overlay, create_slide_from_template, generate_all_slides
from persistence import (
    save_geracao,
    save_metrica,
    sync_session_from_disk,
)
from prompts import (
    PROMPT_IDEIAS,
    PROMPT_LEGENDAS,
    PROMPT_PROMPTS_IMAGEM,
    PROMPT_TENDENCIAS,
    get_prompt_cronograma,
)
from templates import TEMPLATES, MetricaPost, eixo_para_template
import notebooklm_client as nlm

# ─── Configuração da página ───────────────────────────────────────────────────
st.set_page_config(
    page_title="Motor de Carrosséis — Ensina Mais Tatuapé",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Startup: sincronizar disco → session_state (uma vez por sessão) ──────────
if "_synced" not in st.session_state:
    sync_session_from_disk(st.session_state)
    st.session_state["_synced"] = True

# ─── CSS customizado ──────────────────────────────────────────────────────────
st.markdown(f"""
<style>
    .stApp {{ background-color: {CORES['app_bg']}; }}
    .main .block-container {{ padding-top: 2rem; max-width: 1200px; }}
    h1, h2, h3 {{ color: #f0f0f0 !important; }}
    .stTabs [data-baseweb="tab-list"] {{ gap: 8px; }}
    .stTabs [data-baseweb="tab"] {{
        background-color: {CORES['app_card']};
        color: {CORES['app_texto_muted']};
        border-radius: 8px 8px 0 0;
        padding: 10px 24px;
        font-weight: 600;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {CORES['perigo']} !important;
        color: white !important;
    }}
    .idea-card {{
        background: linear-gradient(135deg, {CORES['app_card']} 0%, {CORES['app_card2']} 100%);
        border: 1px solid {CORES['app_borda']};
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }}
    .idea-card h3 {{ color: {CORES['perigo']} !important; margin-top: 0; }}
    .metric-box {{
        background: {CORES['app_card']};
        border-left: 4px solid {CORES['perigo']};
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 8px;
    }}
    .prompt-box {{
        background: {CORES['app_card']};
        border: 1px solid #444;
        border-radius: 8px;
        padding: 16px;
        font-family: 'Courier New', monospace;
        font-size: 0.9em;
        color: #ccc;
        white-space: pre-wrap;
    }}
    .schedule-day {{
        background: {CORES['app_card2']};
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
    }}
    div[data-testid="stExpander"] {{
        background-color: {CORES['app_card']};
        border-radius: 8px;
    }}
    .timeline-item {{
        background: {CORES['app_card']};
        border-left: 4px solid {CORES['perigo']};
        padding: 12px 16px;
        margin-bottom: 8px;
        border-radius: 0 8px 8px 0;
    }}
    .timeline-item.carrossel {{ border-left-color: {CORES['secundaria']}; }}
    .timeline-item.stories   {{ border-left-color: {CORES['destaque']}; }}
    .timeline-item.reel      {{ border-left-color: {CORES['perigo']}; }}
    /* Barra de progresso do fluxo */
    .flow-step {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 14px;
        border-radius: 20px;
        font-size: 0.85em;
        font-weight: 600;
        margin: 2px;
    }}
    .flow-step.done    {{ background: {CORES['secundaria']}22; color: {CORES['secundaria']}; border: 1px solid {CORES['secundaria']}; }}
    .flow-step.current {{ background: {CORES['destaque']}22; color: {CORES['destaque']}; border: 1px solid {CORES['destaque']}; }}
    .flow-step.pending {{ background: #2a2a2a; color: #666; border: 1px solid #444; }}
</style>
""", unsafe_allow_html=True)


# ─── Helpers de UI ────────────────────────────────────────────────────────────

def _api_key_ok() -> bool:
    """Verifica se há chave configurada sem expor o valor."""
    from gemini import _get_api_key  # noqa: PLC0415
    return bool(_get_api_key())


def clipboard_button(text: str, label: str, key: str) -> None:
    """
    Botão que exibe o texto para copiar manualmente.
    """
    if st.button(label, key=key, use_container_width=True):
        st.code(text, language=None)
        st.success("Copie o texto acima!")


def flow_progress() -> None:
    """
    Exibe barra de progresso do fluxo de trabalho no topo do app,
    indicando quais etapas já foram concluídas.
    """
    etapas = [
        ("tendencias",          "📈 Tendências"),
        ("ideias",              "💡 Ideias"),
        ("ideias_selecionadas", "✅ Seleção"),
        ("prompts",             "🎨 Prompts"),
        ("legendas",            "📝 Legendas"),
        ("cronograma",          "📅 Cronograma"),
    ]
    html_parts = []
    for key, label in etapas:
        exists = bool(st.session_state.get(key))
        css = "done" if exists else "pending"
        icon = "✓" if exists else "○"
        html_parts.append(
            f'<span class="flow-step {css}">{icon} {label}</span>'
        )
    st.markdown(
        '<div style="margin-bottom:16px;">' + "".join(html_parts) + "</div>",
        unsafe_allow_html=True,
    )


def render_idea_card(idea: dict, idx: int) -> None:
    """Renderiza um card de ideia com expander de roteiro."""
    eixo = idea.get("eixo", "Didático")
    color = EIXOS.get(eixo, {}).get("cor", CORES["secundaria"])

    st.markdown(f"""
    <div class="idea-card">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
            <h3 style="margin:0; font-size:1.2em;">{idea.get('titulo','Sem título')}</h3>
            <span style="background:{color}; color:white; padding:4px 12px;
                  border-radius:20px; font-size:0.8em; font-weight:600;">{eixo}</span>
        </div>
        <p style="color:#a0a0a0; margin-bottom:8px;">{idea.get('tema','')}</p>
        <div style="margin-bottom:8px;">
            <strong style="color:#888;">Público:</strong>
            <span style="color:#ccc;"> {idea.get('publico_alvo','')}</span>
        </div>
        <div style="margin-bottom:8px;">
            <strong style="color:#888;">KPI Alvo:</strong>
            <span style="color:{color}; font-weight:600;"> {idea.get('kpi_alvo','')}</span>
        </div>
        <div style="margin-bottom:8px;">
            <strong style="color:#888;">CTA:</strong>
            <span style="color:{CORES['destaque']}; font-weight:600;">
                Comente "{idea.get('cta','')}"
            </span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    slides = idea.get("slides_sugeridos", [])
    if slides:
        with st.expander(f"📄 Ver Roteiro ({len(slides)} slides)", expanded=False):
            for slide in slides:
                st.markdown(f"**Slide {slide.get('slide','?')} — {slide.get('tipo','')}**")
                st.markdown(f"_{slide.get('texto','')}_")
                st.divider()


def render_schedule_day(day: dict) -> None:
    """Renderiza um item de cronograma."""
    canal_icons = {
        "Stories": "📱", "Feed": "📸", "Reels": "🎬", "Feed (Carrossel)": "🎠",
    }
    canal = day.get("canal", "")
    icon = canal_icons.get(canal, "📱")
    tipo = day.get("tipo", "")

    if "Carrossel" in tipo or "Feed" in canal:
        css_class = "carrossel"
    elif "Stories" in canal:
        css_class = "stories"
    elif "Reel" in tipo:
        css_class = "reel"
    else:
        css_class = ""

    st.markdown(f"""
    <div class="timeline-item {css_class}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <strong style="color:{CORES['perigo']};">
                    {icon} {day.get('dia','')} — {day.get('data','')}
                </strong>
                <span style="color:#888; margin-left:8px;">{day.get('horario','')}</span>
            </div>
            <span style="background:{CORES['app_card']}; color:{CORES['secundaria']};
                  padding:2px 10px; border-radius:12px; font-size:0.8em;">{canal}</span>
        </div>
        <p style="color:#ccc; margin:8px 0 4px 0; font-size:0.95em;">
            {day.get('conteudo_resumo','')}
        </p>
        <p style="color:#888; margin:0; font-size:0.85em;">
            📌 CTA: {day.get('cta','—')}
        </p>
    </div>
    """, unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configurações")

    api_key_input = st.text_input(
        "🔑 Chave API Gemini",
        value=st.session_state.get("gemini_key", "CHAVE_GEMINI_REMOVIDA"),
        type="password",
        help="Obtida em aistudio.google.com — não é salva em disco.",
        placeholder="Cole sua chave aqui…",
    )
    if api_key_input:
        st.session_state["gemini_key"] = api_key_input

    if _api_key_ok():
        st.success("✅ API configurada")
    else:
        st.warning("⚠️ Chave não configurada")
        st.caption("Defina GEMINI_API_KEY no ambiente ou cole acima.")

    st.divider()
    st.markdown("## 📊 Info da Unidade")
    st.markdown(f"""
    - **Unidade:** {UNIDADE['nome']}
    - **Endereço:** {UNIDADE['endereco']}
    - **WhatsApp:** {UNIDADE['whatsapp']}
    - **Colégios:** {', '.join(UNIDADE['colégios_vizinhos'])}
    - **Público:** {UNIDADE['publico']}
    """)

    st.divider()
    st.markdown("## 🎯 KPIs Alvo")
    st.markdown(f"""
    - 💾 Salvamentos: ≥ {KPIS['salvamentos_pct']}%
    - 📤 Envios DM: ≥ {KPIS['envios_dm_pct']}%
    - 🆕 Não seguidores: ≥ {KPIS['nao_seguidores_pct']}%
    - 📱 Leads/semana: {KPIS['leads_semana_min']}–{KPIS['leads_semana_max']}
    """)

    st.divider()
    st.markdown("## 📐 Formato")
    st.markdown(f"""
    - {FORMATO['largura']}×{FORMATO['altura']}px ({FORMATO['proporcao']})
    - {FORMATO['slides_min']}–{FORMATO['slides_max']} lâminas
    - {FORMATO['palavras_por_slide_min']}–{FORMATO['palavras_por_slide_max']} palavras/slide
    - Máx {FORMATO['max_carrosseis_semana']} carrosséis/semana
    """)


# ─── Título + barra de progresso do fluxo ────────────────────────────────────
st.markdown(f"""
# 🎯 Motor de Carrosséis
### {UNIDADE['nome']} — Instagram Strategy Engine
""")
flow_progress()

# ─── Tabs principais ──────────────────────────────────────────────────────────
tab1, tab2, tab8, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📈 Tendências",
    "💡 Ideias",
    "🔬 NotebookLM",
    "🎨 Prompts Google Flow",
    "🖼️ Gerador de Imagens",
    "📝 Legendas",
    "📅 Cronograma & Métricas",
    "📦 Lote",
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ANÁLISE DE TENDÊNCIAS
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("## 📈 Análise de Tendências do Setor")
    st.markdown("Pesquisa automatizada sobre o que está funcionando no Instagram educacional.")

    col_btn, col_inv = st.columns([1, 1])
    with col_btn:
        gerar_tend = st.button("🔍 Analisar Tendências", type="primary", use_container_width=True)
    with col_inv:
        if st.button("🔄 Forçar nova análise", use_container_width=True,
                     help="Ignora o cache e gera uma análise nova"):
            invalidate_cache(PROMPT_TENDENCIAS)
            st.session_state.pop("tendencias", None)
            st.rerun()

    if gerar_tend:
        if not _api_key_ok():
            st.warning("⚠️ Configure a chave API Gemini na barra lateral.")
        else:
            with st.spinner("🤖 Pesquisando tendências…"):
                raw = call_gemini(PROMPT_TENDENCIAS)
                if raw:
                    data = extract_json(raw)
                    st.session_state["tendencias"] = data
                    st.session_state["tendencias_texto"] = json.dumps(data, ensure_ascii=False)
                    save_geracao("tendencias", data)
                    st.success("✅ Tendências analisadas e salvas!")

    if st.session_state.get("tendencias"):
        data = st.session_state["tendencias"]

        st.markdown("### 🎬 Tendências de Conteúdo no Instagram")
        for t in data.get("tendencias_conteudo", []):
            pot = t.get("potencial_engajamento", "")
            cor = CORES["secundaria"] if pot == "alto" else CORES["destaque"] if pot == "médio" else "#888"
            st.markdown(f"""
            <div class="metric-box">
                <strong style="color:{cor};">{t.get('nome','')}</strong>
                <span style="color:#888; font-size:0.85em; margin-left:8px;">[{pot}]</span>
                <br><span style="color:#ccc; font-size:0.9em;">{t.get('descricao','')}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### 😰 Dores dos Pais no Tatuapé")
        for d in data.get("dores_pais", []):
            with st.expander(f"💔 {d.get('dor','')}"):
                st.markdown(f"**Frequência:** {d.get('frequencia','')}")
                st.markdown(f"**Como abordar:** {d.get('como_abordar','')}")

        st.markdown("### 📅 Sazonalidade Escolar")
        for s in data.get("sazonalidade", []):
            st.info(f"**{s.get('evento','')}** ({s.get('periodo','')}) → {s.get('oportunidade','')}")

        st.markdown("### 🧠 Tendências de Comportamento")
        for t in data.get("tendencias_comportamento", []):
            st.markdown(f"""
            <div class="metric-box">
                <strong style="color:{CORES['perigo']};">{t.get('tendencia','')}</strong>
                <br><span style="color:#ccc; font-size:0.9em;">{t.get('aplicacao','')}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### 🏆 Oportunidades vs. Concorrência")
        for o in data.get("oportunidades_concorrencia", []):
            st.success(
                f"**{o.get('oportunidade','')}** → "
                f"Diferencial local: {o.get('diferencial_local','')}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — IDEIAS DE CARROSSEL
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("## 💡 Gerador de Ideias de Carrossel")

    # ── Templates pré-definidos ──────────────────────────────────────────────
    st.markdown("### 📋 Templates Pré-definidos")
    tcols = st.columns(3)
    for i, (tkey, tval) in enumerate(TEMPLATES.items()):
        with tcols[i]:
            if st.button(
                f"{tval['icone']} {tval['nome']}", key=f"tpl_{tkey}", use_container_width=True
            ):
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

        if st.button("🎲 Gerar com Template", type="primary", use_container_width=True):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ctx = f"Template: {tpl['nome']}\nEixo: {tpl['eixo']}\nTema: {custom_tema}\nCTA: {custom_cta}"
                with st.spinner("🤖 Gerando ideias com template…"):
                    raw = call_gemini(PROMPT_IDEIAS, ctx)
                    if raw:
                        dados = extract_json(raw)
                        st.session_state["ideias"] = dados
                        save_geracao("ideias", dados)
                        st.success("✅ Ideias geradas!")

    st.divider()

    # ── Geração livre ────────────────────────────────────────────────────────
    c1, c2 = st.columns([3, 1])
    with c1:
        foco = st.selectbox(
            "Filtrar por eixo:",
            ["Todos", "Didático (Salvamentos)", "Comportamental (Envios DM)", "Diagnóstico (Leads WhatsApp)"],
        )
    with c2:
        if st.button("🎲 Gerar Ideias", type="primary", use_container_width=True):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                # Verificar se há contexto do NotebookLM
                ctx = st.session_state.get("nb_contexto_para_ideias", "")
                if not ctx:
                    ctx = st.session_state.get(
                        "tendencias_texto",
                        "Sem dados de tendências. Gere ideias gerais para Tatuapé, SP.",
                    )
                with st.spinner("🤖 Gerando 6 ideias estratégicas…"):
                    raw = call_gemini(PROMPT_IDEIAS, f"Tendências:\n{ctx}")
                    if raw:
                        dados = extract_json(raw)
                        st.session_state["ideias"] = dados
                        save_geracao("ideias", dados)
                        st.success("✅ 6 ideias geradas!")

    if st.session_state.get("ideias"):
        ideias = st.session_state["ideias"].get("ideias", [])

        # Aplicar filtro
        eixo_map = {
            "Didático (Salvamentos)": "Didático",
            "Comportamental (Envios DM)": "Comportamental",
            "Diagnóstico (Leads WhatsApp)": "Diagnóstico",
        }
        if foco != "Todos":
            ideias = [i for i in ideias if i.get("eixo") == eixo_map.get(foco)]

        st.markdown(f"### {len(ideias)} ideia(s) encontrada(s)")
        for idx, idea in enumerate(ideias):
            render_idea_card(idea, idx)

        st.divider()
        st.markdown("### ✅ Selecionar para Prompts e Cronograma")
        todas_ideias = st.session_state["ideias"].get("ideias", [])
        opcoes = {
            f"{i.get('eixo','?')} — {i.get('titulo','Sem título')}": i
            for i in todas_ideias
        }
        selecionadas = st.multiselect(
            "Escolha as ideias:",
            options=list(opcoes.keys()),
            key="selecao_ideias",
        )
        if selecionadas:
            st.session_state["ideias_selecionadas"] = [opcoes[s] for s in selecionadas]
            st.success(f"✅ {len(selecionadas)} ideia(s) selecionada(s). Continue nas abas ao lado.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — PROMPTS GOOGLE FLOW
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("## 🎨 Prompts para Google Flow (ImageFX)")
    st.markdown("Gera prompts em inglês para criar cada slide com IA generativa.")

    if not st.session_state.get("ideias_selecionadas"):
        st.info("📌 Selecione ideias na aba **Ideias** primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opcoes_p = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
        escolha = st.selectbox("Ideia para gerar prompts:", list(opcoes_p.keys()), key="sel_prompt")

        if st.button("🎨 Gerar Prompts", type="primary", use_container_width=True):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ideia = opcoes_p[escolha]
                ctx = (
                    f"Carrossel:\n{json.dumps(ideia, ensure_ascii=False)}\n\n"
                    f"Slides:\n{json.dumps(ideia.get('slides_sugeridos',[]), ensure_ascii=False)}"
                )
                with st.spinner("🤖 Gerando prompts de imagem…"):
                    raw = call_gemini(PROMPT_PROMPTS_IMAGEM, ctx)
                    if raw:
                        dados = extract_json(raw)
                        st.session_state["prompts"] = dados
                        save_geracao("prompts", dados)
                        st.success("✅ Prompts gerados!")

        if st.session_state.get("prompts"):
            prompts = st.session_state["prompts"]

            # Paleta de cores
            paleta = prompts.get("paleta_cores", {})
            if paleta:
                st.markdown("### 🎨 Paleta")
                pcols = st.columns(len(paleta))
                for i, (nome, cor) in enumerate(paleta.items()):
                    with pcols[i]:
                        st.markdown(f"""
                        <div style="text-align:center;">
                            <div style="width:60px;height:60px;background:{cor};
                                 border-radius:8px;margin:0 auto 4px;"></div>
                            <span style="color:#888;font-size:0.8em;">{nome}<br>{cor}</span>
                        </div>
                        """, unsafe_allow_html=True)

            # Prompts por slide
            st.markdown("### 📸 Prompts por Slide")
            ref_labels = {
                "logo":             "🏷️ Logo Ensina Mais Turma da Mônica",
                "fachada":          "🏢 Foto da Fachada (Rua Coelho Lisboa, 783)",
                "alunos_robótica":  "🤖 Foto: Aluna montando robô",
                "alunos_programação": "💻 Foto: Aluno programando",
                "alunos_apoio":     "📚 Foto: Alunos em aula de reforço",
                "lab_tecnologia":   "🔬 Foto: Laboratório de Tecnologia",
            }

            for slide in prompts.get("slides", []):
                snum = slide.get("slide_num", "?")
                with st.expander(f"Slide {snum} — {slide.get('estilo','')}", expanded=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**🇺🇸 Prompt (English):**")
                        st.code(slide.get("prompt_en", ""), language=None)
                        clipboard_button(
                            slide.get("prompt_en", ""),
                            f"📋 Copiar prompt Slide {snum}",
                            key=f"clip_prompt_{snum}",
                        )
                    with c2:
                        st.markdown("**🇧🇷 Descrição (Português):**")
                        st.markdown(slide.get("prompt_pt", ""))
                        st.markdown(f"**📝 Texto sobreposto:** `{slide.get('text_overlay','')}`")

                    refs = slide.get("referencias", [])
                    if refs:
                        refs_text = " | ".join(ref_labels.get(r, r) for r in refs)
                        st.markdown(f"**📎 Referências:** {refs_text}")

            # Dicas gerais
            if prompts.get("dicas_gerais"):
                st.markdown("### 💡 Dicas Gerais")
                st.info(prompts["dicas_gerais"])

            # Exportações
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ Exportar JSON",
                    data=json.dumps(prompts, ensure_ascii=False, indent=2),
                    file_name="prompts_carrossel.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with c2:
                txt_content = "\n\n".join(
                    s.get("prompt_en", "")
                    for s in prompts.get("slides", [])
                    if s.get("prompt_en")
                )
                st.download_button(
                    "⬇️ Exportar .txt (automação)",
                    data=txt_content,
                    file_name="prompts_automaticacao.txt",
                    mime="text/plain",
                    use_container_width=True,
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — GERADOR DE IMAGENS
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("## 🖼️ Gerador de Imagens com Texto Sobreposto")

    # Modo 1: Upload
    st.markdown("### 📤 Modo 1 — Upload de Imagem")
    uploaded = st.file_uploader("Imagem (JPG, PNG)", type=["jpg", "jpeg", "png"], key="upload_img")
    if uploaded:
        img_bytes = uploaded.read()
        st.image(img_bytes, caption="Original", use_container_width=True)
        c1, c2, c3 = st.columns(3)
        with c1:
            overlay_text = st.text_input("Texto sobreposto (PT-BR, ≤15 palavras):")
        with c2:
            font_sz = st.slider("Tamanho da fonte:", 24, 72, 48)
        with c3:
            pos = st.selectbox("Posição:", ["center", "bottom", "top"])

        if st.button("🖼️ Adicionar Texto", type="primary", use_container_width=True):
            if overlay_text:
                with st.spinner("Processando…"):
                    result_bytes = add_text_overlay(img_bytes, overlay_text, font_size=font_sz, position=pos)
                    st.image(result_bytes, caption="Com texto sobreposto")
                    st.download_button(
                        "⬇️ Download Slide",
                        data=result_bytes,
                        file_name="slide_com_texto.png",
                        mime="image/png",
                    )
            else:
                st.warning("⚠️ Digite o texto sobreposto.")

    st.divider()

    # Modo 2: Template único
    st.markdown("### 📋 Modo 2 — Gerar com Template")
    tpl_opts = {f"{t['icone']} {t['nome']}": k for k, t in TEMPLATES.items()}
    tpl_choice = st.selectbox("Template:", list(tpl_opts.keys()), key="tpl_img")
    tpl_key = tpl_opts[tpl_choice]
    tpl_data = TEMPLATES[tpl_key]

    slide_num = st.number_input("Número do slide:", min_value=1, max_value=9, value=1)
    estrutura = tpl_data["estrutura"]
    default_text = estrutura[min(slide_num - 1, len(estrutura) - 1)].texto
    slide_text = st.text_area("Texto do slide:", value=default_text)

    if st.button("🖼️ Gerar Slide", type="primary", use_container_width=True):
        with st.spinner("Gerando slide…"):
            sb = create_slide_from_template(tpl_key, int(slide_num), slide_text)
            st.image(sb, caption=f"Slide {slide_num} — {tpl_data['nome']}")
            st.download_button("⬇️ Download", data=sb,
                               file_name=f"slide_{slide_num}_{tpl_key}.png",
                               mime="image/png")

    st.divider()

    # Modo 3: Todos os slides de um carrossel
    st.markdown("### 🎠 Modo 3 — Gerar Carrossel Completo")
    if not st.session_state.get("ideias_selecionadas"):
        st.info("📌 Selecione ideias na aba **Ideias** primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opts_c = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
        escolha_c = st.selectbox("Carrossel:", list(opts_c.keys()), key="carrossel_img")

        if st.button("🎠 Gerar Todos os Slides", type="primary", use_container_width=True):
            ideia = opts_c[escolha_c]
            slides_list = ideia.get("slides_sugeridos", [])
            tkey = eixo_para_template(ideia.get("eixo", "Didático"))

            with st.spinner(f"Gerando {len(slides_list)} slides…"):
                progress = st.progress(0)
                all_slides: list[tuple[int, bytes]] = []
                for i, slide in enumerate(slides_list):
                    sb = create_slide_from_template(tkey, slide.get("slide", i + 1), slide.get("texto", ""))
                    all_slides.append((slide.get("slide", i + 1), sb))
                    progress.progress((i + 1) / len(slides_list))

                st.success(f"✅ {len(all_slides)} slides gerados!")
                for sn, sb in all_slides:
                    st.image(sb, caption=f"Slide {sn}")

                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for sn, sb in all_slides:
                        zf.writestr(f"slide_{sn}.png", sb)
                st.download_button(
                    "⬇️ Download ZIP",
                    data=zip_buf.getvalue(),
                    file_name=f"carrossel_{ideia.get('titulo','')[:30].replace(' ','_')}.zip",
                    mime="application/zip",
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — LEGENDAS
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("## 📝 Gerador de Legendas")
    st.markdown("Gera 3 opções de legenda conectadas ao tema do carrossel selecionado.")

    if not st.session_state.get("ideias_selecionadas"):
        st.info("📌 Selecione ideias na aba **Ideias** primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opts_l = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
        escolha_l = st.selectbox("Carrossel:", list(opts_l.keys()), key="sel_legenda")

        if st.button("📝 Gerar Legendas", type="primary", use_container_width=True):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ideia = opts_l[escolha_l]
                ctx = f"Carrossel:\n{json.dumps(ideia, ensure_ascii=False)}"
                with st.spinner("🤖 Gerando 3 opções de legenda…"):
                    raw = call_gemini(PROMPT_LEGENDAS, ctx)
                    if raw:
                        dados = extract_json(raw)
                        st.session_state["legendas"] = dados
                        save_geracao("legendas", dados)
                        st.success("✅ 3 legendas geradas!")

        if st.session_state.get("legendas"):
            legendas_data = st.session_state["legendas"]
            opcao_icons = {1: "🔴", 2: "🟡", 3: "🟢"}

            for leg in legendas_data.get("legendas", []):
                op = leg.get("opcao", 1)
                estilo = leg.get("estilo", "")
                legenda_completa = leg.get("legenda_completa", "")
                char_count = leg.get("char_count", 0)

                with st.expander(
                    f"{opcao_icons.get(op,'•')} Opção {op} — {estilo}",
                    expanded=(op == 1),
                ):
                    st.markdown(f"**🎣 Gancho:** {leg.get('gancho','')}")
                    st.markdown(f"**📖 Corpo:** {leg.get('corpo','')}")
                    st.markdown(f"**📢 CTA:** {leg.get('cta','')}")
                    st.markdown(f"**# Hashtags:** {leg.get('hashtags','')}")
                    st.divider()
                    st.markdown("**📋 Legenda completa:**")
                    st.code(legenda_completa, language=None)

                    # Contagem de caracteres
                    if char_count > 2200:
                        st.error(f"⚠️ {char_count} chars — acima do limite do Instagram (2.200)")
                    elif char_count > 1800:
                        st.warning(f"⏳ {char_count} chars — próximo do limite")
                    else:
                        st.success(f"✅ {char_count} chars — dentro do ideal")

                    clipboard_button(
                        legenda_completa,
                        f"📋 Copiar Legenda Opção {op}",
                        key=f"clip_leg_{op}",
                    )

            if legendas_data.get("dicas_uso"):
                st.divider()
                st.markdown("### 💡 Dicas de Uso")
                st.info(legendas_data["dicas_uso"])

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ Exportar JSON",
                    data=json.dumps(legendas_data, ensure_ascii=False, indent=2),
                    file_name="legendas_carrossel.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with c2:
                txt_legs = "\n\n---\n\n".join(
                    f"OPÇÃO {l.get('opcao','?')} — {l.get('estilo','')}\n\n{l.get('legenda_completa','')}"
                    for l in legendas_data.get("legendas", [])
                )
                st.download_button(
                    "⬇️ Exportar .txt",
                    data=txt_legs,
                    file_name="legendas_carrossel.txt",
                    mime="text/plain",
                    use_container_width=True,
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6 — CRONOGRAMA & MÉTRICAS
# ═══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("## 📅 Cronograma de Postagens & Acompanhamento")

    # ── Cronograma ───────────────────────────────────────────────────────────
    if not st.session_state.get("ideias_selecionadas"):
        st.info("📌 Selecione ideias na aba **Ideias** primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        st.markdown(f"**{len(ideias_sel)} ideia(s) selecionada(s).**")

        if st.button("📅 Gerar Cronograma", type="primary", use_container_width=True):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ctx = f"Ideias selecionadas:\n{json.dumps(ideias_sel, ensure_ascii=False)}"
                with st.spinner("🤖 Montando cronograma com datas reais…"):
                    # get_prompt_cronograma() injeta a data atual
                    raw = call_gemini(get_prompt_cronograma(), ctx)
                    if raw:
                        dados = extract_json(raw)
                        st.session_state["cronograma"] = dados
                        save_geracao("cronograma", dados)
                        st.success("✅ Cronograma gerado!")

    if st.session_state.get("cronograma"):
        cron = st.session_state["cronograma"]

        st.markdown("### 📆 Calendário Visual")
        all_days = (
            [dict(d, semana=1) for d in cron.get("semana_1", [])]
            + [dict(d, semana=2) for d in cron.get("semana_2", [])]
        )
        for day in all_days:
            render_schedule_day(day)

        # KPIs
        kpis = cron.get("kpis_semanais", {})
        if kpis:
            st.markdown("### 🎯 Metas Semanais")
            k1, k2, k3, k4 = st.columns(4)
            items = [
                (k1, "💾 Salvamentos", kpis.get("meta_salvamentos", "≥4%"),    CORES["secundaria"]),
                (k2, "📤 Envios DM",   kpis.get("meta_envios",       "≥2,5%"), CORES["destaque"]),
                (k3, "🆕 Não Seguid.", kpis.get("meta_nao_seguidores","≥20%"), CORES["perigo"]),
                (k4, "📱 Leads",       kpis.get("meta_leads",        "15-25"), "#A8DADC"),
            ]
            for col, label, valor, cor in items:
                with col:
                    st.markdown(f"""
                    <div class="metric-box">
                        <strong style="color:{cor};">{label}</strong><br>
                        <span style="color:white;font-size:1.3em;font-weight:700;">{valor}</span>
                    </div>
                    """, unsafe_allow_html=True)

        dicas = cron.get("dicas_monitoramento", [])
        if dicas:
            st.markdown("### 📊 Dicas de Monitoramento")
            for d in dicas:
                st.markdown(f"- {d}")

        st.download_button(
            "⬇️ Exportar Cronograma (JSON)",
            data=json.dumps(cron, ensure_ascii=False, indent=2),
            file_name="cronograma_carrosseis.json",
            mime="application/json",
        )

    # ── Registro de Métricas ─────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📊 Registrar Métricas de Post")
    st.caption("Preencha após 72h da publicação para acompanhar os KPIs.")

    with st.form("form_metricas"):
        c1, c2 = st.columns(2)
        with c1:
            post_titulo  = st.text_input("Título do post")
            alcance      = st.number_input("Alcance Total",        min_value=0, value=0)
            salvamentos  = st.number_input("Salvamentos",          min_value=0, value=0)
            envios_dm    = st.number_input("Envios via DM",        min_value=0, value=0)
        with c2:
            nao_seg      = st.number_input("Alcance Não Seguidores", min_value=0, value=0)
            comentarios  = st.number_input("Comentários",           min_value=0, value=0)
            leads_wpp    = st.number_input("Leads WhatsApp",         min_value=0, value=0)
            data_post    = st.date_input("Data da publicação")

        submitted = st.form_submit_button("💾 Salvar Métricas", use_container_width=True)

        if submitted and alcance > 0:
            m = MetricaPost(
                data=str(data_post),
                titulo=post_titulo,
                alcance=alcance,
                salvamentos=salvamentos,
                envios_dm=envios_dm,
                nao_seguidores=nao_seg,
                comentarios=comentarios,
                leads_whatsapp=leads_wpp,
            )
            m.calcular_taxas()
            m_dict = m.to_dict()

            # Salvar em disco e session_state
            save_metrica(m_dict)
            hist = st.session_state.get("historico_metricas", [])
            hist.append(m_dict)
            st.session_state["historico_metricas"] = hist

            # Resultado visual
            st.markdown("#### 📈 Resultado")
            r1, r2, r3, r4 = st.columns(4)
            with r1:
                ok = m.taxa_salvamentos >= KPIS["salvamentos_pct"]
                st.metric("💾 Salvamentos", f"{m.taxa_salvamentos:.1f}%",
                          delta="✅ Meta" if ok else "❌ Abaixo")
            with r2:
                ok = m.taxa_envios >= KPIS["envios_dm_pct"]
                st.metric("📤 Envios DM", f"{m.taxa_envios:.1f}%",
                          delta="✅ Meta" if ok else "❌ Abaixo")
            with r3:
                ok = m.taxa_nao_seguidores >= KPIS["nao_seguidores_pct"]
                st.metric("🆕 Não Seguid.", f"{m.taxa_nao_seguidores:.1f}%",
                          delta="✅ Meta" if ok else "❌ Abaixo")
            with r4:
                ok = leads_wpp >= KPIS["leads_semana_min"]
                st.metric("📱 Leads", str(leads_wpp),
                          delta="✅ Meta" if ok else "❌ Abaixo")
            st.success("✅ Métricas salvas em disco!")

    # Histórico de métricas
    if st.session_state.get("historico_metricas"):
        st.markdown("### 📋 Histórico de Métricas")
        df = pd.DataFrame(st.session_state["historico_metricas"])
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "⬇️ Exportar Métricas (JSON)",
            data=json.dumps(st.session_state["historico_metricas"], ensure_ascii=False, indent=2),
            file_name="metricas_historico.json",
            mime="application/json",
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7 — PROCESSADOR EM LOTE
# ═══════════════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown("## 📦 Processador em Lote")
    st.markdown("Gera prompts, slides e cronograma para todas as ideias selecionadas de uma vez.")

    if not st.session_state.get("ideias_selecionadas"):
        st.info("📌 Selecione ideias na aba **Ideias** primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        st.markdown(f"**{len(ideias_sel)} ideia(s) selecionada(s).**")

        st.markdown("### ⚙️ Opções")
        c1, c2, c3 = st.columns(3)
        with c1:
            fazer_prompts    = st.checkbox("🎨 Prompts de Imagem",       value=True)
        with c2:
            fazer_slides     = st.checkbox("🖼️ Slides com Templates",    value=True)
        with c3:
            fazer_cronograma = st.checkbox("📅 Cronograma",              value=True)

        if st.button("🚀 Processar Tudo em Lote", type="primary", use_container_width=True):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                results: dict = {}
                progress_bar = st.progress(0)
                status_msg   = st.empty()
                total_steps  = len(ideias_sel) + (1 if fazer_cronograma else 0)
                step         = 0

                for idx, ideia in enumerate(ideias_sel):
                    titulo = ideia.get("titulo", f"Ideia {idx+1}")
                    status_msg.text(f"⚙️ Processando: {titulo}…")

                    if fazer_prompts:
                        ctx = (
                            f"Carrossel:\n{json.dumps(ideia, ensure_ascii=False)}\n\n"
                            f"Slides:\n{json.dumps(ideia.get('slides_sugeridos',[]), ensure_ascii=False)}"
                        )
                        raw = call_gemini(PROMPT_PROMPTS_IMAGEM, ctx)
                        if raw:
                            results[f"prompts_{idx}"] = {"titulo": titulo, "prompts": extract_json(raw)}

                    if fazer_slides:
                        tkey = eixo_para_template(ideia.get("eixo", "Didático"))
                        imgs = generate_all_slides(tkey, ideia.get("slides_sugeridos", []))
                        results[f"slides_{idx}"] = {"titulo": titulo, "images": imgs}

                    step += 1
                    progress_bar.progress(step / total_steps)

                if fazer_cronograma:
                    status_msg.text("📅 Gerando cronograma…")
                    ctx = f"Ideias:\n{json.dumps(ideias_sel, ensure_ascii=False)}"
                    raw = call_gemini(get_prompt_cronograma(), ctx)
                    if raw:
                        cron_data = extract_json(raw)
                        results["cronograma"] = cron_data
                        save_geracao("cronograma", cron_data)
                    step += 1
                    progress_bar.progress(step / total_steps)

                status_msg.text("✅ Processamento concluído!")
                st.session_state["batch_results"] = results
                st.success(f"✅ {len(ideias_sel)} carrosseis processados!")

        # ── Resultados do lote ───────────────────────────────────────────────
        if st.session_state.get("batch_results"):
            results = st.session_state["batch_results"]

            # Prompts
            prompts_items = {k: v for k, v in results.items() if k.startswith("prompts_")}
            if prompts_items:
                st.markdown("#### 🎨 Prompts Gerados")
                for key, item in prompts_items.items():
                    with st.expander(f"📋 {item['titulo']}", expanded=False):
                        for slide in item["prompts"].get("slides", []):
                            sn = slide.get("slide_num", "?")
                            st.markdown(f"**Slide {sn}:**")
                            st.code(slide.get("prompt_en", ""), language=None)
                            clipboard_button(
                                slide.get("prompt_en", ""),
                                f"📋 Copiar Slide {sn}",
                                key=f"clip_lote_{key}_{sn}",
                            )
                            st.markdown(f"📝 `{slide.get('text_overlay','')}`")
                            st.divider()

            # Slides
            slides_items = {k: v for k, v in results.items() if k.startswith("slides_")}
            if slides_items:
                st.markdown("#### 🖼️ Slides Gerados")
                for key, item in slides_items.items():
                    with st.expander(f"🎠 {item['titulo']}", expanded=False):
                        for sn, sb in item["images"]:
                            st.image(sb, caption=f"Slide {sn}")

            # Cronograma
            if "cronograma" in results:
                st.markdown("#### 📅 Cronograma")
                all_days = (
                    [dict(d, semana=1) for d in results["cronograma"].get("semana_1", [])]
                    + [dict(d, semana=2) for d in results["cronograma"].get("semana_2", [])]
                )
                for day in all_days:
                    render_schedule_day(day)

            # Export ZIP completo
            st.divider()
            if st.button("📥 Exportar Lote Completo (ZIP)", use_container_width=True):
                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for key, item in prompts_items.items():
                        fname = item["titulo"][:50].replace(" ", "_")
                        zf.writestr(
                            f"prompts/{fname}.json",
                            json.dumps(item["prompts"], ensure_ascii=False, indent=2),
                        )
                    for key, item in slides_items.items():
                        folder = item["titulo"][:30].replace(" ", "_")
                        for sn, sb in item["images"]:
                            zf.writestr(f"slides/{folder}/slide_{sn}.png", sb)
                    if "cronograma" in results:
                        zf.writestr(
                            "cronograma.json",
                            json.dumps(results["cronograma"], ensure_ascii=False, indent=2),
                        )
                st.download_button(
                    "⬇️ Download ZIP",
                    data=zip_buf.getvalue(),
                    file_name=f"lote_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip",
                    use_container_width=True,
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 8: NOTEBOOKLM
# ═══════════════════════════════════════════════════════════════════════════════
with tab8:
    st.markdown("## 🔬 NotebookLM — Motor de Tendências e Ideias")
    st.markdown("Consulte notebooks existentes no NotebookLM para buscar tendências e gerar ideias baseadas em fontes reais.")

    # Verificar autenticação
    try:
        notebooks = nlm.list_notebooks()
        authenticated = True
    except Exception:
        notebooks = []
        authenticated = False

    if not authenticated:
        st.error("❌ NotebookLM não autenticado. Execute: `notebooklm login`")
    else:
        # Notebook fixo para Ensina Mais Tatuapé
        NOTEBOOK_ID_FIXO = "7f415de3-0f02-4eb9-b5f1-3d104a00354a"
        NOTEBOOK_TITULO = "Estratégia de Engajamento e Crescimento: Ensina Mais Tatuapé"
        
        selected_nb_id = NOTEBOOK_ID_FIXO
        
        # Sidebar com info do notebook
        with st.sidebar:
            st.markdown("---")
            st.markdown("## 🔬 NotebookLM")
            st.markdown(f"**Notebook ativo:**")
            st.info(f"📚 {NOTEBOOK_TITULO}")
            st.caption(f"ID: {selected_nb_id[:12]}...")

        # Opções de consulta
        st.markdown("### 🔍 Tipo de Consulta")
        
        col1, col2 = st.columns(2)
        with col1:
            consulta_tipo = st.radio(
                "O que deseja buscar:",
                ["📈 Tendências do Setor", "💡 Ideias de Carrossel", "🏢 Análise de Concorrência", "❓ Pergunta Livre"],
                key="nb_consulta_tipo"
            )
        
        with col2:
            if consulta_tipo == "❓ Pergunta Livre":
                pergunta_livre = st.text_area(
                    "Digite sua pergunta:",
                    placeholder="Ex: Quais são as maiores dúvidas de pais sobre frações?",
                    key="nb_pergunta_livre"
                )

        # Botão de busca
        if st.button("🔍 Buscar no NotebookLM", type="primary", use_container_width=True):
            if not selected_nb_id:
                st.warning("⚠️ Selecione um notebook primeiro.")
            else:
                with st.spinner("🤖 Consultando NotebookLM..."):
                    if consulta_tipo == "📈 Tendências do Setor":
                        result = nlm.get_trends(selected_nb_id)
                    elif consulta_tipo == "💡 Ideias de Carrossel":
                        result = nlm.generate_ideas(selected_nb_id)
                    elif consulta_tipo == "🏢 Análise de Concorrência":
                        result = nlm.get_competitor_analysis(selected_nb_id)
                    else:
                        result = nlm.search_in_notebook(selected_nb_id, pergunta_livre)
                    
                    if result:
                        st.session_state["nb_result"] = result
                        st.success("✅ Consulta concluída!")
                    else:
                        st.error("❌ Não foi possível obter resposta do notebook.")

        # Exibir resultado
        if "nb_result" in st.session_state and st.session_state["nb_result"]:
            result = st.session_state["nb_result"]
            
            # Exibir resposta do NotebookLM em Markdown
            st.markdown("### 📄 Resposta do NotebookLM")
            st.markdown(result)
            
            # Tentar parsear como JSON (fallback)
            try:
                data = json.loads(result)
                
                # Exibir tendências
                if "tendencias" in data:
                    st.markdown("### 📈 Tendências Identificadas")
                    for t in data["tendencias"]:
                        potencial = t.get("potencial", "médio")
                        cor = "#4ECDC4" if potencial == "alto" else "#FFD166" if potencial == "médio" else "#888"
                        st.markdown(f"""
                        <div class="metric-box">
                            <strong style="color:{cor};">{t.get('nome', '')}</strong>
                            <span style="color:#888; font-size:0.85em;">[{potencial}]</span>
                            <br><span style="color:#ccc;">{t.get('descricao', '')}</span>
                        </div>
                        """, unsafe_allow_html=True)
                
                # Exibir dores dos pais
                if "dores_pais" in data:
                    st.markdown("### 😰 Dores dos Pais")
                    for d in data["dores_pais"]:
                        with st.expander(f"💔 {d.get('dor', '')}"):
                            st.markdown(f"**Frequência:** {d.get('frequencia', '')}")
                            st.markdown(f"**Oportunidade:** {d.get('oportunidade', '')}")
                
                # Exibir oportunidades
                if "oportunidades" in data:
                    st.markdown("### 🎯 Oportunidades")
                    for o in data["oportunidades"]:
                        st.success(f"**{o.get('oportunidade', '')}** → {o.get('acao_sugerida', '')}")
                
                # Exibir ideias
                if "ideias" in data:
                    st.markdown("### 💡 Ideias Geradas")
                    
                    # Botão para enviar todas as ideias para o gerador de prompts
                    if st.button("📤 Enviar ideias para Gerador de Prompts", type="primary", use_container_width=True):
                        # Formatar ideias no formato esperado pelo PROMPT_PROMPTS_IMAGEM
                        ideias_formatadas = []
                        for ideia in data["ideias"]:
                            ideia_formatada = {
                                "titulo": ideia.get("titulo", ""),
                                "eixo": ideia.get("eixo", "Didático"),
                                "tema": ideia.get("tema", ""),
                                "publico_alvo": ideia.get("publico_alvo", "Pais de classes A/B do Tatuapé"),
                                "palavras_chave_seo": ["apoio escolar Tatuapé", "reforço escolar Tatuapé"],
                                "cta": ideia.get("cta", "DESAFIO"),
                                "slides_sugeridos": ideia.get("slides_sugeridos", []),
                                "kpi_alvo": ideia.get("kpi_alvo", "Salvamentos/Envios/Leads"),
                                "justificativa": ideia.get("justificativa", ideia.get("fonte_notebook", "")),
                                "fonte_notebook": ideia.get("fonte_notebook", ""),
                            }
                            ideias_formatadas.append(ideia_formatada)
                        
                        # Salvar no session_state para usar na aba de prompts
                        st.session_state["ideias_selecionadas"] = ideias_formatadas
                        st.session_state["nb_ideias_para_prompts"] = True
                        st.success(f"✅ {len(ideias_formatadas)} ideias enviadas! Vá para a aba '🎨 Prompts Google Flow'")
                    
                    # Exibir cada ideia
                    for i, ideia in enumerate(data["ideias"]):
                        with st.expander(f"{'🔴' if i==0 else '🟡' if i==1 else '🟢'} {ideia.get('titulo', '')}"):
                            st.markdown(f"**Eixo:** {ideia.get('eixo', '')}")
                            st.markdown(f"**Tema:** {ideia.get('tema', '')}")
                            st.markdown(f"**Público:** {ideia.get('publico_alvo', 'Pais de classes A/B do Tatuapé')}")
                            st.markdown(f"**CTA:** `{ideia.get('cta', '')}`")
                            st.markdown(f"**Fonte Notebook:** {ideia.get('fonte_notebook', '')}")
                            
                            # Botão para enviar ideia individual
                            if st.button(f"📤 Enviar para Prompts", key=f"send_idea_{i}"):
                                ideia_formatada = {
                                    "titulo": ideia.get("titulo", ""),
                                    "eixo": ideia.get("eixo", "Didático"),
                                    "tema": ideia.get("tema", ""),
                                    "publico_alvo": ideia.get("publico_alvo", "Pais de classes A/B do Tatuapé"),
                                    "palavras_chave_seo": ["apoio escolar Tatuapé", "reforço escolar Tatuapé"],
                                    "cta": ideia.get("cta", "DESAFIO"),
                                    "slides_sugeridos": ideia.get("slides_sugeridos", []),
                                    "kpi_alvo": ideia.get("kpi_alvo", "Salvamentos/Envios/Leads"),
                                    "justificativa": ideia.get("justificativa", ideia.get("fonte_notebook", "")),
                                    "fonte_notebook": ideia.get("fonte_notebook", ""),
                                }
                                if "ideias_selecionadas" not in st.session_state:
                                    st.session_state["ideias_selecionadas"] = []
                                st.session_state["ideias_selecionadas"].append(ideia_formatada)
                                st.success(f"✅ '{ideia.get('titulo', '')}' enviada para Prompts!")
                
                # Exibir análise de concorrência
                if "concorrentes" in data:
                    st.markdown("### 🏢 Análise de Concorrência")
                    for c in data["concorrentes"]:
                        with st.expander(f"🏫 {c.get('nome', '')}"):
                            st.markdown(f"**O que faz:** {c.get('o_que_faz', '')}")
                            st.markdown(f"**Pontos fortes:** {c.get('pontos_fortes', '')}")
                            st.markdown(f"**Pontos fracos:** {c.get('pontos_fracos', '')}")
                
                # Exibir dados relevantes
                if "dados_relevantes" in data:
                    st.markdown("### 📊 Dados Relevantes")
                    for d in data["dados_relevantes"]:
                        st.info(f"**{d.get('dado', '')}**\nFonte: {d.get('fonte', '')}")
                
            except json.JSONDecodeError:
                # Exibir como texto
                st.markdown("### 📄 Resposta do NotebookLM")
                st.markdown(result)
            
            # Botões de ação
            st.markdown("---")
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("📤 Enviar como Tendências", use_container_width=True):
                    st.session_state["tendencias_texto"] = result
                    st.success("✅ Enviado! Vá para aba '📈 Tendências'")
            
            with col2:
                if st.button("📤 Enviar como Contexto para Ideias", use_container_width=True):
                    st.session_state["nb_contexto_para_ideias"] = result
                    st.success("✅ Enviado! Vá para aba '💡 Ideias' e use este contexto")

        # Link direto para o notebook
        if selected_nb_id:
            st.markdown("---")
            st.markdown(f"### 🔗 Link direto para o notebook")
            st.markdown(f"[Abrir no NotebookLM](https://notebooklm.google.com/notebook/{selected_nb_id})")
