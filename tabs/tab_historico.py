"""
tabs/tab_historico.py — Aba de Histórico de Gerações e Backup.
"""

import json
import zipfile
from datetime import datetime
from io import BytesIO

import streamlit as st

from backup import apply_backup_zip, build_backup_zip, preview_backup
from persistence import load_historico_geracoes
from tabs.tab_ideias import _ensure_idea_ids
from tabs.tab_tendencias import _normalizar_tendencias


def render():
    """Renderiza a aba de Histórico."""
    st.markdown("## 🗂️ Histórico de Gerações")
    st.markdown("Últimas 50 gerações salvas em disco. Expanda para ver o conteúdo e restaure qualquer uma.")

    historico = load_historico_geracoes()

    if not historico:
        st.info("Nenhuma geração salva ainda. Gere conteúdo nas outras abas e ele aparecerá aqui.")
    else:
        tipos_disponiveis = ["Todos"] + sorted({e.get("tipo", "?") for e in historico})
        filtro_tipo = st.selectbox("Filtrar por tipo:", tipos_disponiveis)
        filtrado = [e for e in historico if filtro_tipo == "Todos" or e.get("tipo") == filtro_tipo]

        st.caption(f"Mostrando {len(filtrado)} de {len(historico)} gerações (mais recentes primeiro).")

        _TIPO_META = {
            "tendencias": ("tendencias", "📈"),
            "ideias": ("ideias", "💡"),
            "prompts": ("prompts_lote", "🎨"),
            "legendas": ("legendas_lote", "📝"),
            "cronograma": ("cronograma", "📅"),
            "video_curto": ("video_curto", "🎬"),
        }

        for pos, entrada in enumerate(reversed(filtrado)):
            tipo = entrada.get("tipo", "?")
            quando = entrada.get("gerado_em", "?")
            dados = entrada.get("dados", {})
            if tipo == "tendencias":
                dados = _normalizar_tendencias(dados)
            session_key = _TIPO_META.get(tipo, (tipo, "📦"))[0]
            icon = _TIPO_META.get(tipo, (tipo, "📦"))[1]

            if tipo == "ideias":
                n = len(dados.get("ideias", []))
                resumo = f"{n} ideias — {dados.get('ideias', [{}])[0].get('titulo', '')[:60]}" if n else "vazio"
            elif tipo == "prompts":
                prompts_inner = dados.get("prompts", dados)
                resumo = f"{len(prompts_inner.get('slides', []))} slides de prompt"
            elif tipo == "legendas":
                resumo = f"{len(dados.get('legendas', []))} legendas"
            elif tipo == "cronograma":
                resumo = f"{len(dados.get('semana_1', [])) + len(dados.get('semana_2', []))} posts agendados"
            elif tipo == "tendencias":
                resumo = f"{len(dados.get('tendencias_conteudo', []))} tendências"
            else:
                resumo = str(dados)[:80]

            with st.expander(f"{icon} {tipo.title()} — {quando} — {resumo}", expanded=False):
                if session_key:
                    if st.button("↩️ Restaurar esta geração", key=f"restaurar_hist_{pos}", width="stretch"):
                        if session_key == "prompts_lote":
                            st.session_state.setdefault("prompts_lote", []).append(dados)
                        elif session_key == "legendas_lote":
                            st.session_state.setdefault("legendas_lote", []).append(dados)
                        elif session_key == "ideias":
                            _ensure_idea_ids(dados.get("ideias", []), "historico")
                            st.session_state["ideias"] = dados
                            st.session_state["ideias_selecionadas"] = dados.get("ideias", [])
                        else:
                            st.session_state[session_key] = dados
                        st.success(f"✅ Restaurado! Veja na aba correspondente ({tipo}).")
                        st.rerun()

                st.json(dados, expanded=False)

    st.divider()
    st.markdown("### 💾 Backup e restauração")
    st.caption("Exporte métricas e histórico para transportar ou proteger os dados locais.")

    backup_col, restore_col = st.columns(2)
    with backup_col:
        st.download_button(
            "⬇️ Exportar backup completo",
            data=build_backup_zip(),
            file_name=f"motor_carrosseis_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
            mime="application/zip",
            width="stretch",
        )

    with restore_col:
        backup_upload = st.file_uploader(
            "Importar backup (.zip)",
            type=["zip"],
            key="backup_upload",
        )

    if backup_upload is not None:
        backup_bytes = backup_upload.getvalue()
        try:
            backup_info = preview_backup(backup_bytes)
            st.info(
                f"Backup de {backup_info['manifest'].get('gerado_em', 'data desconhecida')} · "
                f"{backup_info['total_itens']} registros encontrados."
            )
            modo_backup = st.radio(
                "Modo de importação",
                ["merge", "replace"],
                format_func=lambda modo: (
                    "Mesclar com os dados atuais" if modo == "merge" else "Substituir os dados atuais"
                ),
                horizontal=True,
                key="backup_mode",
            )
            if st.button("📥 Aplicar backup", type="primary", key="apply_backup"):
                ok, mensagem = apply_backup_zip(backup_bytes, mode=modo_backup)
                if ok:
                    st.session_state.pop("_synced", None)
                    st.success(mensagem)
                    st.rerun()
                else:
                    st.error(mensagem)
        except (ValueError, OSError, zipfile.BadZipFile) as exc:
            st.error(f"❌ Backup inválido: {exc}")
