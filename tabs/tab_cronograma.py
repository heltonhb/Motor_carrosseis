"""
tabs/tab_cronograma.py — Aba 6: Cronograma & Métricas.

Extraída do app.py (linhas 1710-2001) sem alteração na lógica.
"""

import csv
import json
import os
from io import StringIO

import pandas as pd
import streamlit as st

from tabs._ui import api_key_ok, empty_state, esc, render_schedule_day
from gemini import call_gemini_json, invalidate_cache
from prompts import get_prompt_cronograma, TEMPERATURAS
from persistence import (
    importar_metricas,
    limpar_metricas_vazias,
    load_metricas,
    save_geracao,
    save_metrica,
)
from ics_export import cronograma_para_ics
from templates import MetricaPost
from config import KPIS, CORES
from instagram_service import fetch_post_metrics


def render() -> None:
    """Renderiza a aba 6 — Cronograma & Métricas."""
    st.markdown("## 📅 Cronograma de Postagens & Acompanhamento")

    # ── Cronograma ───────────────────────────────────────────────────────────
    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        st.markdown(f"**{len(ideias_sel)} ideia(s) selecionada(s).**")

        if st.button("📅 Gerar Cronograma", type="primary", width="stretch"):
            if not api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ctx = f"Ideias selecionadas:\n{json.dumps(ideias_sel, ensure_ascii=False)}"
                with st.spinner("🤖 Montando cronograma com datas reais…"):
                    # get_prompt_cronograma() injeta a data atual
                    invalidate_cache(get_prompt_cronograma(), ctx)
                    dados = call_gemini_json(get_prompt_cronograma(), ctx, temperature=TEMPERATURAS["cronograma"])
                    if dados:
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
                (k4, "📱 Leads",       kpis.get("meta_leads",        "15-25"), CORES["primaria"]),
            ]
            for col, label, valor, cor in items:
                with col:
                    st.markdown(f"""
                    <div class="metric-box">
                        <strong style="color:{cor};">{label}</strong><br>
                        <span style="color:{CORES['texto']};font-size:1.2em;font-weight:700;">{valor}</span>
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

        # ── M5: export .ics para Google Calendar ───────────────────────────
        ics_texto, n_eventos = cronograma_para_ics(cron)
        if n_eventos > 0:
            st.download_button(
                "📅 Exportar Cronograma (.ics — Google Calendar)",
                data=ics_texto,
                file_name="cronograma_carrosseis.ics",
                mime="text/calendar",
                help=f"{n_eventos} eventos com lembrete 30min antes. Importe no Google Calendar: Configurações → Importar e exportar.",
            )
        else:
            st.caption("⚠️ Nenhuma data reconhecida no cronograma — .ics indisponível.")

    # ── Registro de Métricas ─────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📊 Registrar Métricas de Post")
    st.caption("Preencha após 72h da publicação para acompanhar os KPIs.")

    with st.form("form_metricas"):
        c1, c2 = st.columns(2)
        with c1:
            # Selectbox com os títulos já gerados (ideias + posts publicados):
            # o feedback loop casa por string de título — digitar à mão quebra
            # o aprendizado por erro de digitação
            _titulos_existentes = sorted({
                str(m.get("titulo", "")).strip()
                for m in st.session_state.get("historico_metricas", [])
                if str(m.get("titulo", "")).strip()
            })
            post_titulo = st.selectbox(
                "Título do post",
                options=_titulos_existentes or ["(digite abaixo)"],
                accept_new_options=True,
                help="Escolha o post ou digite um novo — o título é a chave que "
                     "conecta a métrica à ideia no feedback loop.",
            )
            if post_titulo == "(digite abaixo)":
                post_titulo = st.text_input("Novo título:")
            alcance      = st.number_input("Alcance Total",        min_value=0, value=0)
            salvamentos  = st.number_input("Salvamentos",          min_value=0, value=0)
            envios_dm    = st.number_input("Envios via DM",        min_value=0, value=0)
        with c2:
            nao_seg      = st.number_input("Alcance Não Seguidores", min_value=0, value=0)
            comentarios  = st.number_input("Comentários",           min_value=0, value=0)
            leads_wpp    = st.number_input("Leads WhatsApp",         min_value=0, value=0)
            data_post    = st.date_input("Data da publicação")

        submitted = st.form_submit_button("💾 Salvar Métricas", width="stretch")

        if submitted:
            if not post_titulo.strip():
                st.error("⚠️ Título do post é obrigatório — é ele que conecta a métrica à ideia no feedback loop.")
            elif alcance <= 0:
                st.error("⚠️ Alcance deve ser maior que zero para a métrica alimentar o aprendizado.")
            else:
                m = MetricaPost(
                    data=str(data_post),
                    titulo=post_titulo.strip(),
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
                if not save_metrica(m_dict):
                    st.warning("ℹ️ Métrica idêntica já registrada — nada salvo.")
                else:
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

    # ── V1: Importar métricas via CSV ──────────────────────────────────────────
    st.divider()
    st.markdown("### 📱 Importar Métricas do Instagram (CSV)")
    st.caption(
        "Use o CSV do Meta Business Suite. Formato esperado: "
        "data,titulo,alcance,salvamentos,envios,leads_whatsapp"
    )

    up = st.file_uploader("Carregar CSV", type=["csv"], key="csv_metrics_upload")
    if up is not None:
        try:
            content = up.read().decode("utf-8")
            reader = csv.DictReader(StringIO(content))

            # Validação do cabeçalho antes de importar qualquer linha
            obrigatorias = {"data", "titulo", "alcance", "salvamentos", "envios", "leads_whatsapp"}
            faltando = obrigatorias - {c.strip().lower() for c in (reader.fieldnames or [])}
            if faltando:
                st.error(
                    f"❌ CSV sem as colunas obrigatórias: {', '.join(sorted(faltando))}. "
                    "Use o modelo data/metricas_sample.csv."
                )
            else:
                linhas = list(reader)
                resumo = importar_metricas(linhas)

                # Espelha o disco no session_state (o gráfico e o histórico
                # só liam o que estava em memória desde o startup)
                st.session_state["historico_metricas"] = load_metricas()

                if resumo["importadas"] or resumo["duplicadas"] or resumo["invalidas"]:
                    partes = [f"✅ {resumo['importadas']} importada(s)"]
                    if resumo["duplicadas"]:
                        partes.append(f"{resumo['duplicadas']} duplicada(s) ignorada(s)")
                    if resumo["invalidas"]:
                        partes.append(f"{resumo['invalidas']} inválida(s) (sem título ou alcance 0)")
                    st.success(" · ".join(partes) + ".")
                else:
                    st.info("ℹ️ Nenhuma linha no CSV.")
        except Exception as e:
            st.error(f"❌ Erro ao ler CSV: {e}")

    # ── V1: Importar métricas via Instagram Graph API ──────────────────────────
    st.divider()
    st.markdown("### 📱 Importar Métricas do Instagram (API)")
    st.caption("Preencha as credenciais no .env. A API busca alcance, impressões, salvamentos, shares e comentários.")

    # Leitura de variáveis de ambiente
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    page_id = os.getenv("INSTAGRAM_PAGE_ID", "")

    if not token or not page_id:
        st.warning("⚠️ Configure `INSTAGRAM_ACCESS_TOKEN` e `INSTAGRAM_PAGE_ID` no arquivo .env.")
    else:
        if st.button("⬇️ Buscar Métricas do Instagram", key="btn_fetch_instagram", width="stretch"):
            with st.spinner("🤖 Buscando métricas..."):
                metrics = fetch_post_metrics(token, page_id)
                if metrics:
                    resumo = importar_metricas(metrics)
                    st.session_state["historico_metricas"] = load_metricas()
                    if resumo["importadas"] > 0:
                        partes = [f"✅ {resumo['importadas']} métrica(s) importada(s) do Instagram"]
                        if resumo["duplicadas"]:
                            partes.append(f"{resumo['duplicadas']} já conhecida(s)")
                        st.success(" · ".join(partes) + ".")
                    else:
                        st.info("ℹ️ Nenhuma nova métrica encontrada.")
                else:
                    st.error(
                        "❌ Não foi possível buscar métricas de alcance. "
                        "Verifique token, page_id e se a conta é Business/Creator."
                    )

    # Histórico de métricas
    if st.session_state.get("historico_metricas"):
        st.markdown("### 📋 Histórico de Métricas")

        # Entradas vazias não alimentam o feedback loop — limpeza explícita
        _vazias = sum(
            1 for m in st.session_state["historico_metricas"]
            if not (str(m.get("titulo", "")).strip() and m.get("alcance", 0) > 0)
        )
        if _vazias and st.button(
            f"🧹 Limpar {_vazias} entrada(s) vazia(s) do histórico",
            help="Remove registros sem título ou com alcance 0 — não alimentam "
                 "o feedback loop e poluem o gráfico.",
        ):
            removidas = limpar_metricas_vazias()
            st.session_state["historico_metricas"] = load_metricas()
            st.success(f"✅ {removidas} entrada(s) removida(s).")

        df = pd.DataFrame(st.session_state["historico_metricas"])
        st.dataframe(df, width="stretch")

        # ── M2: gráfico de KPIs ao longo do tempo ──────────────────────────
        st.markdown("### 📈 KPIs ao Longo do Tempo")
        df_plot = df.copy()
        # ordena por data e usa só colunas de taxa (0–100%)
        for col in ("taxa_salvamentos", "taxa_envios", "taxa_nao_seguidores"):
            if col not in df_plot.columns:
                df_plot[col] = 0.0
        df_plot["data"] = pd.to_datetime(df_plot["data"], errors="coerce")
        df_plot = df_plot.sort_values("data")
        st.line_chart(
            df_plot.set_index("data")[[
                "taxa_salvamentos", "taxa_envios", "taxa_nao_seguidores",
            ]].rename(columns={
                "taxa_salvamentos": "💾 Salvamentos (%)",
                "taxa_envios": "📤 Envios DM (%)",
                "taxa_nao_seguidores": "🆕 Não Seguidores (%)",
            }),
            height=320,
        )
        st.caption("Metas: Salvamentos ≥ 4% · Envios DM ≥ 2,5% · Não seguidores ≥ 20%")

        st.download_button(
            "⬇️ Exportar Métricas (JSON)",
            data=json.dumps(st.session_state["historico_metricas"], ensure_ascii=False, indent=2),
            file_name="metricas_historico.json",
            mime="application/json",
        )