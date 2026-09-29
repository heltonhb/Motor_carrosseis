"""
tab_lote.py — Processador em Lote (Tab 7)
Gera prompts, slides e cronograma para todas as ideias selecionadas de uma vez.
"""
import json
import zipfile
from datetime import datetime
from io import BytesIO

import streamlit as st

from tabs._ui import api_key_ok, clipboard_button, empty_state, render_schedule_day
from batch_engine import normalizar_prompts, processar_lote
from persistence import save_geracao
from prompts import formatar_txt_prompts, validate_prompts


def render() -> None:
    st.markdown("## 📦 Processador em Lote")
    st.markdown("Gera prompts, slides e cronograma para todas as ideias selecionadas de uma vez.")

    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
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

        if st.button("🚀 Processar Tudo em Lote", type="primary", width="stretch"):
            if not api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                progress_bar = st.progress(0)
                status_msg   = st.empty()

                def _update_progress(step: int, total: int, msg: str):
                    status_msg.text(msg)
                    progress_bar.progress(step / total)

                results = processar_lote(
                    ideias_sel,
                    fazer_prompts=fazer_prompts,
                    fazer_slides=fazer_slides,
                    fazer_cronograma=fazer_cronograma,
                    forcar=True,
                    on_progress=_update_progress,
                )
                # Persistir cronograma (mesmo comportamento de antes)
                if fazer_cronograma and "cronograma" in results:
                    save_geracao("cronograma", results["cronograma"])
                # Prompts do lote entram no histórico como os das abas individuais
                if fazer_prompts:
                    for k_res, item_res in results.items():
                        if k_res.startswith("prompts_"):
                            save_geracao("prompts", item_res)

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
                for _key, item in prompts_items.items():
                    if isinstance(item.get("prompts"), dict):
                        item["prompts"] = normalizar_prompts(item["prompts"])
                    with st.expander(f"📋 {item['titulo']}", expanded=False):
                        for corr in item.get("corrigidos") or []:
                            st.success(f"🛠️ {corr}")
                        avisos_lote = item.get("avisos")
                        if avisos_lote is None:
                            avisos_lote = validate_prompts(
                                item.get("prompts") or {}, item.get("ideia")
                            )
                        for a in avisos_lote:
                            st.warning(a)
                        for slide in item["prompts"].get("slides", []):
                            sn = slide.get("slide_num", "?")
                            st.markdown(f"**Slide {sn}:**")
                            st.code(slide.get("prompt_en", ""), language=None)
                            clipboard_button(
                                slide.get("prompt_en", ""),
                                f"📋 Copiar Slide {sn}",
                                key=f"clip_lote_{_key}_{sn}",
                            )
                            st.markdown(f"📝 `{slide.get('text_overlay','')}`")
                            st.divider()

            # Slides
            slides_items = {k: v for k, v in results.items() if k.startswith("slides_")}
            if slides_items:
                st.markdown("#### 🖼️ Slides Gerados")
                for _key, item in slides_items.items():
                    with st.expander(f"🎠 {item['titulo']}", expanded=False):
                        for sn, sb, _info in item["images"]:
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
            if st.button("📥 Exportar Lote Completo (ZIP)", width="stretch"):
                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for _key, item in prompts_items.items():
                        fname = item["titulo"][:50].replace(" ", "_")
                        zf.writestr(
                            f"prompts/{fname}.json",
                            json.dumps(item["prompts"], ensure_ascii=False, indent=2),
                        )
                        zf.writestr(
                            f"prompts/{fname}.txt",
                            formatar_txt_prompts(item["prompts"]),
                        )
                    for _key, item in slides_items.items():
                        folder = item["titulo"][:30].replace(" ", "_")
                        for sn, sb, _info in item["images"]:
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
                    width="stretch",
                )
