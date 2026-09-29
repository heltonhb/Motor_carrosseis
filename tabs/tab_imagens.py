"""
tabs/tab_imagens.py — Aba de Gerador de Imagens com Texto Sobreposto.

Modos: Upload, Template e Carrossel Completo.
Extraído do app.py linhas 1446-1572.
"""

from io import BytesIO
import zipfile

import streamlit as st

from tabs._ui import esc, api_key_ok, empty_state
from image_utils import create_slide_from_template, add_text_overlay
from templates import TEMPLATES, eixo_para_template


def render() -> None:
    st.markdown("## 🖼️ Gerador de Imagens com Texto Sobreposto")

    # ── Modo 1: Upload ─────────────────────────────────────────────────────
    st.markdown("### 📤 Modo 1 — Upload de Imagem")
    uploaded = st.file_uploader("Imagem (JPG, PNG)", type=["jpg", "jpeg", "png"], key="upload_img")
    if uploaded:
        img_bytes = uploaded.read()
        st.image(img_bytes, caption="Original", width="stretch")
        c1, c2, c3 = st.columns(3)
        with c1:
            overlay_text = st.text_input("Texto sobreposto (PT-BR, ≤15 palavras):")
        with c2:
            font_sz = st.slider("Tamanho da fonte:", 24, 72, 48)
        with c3:
            pos = st.selectbox("Posição:", ["center", "bottom", "top"])

        if st.button("🖼️ Adicionar Texto", type="primary", width="stretch"):
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

    # ── Modo 2: Template único ─────────────────────────────────────────────
    st.markdown("### 📋 Modo 2 — Gerar com Template")
    tpl_opts = {f"{t['icone']} {t['nome']}": k for k, t in TEMPLATES.items()}
    tpl_choice = st.selectbox("Template:", list(tpl_opts.keys()), key="tpl_img")
    tpl_key = tpl_opts[tpl_choice]
    tpl_data = TEMPLATES[tpl_key]

    slide_num = st.number_input("Número do slide:", min_value=1, max_value=9, value=1)
    estrutura = tpl_data["estrutura"]
    default_text = estrutura[min(slide_num - 1, len(estrutura) - 1)].texto
    slide_text = st.text_area("Texto do slide:", value=default_text)

    if st.button("🖼️ Gerar Slide", type="primary", width="stretch"):
        with st.spinner("Gerando slide…"):
            sb, info = create_slide_from_template(tpl_key, int(slide_num), slide_text or "", return_info=True)
            st.image(sb, caption=f"Slide {slide_num} — {tpl_data['nome']}")
            if info.get("truncated"):
                st.warning(f"⚠️ Texto não coube nem com fonte {info['font_size']}px — {info['dropped']} linha(s) cortada(s). Encurte o texto.")
            elif info.get("auto_shrunk"):
                st.info(f"⏳ Fonte auto-reduzida para {info['font_size']}px para caber ({info['lines']} linhas).")
            st.download_button("⬇️ Download", data=sb,
                               file_name=f"slide_{slide_num}_{tpl_key}.png",
                               mime="image/png")

    st.divider()

    # ── Modo 3: Todos os slides de um carrossel ────────────────────────────
    st.markdown("### 🎠 Modo 3 — Gerar Carrossel Completo")
    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opts_c = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
        escolha_c = st.selectbox("Carrossel:", list(opts_c.keys()), key="carrossel_img")
        ideia = opts_c[escolha_c]
        slides_list = ideia.get("slides_sugeridos", [])
        tkey = eixo_para_template(ideia.get("eixo", "Didático"))

        # ── Revisão dos textos ANTES de gerar ──────────────────────────────
        if slides_list:
            with st.expander(f"✏️ Revisar textos dos slides antes de gerar ({len(slides_list)} slides)", expanded=True):
                st.caption("Edite os textos abaixo — eles serão usados na imagem. Fonte reduz ou corta trecho apenas se não couber; você será avisado.")
                for i, slide in enumerate(slides_list):
                    snum_ed = slide.get("slide", i + 1)
                    wkey = f"edt_{escolha_c}_{snum_ed}"
                    st.text_area(
                        f"Slide {snum_ed} — {slide.get('tipo', '')}",
                        value=slide.get("texto", ""),
                        key=wkey,
                        height=110,
                    )

        if st.button("🎠 Gerar Todos os Slides", type="primary", width="stretch"):
            # Textos editados (fallback: texto original da ideia)
            textos_edit = []
            for i, slide in enumerate(slides_list):
                snum_ed = slide.get("slide", i + 1)
                wkey = f"edt_{escolha_c}_{snum_ed}"
                texto_final = st.session_state.get(wkey, slide.get("texto", ""))
                textos_edit.append({"slide": snum_ed, "texto": texto_final})

            with st.spinner(f"Gerando {len(textos_edit)} slides…"):
                progress = st.progress(0)
                all_slides: list[tuple[int, bytes, dict]] = []
                avisos: list[str] = []
                for i, slide in enumerate(textos_edit):
                    sb, info = create_slide_from_template(tkey, slide["slide"], slide["texto"], return_info=True)
                    all_slides.append((slide["slide"], sb, info))
                    if info.get("truncated"):
                        avisos.append(f"⚠️ Slide {slide['slide']}: texto não coube nem com fonte {info['font_size']}px — {info['dropped']} linha(s) cortada(s). Encurte o texto e gere de novo.")
                    elif info.get("auto_shrunk"):
                        avisos.append(f"⏳ Slide {slide['slide']}: fonte auto-reduzida para {info['font_size']}px para caber ({info['lines']} linhas).")
                    progress.progress((i + 1) / len(textos_edit))

                st.success(f"✅ {len(all_slides)} slides gerados!")
                if avisos:
                    with st.expander(f"⚠️ Avisos de ajuste ({len(avisos)})", expanded=True):
                        for a in avisos:
                            st.warning(a)
                for sn, sb, _ in all_slides:
                    st.image(sb, caption=f"Slide {sn}")

                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for sn, sb, _ in all_slides:
                        zf.writestr(f"slide_{sn}.png", sb)
                st.download_button(
                    "⬇️ Download ZIP",
                    data=zip_buf.getvalue(),
                    file_name=f"carrossel_{ideia.get('titulo','')[:30].replace(' ','_')}.zip",
                    mime="application/zip",
                )
