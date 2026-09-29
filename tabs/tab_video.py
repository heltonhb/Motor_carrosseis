"""
tabs/tab_video.py — Aba de Requisição de Vídeo Curto (Gemini Notebook).
"""

import json

import streamlit as st

from config import NOTEBOOK_ID_PADRAO
from gemini import call_gemini_json
from persistence import save_geracao
from prompts import PROMPT_VIDEO_CURTO, TEMPERATURAS
from tabs._ui import api_key_ok, clipboard_button, empty_state
import notebooklm_client as nlm


def render():
    """Renderiza a aba de Vídeo Curto."""
    st.markdown("## 🎬 Requisição de Vídeo Curto — Gemini Notebook")
    st.markdown(
        "Monta uma **requisição detalhada** para gerar um **Video Overview no formato \"Short\"** "
        "no Gemini Notebook (Studio): um vídeo vertical 9:16 de ~60s que condensa o tema central "
        "da ideia, **fiel ao roteiro dos slides**."
    )

    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
        return

    ideias_sel = st.session_state["ideias_selecionadas"]
    opcoes_v = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
    escolha_v = st.selectbox("Ideia de origem:", list(opcoes_v.keys()), key="sel_video")

    ideia = opcoes_v[escolha_v]
    slides_list = ideia.get("slides_sugeridos", [])

    if slides_list:
        with st.expander(f"📄 Roteiro de origem ({len(slides_list)} slides)", expanded=False):
            for slide in slides_list:
                st.markdown(f"**Slide {slide.get('slide','?')} — {slide.get('tipo','')}**")
                st.markdown(f"_{slide.get('texto','')}_")
                st.divider()
    else:
        st.warning("⚠️ Esta ideia não possui roteiro de slides. Gere os slides antes de montar a requisição.")

    salvar_nlm = st.checkbox(
        "🔬 Gravar também a requisição no notebook do Gemini Notebook (via CLI)",
        value=True,
        key="video_salvar_nlm",
    )

    if st.button("🎬 Montar Requisição de Vídeo", type="primary", width="stretch", key="btn_video"):
        if not api_key_ok():
            st.warning("⚠️ Configure a chave API Gemini.")
        else:
            ctx = (
                f"Carrossel:\n{json.dumps(ideia, ensure_ascii=False)}\n\n"
                f"Roteiro dos slides:\n{json.dumps(slides_list, ensure_ascii=False)}"
            )
            with st.spinner("🤖 Montando requisição para o Gemini Notebook…"):
                dados = call_gemini_json(PROMPT_VIDEO_CURTO, ctx, temperature=TEMPERATURAS["prompts_imagem"])
                if dados:
                    st.session_state["video_curto"] = dados
                    save_geracao("video_curto", dados)
                    st.success("✅ Requisição montada!")

    if st.session_state.get("video_curto"):
        vd = st.session_state["video_curto"]

        params = vd.get("parametros_geracao", {})
        if params:
            st.markdown("### ⚙️ Parâmetros de Geração")
            pcols = st.columns(4)
            p_itens = [
                ("Formato", params.get("format", "Short")),
                ("Idioma", params.get("language", "Português (Brasil)")),
                ("Duração", params.get("duracao", "~60s")),
                ("Estilo Visual", params.get("visual_style_custom") or params.get("visual_style", "Classic")),
            ]
            for i, (label, valor) in enumerate(p_itens):
                with pcols[i]:
                    from config import CORES
                    st.markdown(f"""
                    <div class="metric-box">
                        <strong style="color:{CORES['texto_sec']};font-size:0.72em;text-transform:uppercase;">{label}</strong><br>
                        <span style="color:{CORES['primaria']};font-weight:600;">{valor}</span>
                    </div>
                    """, unsafe_allow_html=True)

        steering = vd.get("steering_prompt", "")
        if steering:
            st.markdown("### 🎯 Steering Prompt (cole no campo de tópico/foco)")
            st.code(steering, language=None)
            clipboard_button(steering, "📋 Copiar Steering Prompt", key="clip_video_steering")

        narrativa = vd.get("narrativa", "")
        if narrativa:
            st.markdown("### 📖 Narrativa do Short (fiel ao roteiro)")
            st.markdown(narrativa)

        requisicao_completa = vd.get("requisicao_completa", "")
        if requisicao_completa:
            st.markdown("### 📦 Requisição Completa (para registro/gravação)")
            st.code(requisicao_completa, language=None)
            clipboard_button(requisicao_completa, "📋 Copiar Requisição Completa", key="clip_video_req")

            if salvar_nlm and nlm.is_nlm_available():
                if st.button("🔬 Gravar Requisição no Gemini Notebook", width="stretch", key="btn_video_nlm"):
                    with st.spinner("📚 Enviando para o Gemini Notebook…"):
                        nb_id = st.session_state.get("_nb_active_id") or NOTEBOOK_ID_PADRAO
                        resposta = nlm.ask_notebook(nb_id, requisicao_completa)
                        if resposta:
                            st.success("✅ Requisição gravada no Gemini Notebook!")
                        else:
                            st.warning("⚠️ Não foi possível gravar. Verifique a autenticação (`notebooklm login`).")
            elif salvar_nlm:
                st.warning("⚠️ CLI `notebooklm` não encontrado. A requisição não foi gravada.")

        if vd.get("instrucoes_uso"):
            st.divider()
            st.markdown("### 💡 Como Usar")
            st.info(vd["instrucoes_uso"])

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "⬇️ Exportar JSON",
                data=json.dumps(vd, ensure_ascii=False, indent=2),
                file_name="requisicao_video_curto.json",
                mime="application/json",
                width="stretch",
            )
        with c2:
            st.download_button(
                "⬇️ Exportar Requisição (.txt)",
                data=requisicao_completa,
                file_name="requisicao_video_curto.txt",
                mime="text/plain",
                width="stretch",
            )
