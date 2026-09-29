"""
tabs/tab_prompts.py — Aba de Prompts Google Flow.

Mudanças:
  P1-1: Botão "Gerar Prompts para Todas as Ideias Selecionadas"
  P1-2: Editor inline de prompts (text_area editável antes de exportar)
"""

import json

import streamlit as st

from batch_engine import gerar_prompts_ideia, normalizar_prompts
from config import CORES
from prompts import DICAS_SERIE_FLOW, cor_eh_valida, formatar_txt_prompts, validate_prompts
from refs_catalog import arquivo_principal, rotulos_referencias
from tabs._ui import api_key_ok, clipboard_button, empty_state, esc


def render():
    """Renderiza a aba de Prompts para Google Flow."""
    st.markdown("## 🎨 Prompts para Google Flow")
    st.markdown("Gera prompts em inglês para criar cada slide com IA generativa.")

    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
        return

    ideias_sel = st.session_state["ideias_selecionadas"]

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
                    dados = gerar_prompts_ideia(ideia, forcar=True, avisos=avisos_gen, corrigidos=corrigidos_gen)
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

    if st.button("🎨 Gerar Prompts", type="primary", width="stretch"):
        if not api_key_ok():
            st.warning("⚠️ Configure a chave API Gemini.")
        else:
            ideia = opcoes_p[escolha]
            with st.spinner("🤖 Gerando prompts de imagem…"):
                avisos_gen: list = []
                corrigidos_gen: list = []
                dados = gerar_prompts_ideia(
                    ideia, forcar=True, avisos=avisos_gen, corrigidos=corrigidos_gen
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

        # ── P1-2: Editor inline de prompts por slide ─────────────────────
        st.markdown("### 📸 Prompts por Slide")
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
