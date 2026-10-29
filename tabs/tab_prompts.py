"""
tabs/tab_prompts.py — Aba de Prompts Google Flow.

Mudanças:
  P1-1: Botão "Gerar Prompts para Todas as Ideias Selecionadas"
  P1-2: Editor inline de prompts (text_area editável antes de exportar)
"""

import json

import streamlit as st

from acervo import avaliar_promocao, promover_para_acervo, resumo_acervo
from batch_engine import gerar_prompts_ideia, normalizar_prompts
from brief import montar_brief, montar_storyboard, resumo_storyboard, validar_brief
from config import CORES
from prompts import DICAS_SERIE_FLOW, cor_eh_valida, formatar_txt_prompts, validate_prompts
from refs_catalog import arquivo_principal, rotulos_referencias
from tabs._ui import api_key_ok, clipboard_button, empty_state, esc, seletor_fidelidade


def _prompts_da_ideia(ideia_id: str) -> dict | None:
    """Procura no lote da sessão os prompts já gerados para uma ideia."""
    if not ideia_id:
        return None
    for item in st.session_state.get("prompts_lote", []):
        if (item.get("ideia") or {}).get("id") == ideia_id:
            return item.get("prompts")
    return None


def render():
    """Renderiza a aba de Prompts para Google Flow."""
    st.markdown("## 🎨 Prompts para Google Flow")
    st.markdown("Gera prompts em inglês para criar cada slide com IA generativa.")

    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
        return

    ideias_sel = st.session_state["ideias_selecionadas"]
    fidelidade = seletor_fidelidade("fidelidade_prompts")

    # ── P1-1: Botão "Gerar para Todas" ──────────────────────────────────
    with st.container(border=True):
        st.markdown("### ⚡ Geração em Lote")
        st.caption(f"Você tem {len(ideias_sel)} ideia(s) selecionada(s). Gere prompts para todas de uma vez.")
        if st.button("🚀 Gerar Prompts para Todas as Ideias", type="primary", width="stretch", key="btn_prompts_all"):
            if not api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                progress = st.progress(0)
                status = st.empty()
                avisos_gerais: list[str] = []
                corrigidos_gerais: list[str] = []

                for idx, ideia in enumerate(ideias_sel):
                    titulo = ideia.get("titulo", f"Ideia {idx + 1}")
                    status.info(f"🎨 [{idx + 1}/{len(ideias_sel)}] Gerando prompts: {titulo}…")
                    avisos_gen: list = []
                    corrigidos_gen: list = []
                    dados = gerar_prompts_ideia(
                        ideia, forcar=True, avisos=avisos_gen, corrigidos=corrigidos_gen,
                        fidelidade=fidelidade,
                    )
                    if dados:
                        item_gen = {
                            "titulo": titulo,
                            "prompts": dados,
                            "ideia": ideia,
                            "avisos": avisos_gen,
                            "corrigidos": corrigidos_gen,
                        }
                        st.session_state.setdefault("prompts_lote", []).append(item_gen)
                        from persistence import save_geracao
                        save_geracao("prompts", item_gen)
                        avisos_gerais.extend(avisos_gen)
                        corrigidos_gerais.extend(corrigidos_gen)
                    progress.progress((idx + 1) / len(ideias_sel))

                status.empty()
                n = len(ideias_sel)
                st.success(f"✅ {n} prompts gerados!")
                if avisos_gerais:
                    st.warning(f"⚠️ {len(avisos_gerais)} aviso(s) de validação no total.")
                if corrigidos_gerais:
                    for c in corrigidos_gerais:
                        st.success(f"🛠️ {c}")
                st.rerun()

    st.divider()

    # ── Geração individual ───────────────────────────────────────────────
    opcoes_p = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
    escolha = st.selectbox("Ideia para gerar prompts:", list(opcoes_p.keys()), key="sel_prompt")

    # ── Brief e storyboard (V8) ──────────────────────────────────────────
    with st.expander("🗂 Brief e storyboard"):
        _ideia_sel = opcoes_p[escolha]
        _brief = montar_brief(_ideia_sel, tom=None, fidelidade=fidelidade, modo="vivo")
        _avisos_brief = validar_brief(_brief)
        st.caption(
            "O brief é o contrato do carrossel (para quem, com que objetivo, em que "
            "voz, com que aparência) e o storyboard é o mesmo contrato no tempo. "
            "O renderer de animação (V9) vai consumir este JSON."
        )
        st.json(
            {k: _brief[k] for k in ("titulo", "eixo", "tom", "cta", "referencias", "fidelidade", "trilha")},
            expanded=False,
        )
        if _avisos_brief:
            for _a in _avisos_brief:
                st.warning(_a)

        _col1, _col2 = st.columns(2)
        with _col1:
            if st.button("Gerar storyboard", key="btn_storyboard", width="stretch"):
                _sb = montar_storyboard(_brief, prompts=_prompts_da_ideia(_ideia_sel.get("id", "")))
                st.session_state["storyboard_atual"] = _sb
                st.success(
                    f"Storyboard com {_sb['total_frames']} frames "
                    f"({_sb['duracao_total_s']}s a {_sb['bpm']} bpm)."
                )
        with _col2:
            _sb_atual = st.session_state.get("storyboard_atual")
            if _sb_atual:
                _res = resumo_storyboard(_sb_atual)
                st.metric("Duração", f"{_res['duracao_total_s']}s")
                st.download_button(
                    "Baixar storyboard.json",
                    data=json.dumps(_sb_atual, ensure_ascii=False, indent=2),
                    file_name="storyboard.json",
                    mime="application/json",
                    key="dl_storyboard",
                )

        _sb_atual = st.session_state.get("storyboard_atual")
        if _sb_atual:
            for _a in _sb_atual.get("avisos", []):
                st.info(_a)

    # ── Acervo: o que já funcionou ───────────────────────────────────────
    _resumo = resumo_acervo()
    with st.expander(
        f"\N{BOOKS} Acervo — {_resumo['total']} carrossel(is) aprovado(s)"
        + (f" · média de {_resumo['taxa_media']}% de salvamentos" if _resumo["com_metrica"] else ""),
    ):
        st.caption(
            "Post **publicado** e com a taxa de salvamento no alvo do eixo entra no "
            "acervo. O DNA dele (estrutura, recursos, paleta) é lido nas próximas "
            "gerações, para o feed não nascer com cara de template."
        )
        _pode, _motivo = avaliar_promocao(opcoes_p[escolha])
        (_st_ok := st.success)(_motivo) if _pode else (_st_ok := st.info)(_motivo)
        if st.button("Promover ao acervo", key="btn_promover_acervo", disabled=not _pode):
            registro, motivo = promover_para_acervo(
                opcoes_p[escolha],
                prompts=_prompts_da_ideia(opcoes_p[escolha].get("id", "")),
                forcar=not _pode,
            )
            if registro:
                st.success(f"\N{WHITE HEAVY CHECK MARK} Acervo atualizado: {motivo}")
                st.rerun()

    st.divider()


    if st.button("🎨 Gerar Prompts", type="primary", width="stretch"):
        if not api_key_ok():
            st.warning("⚠️ Configure a chave API Gemini.")
        else:
            ideia = opcoes_p[escolha]
            with st.spinner("🤖 Gerando prompts de imagem…"):
                avisos_gen: list = []
                corrigidos_gen: list = []
                dados = gerar_prompts_ideia(
                    ideia, forcar=True, avisos=avisos_gen, corrigidos=corrigidos_gen,
                    fidelidade=fidelidade,
                )
                if dados:
                    titulo = ideia.get("titulo", "Ideia")
                    item_gen = {
                        "titulo": titulo,
                        "prompts": dados,
                        "ideia": ideia,
                        "avisos": avisos_gen,
                        "corrigidos": corrigidos_gen,
                    }
                    st.session_state.setdefault("prompts_lote", []).append(item_gen)
                    from persistence import save_geracao
                    save_geracao("prompts", item_gen)
                    novo_idx_p = len(st.session_state["prompts_lote"])
                    st.session_state["sel_prompts_lote"] = f"{novo_idx_p}. {titulo}"
                    for c in corrigidos_gen:
                        st.success(f"🛠️ {c}")
                    if avisos_gen:
                        st.warning(f"⚠️ {len(avisos_gen)} aviso(s) na validação dos prompts gerados.")
                    else:
                        st.success("✅ Prompts gerados e validados!")
                    st.rerun()

    # ── Exibição dos prompts gerados ─────────────────────────────────────
    if st.session_state.get("prompts_lote"):
        prompts_items = st.session_state["prompts_lote"]
        labels_p = [f"{n + 1}. {it.get('titulo', 'Ideia')}" for n, it in enumerate(prompts_items)]

        if len(prompts_items) > 1:
            if st.session_state.get("sel_prompts_lote") not in labels_p:
                st.session_state["sel_prompts_lote"] = labels_p[-1]
            csel, cdel = st.columns([5, 1])
            with csel:
                escolhido_p = st.selectbox("Geração de prompts:", labels_p, key="sel_prompts_lote")
                idx_p = labels_p.index(escolhido_p)
            with cdel:
                st.write("")
                if st.button("🗑️", key="del_prompts_lote", help="Remover esta geração"):
                    prompts_items.pop(idx_p)
                    if not prompts_items:
                        st.session_state.pop("prompts_lote", None)
                    st.session_state.pop("sel_prompts_lote", None)
                    st.rerun()
        else:
            idx_p = 0

        item_p = prompts_items[idx_p]
        titulo_p = item_p.get("titulo", "Carrossel")
        st.info(f"📌 **Carrossel:** {titulo_p}")

        prompts = item_p.get("prompts") if "prompts" in item_p else item_p
        if not isinstance(prompts, dict):
            prompts = {}
        else:
            prompts = normalizar_prompts(prompts)

        avisos_p = item_p.get("avisos")
        if avisos_p is None:
            avisos_p = validate_prompts(prompts, item_p.get("ideia"))
        for c in item_p.get("corrigidos") or []:
            st.success(f"🛠️ {c}")
        if avisos_p:
            with st.expander(f"⚠️ Avisos de validação ({len(avisos_p)})", expanded=True):
                for a in avisos_p:
                    st.warning(a)

        # Paleta de cores
        paleta = prompts.get("paleta_cores", {})
        if paleta:
            st.markdown("### 🎨 Paleta")
            pcols = st.columns(len(paleta))
            for i, (nome, cor) in enumerate(paleta.items()):
                nome_seg = esc(nome)
                cor_txt = esc(str(cor))
                swatch = ""
                if cor_eh_valida(cor):
                    swatch = (
                        f'<div style="width:52px;height:52px;background:{str(cor).strip()};'
                        f' border-radius:8px;margin:0 auto 4px;'
                        f' border:1px solid {CORES["borda"]};'
                        f' box-shadow:{CORES["app_sombra"]};"></div>'
                    )
                with pcols[i]:
                    st.markdown(
                        f'<div style="text-align:center;">{swatch}'
                        f'<span style="color:{CORES["texto_sec"]};font-size:0.72em;">'
                        f"{nome_seg}<br>{cor_txt}</span></div>",
                        unsafe_allow_html=True,
                    )

        # Base prompt
        base_prompt = (prompts.get("base_prompt") or "").strip()
        if base_prompt:
            st.markdown("### 🧩 Base Prompt (consistência entre as 8 lâminas)")
            st.code(base_prompt, language=None)
            clipboard_button(base_prompt, "📋 Copiar Base Prompt", key="clip_base_prompt")

        # ── Studio Visual de Carrossel (Inspirado no Google Stitch MCP) ───────
        slides = prompts.get("slides", [])
        if slides:
            st.markdown("### 🎠 Studio Visual do Carrossel (Formato Instagram 4:5)")
            studio_key = f"_studio_slide_{idx_p}"
            if studio_key not in st.session_state or st.session_state[studio_key] >= len(slides):
                st.session_state[studio_key] = 0

            cur_idx = st.session_state[studio_key]
            cur_slide = slides[cur_idx]
            cur_num = cur_slide.get("slide_num", cur_idx + 1)
            cur_style = cur_slide.get("estilo", "Slide")
            cur_overlay = cur_slide.get("text_overlay", "")
            cur_pt = cur_slide.get("prompt_pt", "")

            # Controles de navegação rápida
            nav_c1, nav_c2, nav_c3 = st.columns([1, 4, 1])
            with nav_c1:
                if st.button("◀ Anterior", key=f"prev_slide_{idx_p}", width="stretch", disabled=(cur_idx == 0)):
                    st.session_state[studio_key] = max(0, cur_idx - 1)
                    st.rerun()
            with nav_c2:
                # Seletor de botões de miniaturas 1 a 8
                cols_thumbs = st.columns(len(slides))
                for s_i, sl in enumerate(slides):
                    s_label = f"S{sl.get('slide_num', s_i+1)}"
                    is_active = (s_i == cur_idx)
                    with cols_thumbs[s_i]:
                        if st.button(
                            s_label,
                            key=f"thumb_{idx_p}_{s_i}",
                            type="primary" if is_active else "secondary",
                            width="stretch",
                            help=sl.get("estilo", f"Slide {s_i+1}"),
                        ):
                            st.session_state[studio_key] = s_i
                            st.rerun()
            with nav_c3:
                if st.button("Próximo ▶", key=f"next_slide_{idx_p}", width="stretch", disabled=(cur_idx >= len(slides) - 1)):
                    st.session_state[studio_key] = min(len(slides) - 1, cur_idx + 1)
                    st.rerun()

            # Moldura do Slide 4:5 com Glassmorphism Stitch
            is_cta = (cur_num == 8 or "CTA" in cur_style.upper())
            badge_color = "#76BC21" if is_cta else "#2463eb"
            badge_text = "CTA FINAL & CONVERSÃO" if is_cta else cur_style.upper()

            st.html(f"""
<div style="display:flex; justify-content:center; margin: 16px 0 24px 0;">
    <div style="width:100%; max-width:480px; min-height:540px; background:linear-gradient(180deg, #14141d 0%, #0c0c11 100%);
                border:2px solid rgba(255, 255, 255, 0.1); border-radius:20px; box-shadow:0 20px 40px -10px rgba(0,0,0,0.8), 0 0 25px -5px rgba(36,99,235,0.25);
                padding:24px 26px; display:flex; flex-direction:column; justify-content:space-between; position:relative; overflow:hidden;">

        <div style="display:flex; justify-content:space-between; align-items:center; padding-bottom:14px; border-bottom:1px solid rgba(255,255,255,0.08); z-index:2;">
            <div style="display:flex; align-items:center; gap:10px;">
                <div style="width:32px; height:32px; border-radius:50%; background:linear-gradient(135deg, #2463eb 0%, #76BC21 100%); display:flex; align-items:center; justify-content:center; font-weight:800; font-size:12px; color:#FFFFFF;">
                    EM
                </div>
                <div>
                    <span style="font-weight:700; font-size:0.85rem; color:#FFFFFF; display:flex; align-items:center; gap:4px;">
                        ensinamais.tatuape
                        <span style="color:#2463eb; font-size:13px;">✓</span>
                    </span>
                    <span style="font-size:0.68rem; color:#94A3B8; display:block; margin-top:-2px;">Educação e Apoio Escolar</span>
                </div>
            </div>
            <span style="font-family:'JetBrains Mono',monospace; font-size:0.68rem; font-weight:700; color:{badge_color}; background:rgba(36,99,235,0.15); border:1px solid rgba(36,99,235,0.3); padding:3px 8px; border-radius:6px; letter-spacing:0.04em;">
                {esc(badge_text)}
            </span>
        </div>

        <div style="flex:1; display:flex; flex-direction:column; justify-content:center; align-items:center; text-align:center; padding:32px 12px; z-index:2;">
            <div style="font-size:1.45rem; font-weight:800; line-height:1.35; color:#FFFFFF; letter-spacing:-0.02em; text-shadow:0 2px 10px rgba(0,0,0,0.5); margin-bottom:18px;">
                "{esc(cur_overlay or 'Texto Principal do Slide')}"
            </div>
            <div style="font-size:0.82rem; color:#94A3B8; line-height:1.5; max-width:380px; background:rgba(0,0,0,0.4); padding:10px 14px; border-radius:10px; border:1px solid rgba(255,255,255,0.06);">
                💡 <strong style="color:#E2E8F0;">Cena:</strong> {esc(cur_pt[:180] + ('…' if len(cur_pt) > 180 else ''))}
            </div>
        </div>

        <div style="padding-top:14px; border-top:1px solid rgba(255,255,255,0.08); display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; color:#94A3B8; z-index:2;">
            <div style="display:flex; align-items:center; gap:4px; font-family:'JetBrains Mono',monospace; font-size:0.7rem; color:#64748B;">
                <span style="color:#76BC21;">📍</span> Tatuapé &bull; SP
            </div>
            <div style="color:{'#76BC21' if is_cta else '#60A5FA'}; font-weight:700; display:flex; align-items:center; gap:4px;">
                {'📲 Chame no WhatsApp (11) 94475-0009' if is_cta else 'Mova para o próximo ➔'}
            </div>
            <div style="font-family:'JetBrains Mono',monospace; font-weight:800; color:#E2E8F0;">
                {cur_num}/{len(slides)}
            </div>
        </div>
    </div>
</div>
            """)

        # ── P1-2: Editor inline de prompts por slide ─────────────────────
        st.markdown("### 📸 Prompts Detalhados por Slide")
        ref_labels = rotulos_referencias()

        # Flag para detectar edições
        _editor_key = f"_editor_prompts_{idx_p}"
        if _editor_key not in st.session_state:
            st.session_state[_editor_key] = False

        for slide in prompts.get("slides", []):
            snum = slide.get("slide_num", "?")
            with st.expander(f"Slide {snum} — {slide.get('estilo','')}", expanded=True):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**🇺🇸 Prompt (English):**")
                    # P1-2: text_area editável
                    prompt_en_key = f"edit_prompt_{idx_p}_{snum}"
                    prompt_en_editado = st.text_area(
                        f"Prompt Slide {snum}",
                        value=slide.get("prompt_en", ""),
                        key=prompt_en_key,
                        height=150,
                        label_visibility="collapsed",
                    )
                    if prompt_en_editado != slide.get("prompt_en", ""):
                        slide["prompt_en"] = prompt_en_editado
                        st.session_state[_editor_key] = True
                    clipboard_button(
                        slide.get("prompt_en", ""),
                        f"📋 Copiar prompt Slide {snum}",
                        key=f"clip_prompt_{snum}",
                    )
                with c2:
                    st.markdown("**🇧🇷 Descrição (Português):**")
                    st.markdown(slide.get("prompt_pt", ""))
                    overlay_key = f"edit_overlay_{idx_p}_{snum}"
                    overlay_editado = st.text_input(
                        f"Texto sobreposto Slide {snum}",
                        value=slide.get("text_overlay", ""),
                        key=overlay_key,
                        label_visibility="collapsed",
                    )
                    if overlay_editado != slide.get("text_overlay", ""):
                        slide["text_overlay"] = overlay_editado
                        st.session_state[_editor_key] = True

                refs = slide.get("referencias", [])
                if refs:
                    partes = []
                    for r in refs:
                        rot = ref_labels.get(r, r)
                        arq = arquivo_principal(r)
                        partes.append(f"{rot} (`{arq}`)" if arq else rot)
                    st.markdown(f"**📎 Referências para anexar no Flow:** {' | '.join(partes)}")

        # Botão para salvar edições do editor
        if st.session_state.get(_editor_key):
            if st.button("💾 Salvar Edições dos Prompts", type="primary", width="stretch", key=f"save_edits_{idx_p}"):
                from persistence import save_geracao
                save_geracao("prompts", item_p)
                st.session_state[_editor_key] = False
                st.success("✅ Edições salvas!")
                st.rerun()

        # Dicas gerais
        st.markdown("### 💡 Como gerar a série no Google Flow")
        st.info(DICAS_SERIE_FLOW)
        if prompts.get("dicas_gerais"):
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
                width="stretch",
            )
        with c2:
            txt_content = formatar_txt_prompts(prompts)
            st.download_button(
                "⬇️ Exportar .txt (automação)",
                data=txt_content,
                file_name="prompts_automaticacao.txt",
                mime="text/plain",
                width="stretch",
            )
