"""
tabs/tab_tendencias.py — Aba de Análise de Tendências.
"""

import json

import streamlit as st

from config import CORES
from gemini import call_gemini_json, invalidate_cache
from persistence import save_geracao
from prompts import PROMPT_TENDENCIAS, TEMPERATURAS
from tabs._ui import api_key_ok, esc


def _normalizar_tendencias(data) -> dict:
    """Converte respostas antigas em lista para o schema da aba de tendências."""
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        if len(data) == 1 and isinstance(data[0], dict):
            secoes = {
                "tendencias_conteudo", "engagement_forensics", "dores_pais",
                "sazonalidade", "tendencias_comportamento", "oportunidades_concorrencia",
            }
            if secoes.intersection(data[0]):
                return data[0]
        itens = [item for item in data if isinstance(item, dict)]
        if itens:
            return {"tendencias_conteudo": itens}
    return {}


def render():
    """Renderiza a aba de Tendências."""
    st.markdown("## 📈 Análise de Tendências do Setor")
    st.markdown("Pesquisa automatizada sobre o que está funcionando no Instagram educacional.")

    col_btn, col_inv = st.columns([1, 1])
    with col_btn:
        gerar_tend = st.button("🔍 Analisar Tendências", type="primary", width="stretch")
    with col_inv:
        if st.button("🔄 Forçar nova análise", width="stretch",
                     help="Ignora o cache e gera uma análise nova"):
            invalidate_cache(PROMPT_TENDENCIAS)
            st.session_state.pop("tendencias", None)
            st.rerun()

    if gerar_tend:
        if not api_key_ok():
            st.warning("⚠️ Configure a chave API Gemini na barra lateral.")
        else:
            with st.spinner("🤖 Pesquisando tendências…"):
                data = call_gemini_json(PROMPT_TENDENCIAS, temperature=TEMPERATURAS["tendencias"])
                data = _normalizar_tendencias(data)
                if data:
                    st.session_state["tendencias"] = data
                    st.session_state["tendencias_texto"] = json.dumps(data, ensure_ascii=False)
                    save_geracao("tendencias", data)
                    st.success("✅ Tendências analisadas e salvas!")

    if st.session_state.get("tendencias"):
        data = _normalizar_tendencias(st.session_state["tendencias"])
        st.session_state["tendencias"] = data

        st.markdown("### 🎬 Tendências de Conteúdo no Instagram")
        for t in data.get("tendencias_conteudo", []):
            pot = t.get("potencial_engajamento", "")
            cor = CORES["secundaria"] if pot == "alto" else CORES["destaque"] if pot == "médio" else CORES["texto_sec"]
            st.markdown(f"""
            <div class="metric-box">
                <strong style="color:{cor};">{esc(t.get('nome',''))}</strong>
                <span style="color:{CORES['texto_sec']}; font-size:0.85em; margin-left:8px;">[{esc(pot)}]</span>
                <br><span style="color:{CORES['texto']}; font-size:0.9em;">{esc(t.get('descricao',''))}</span>
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
                <strong style="color:{CORES['primaria']};">{esc(t.get('tendencia',''))}</strong>
                <br><span style="color:{CORES['texto']}; font-size:0.9em;">{esc(t.get('aplicacao',''))}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### 🏆 Oportunidades vs. Concorrência")
        for o in data.get("oportunidades_concorrencia", []):
            st.success(
                f"**{o.get('oportunidade','')}** → "
                f"Diferencial local: {o.get('diferencial_local','')}"
            )
