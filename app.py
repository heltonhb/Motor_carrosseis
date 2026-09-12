"""
Motor de Carrosséis — Ensina Mais Tatuapé
Gerador inteligente de carrosséis para Instagram com análise de tendências,
ideias estratégicas, prompts para Google Flow, geração de imagens e cronograma.
"""

# ─── Imports (todos no topo) ──────────────────────────────────────────────────
import json
import time
import zipfile
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from config import (
    CORES,
    EIXOS,
    FORMATO,
    KPIS,
    NOTEBOOK_ID_PADRAO,
    NOTEBOOK_TITULO_PADRAO,
    UNIDADE,
)
from gemini import call_gemini, call_gemini_json, extract_json, invalidate_cache
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
    TEMPERATURAS,
    get_prompt_cronograma,
    get_prompt_ideias,
    validate_idea_diversity,
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
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&display=swap" rel="stylesheet">

<style>
    /* ═══ Base ═══ */
    .stApp {{
        background-color: {CORES['app_bg']};
        font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif;
    }}
    .main .block-container {{
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1200px;
    }}

    /* ═══ Tipografia ═══ */
    h1, h2, h3, h4, h5, h6 {{
        color: {CORES['texto']} !important;
        font-family: 'Geist', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        line-height: 1.3;
    }}
    h1 {{ font-size: 1.8rem !important; margin-bottom: 0.5rem !important; }}
    h2 {{ font-size: 1.4rem !important; margin-bottom: 0.4rem !important; }}
    h3 {{ font-size: 1.15rem !important; margin-bottom: 0.3rem !important; }}

    p {{ color: {CORES['texto_sec']}; line-height: 1.6; margin-bottom: 0.5rem; }}

    /* ═══ Tabs — underline limpo ═══ */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background: transparent;
        border-bottom: 1px solid {CORES['borda']};
        padding-bottom: 0;
        margin-bottom: 1.5rem;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        color: {CORES['texto_sec']};
        border-radius: 0;
        padding: 10px 18px;
        font-weight: 500;
        font-size: 0.88em;
        border-bottom: 2px solid transparent;
        transition: all 0.2s cubic-bezier(0.32, 0.72, 0, 1);
        white-space: nowrap;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: {CORES['primaria']};
        background-color: transparent;
    }}
    .stTabs [aria-selected="true"] {{
        color: {CORES['primaria']} !important;
        border-bottom: 2px solid {CORES['primaria']} !important;
        background-color: transparent !important;
        font-weight: 600 !important;
    }}

    /* ═══ Cards — sem sobreposição ═══ */
    .idea-card {{
        background: {CORES['app_card']};
        border: 1px solid {CORES['borda']};
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: {CORES['app_sombra']};
        transition: box-shadow 0.3s cubic-bezier(0.32, 0.72, 0, 1),
                    transform 0.3s cubic-bezier(0.32, 0.72, 0, 1);
        position: relative;
        z-index: 1;
    }}
    .idea-card:hover {{
        box-shadow: {CORES['app_sombra_hover']};
        transform: translateY(-1px);
        z-index: 2;
    }}
    .idea-card h3 {{
        color: {CORES['primaria']} !important;
        margin-top: 0;
        margin-bottom: 8px;
    }}

    /* ═══ Metric box ═══ */
    .metric-box {{
        background: {CORES['app_card']};
        border: 1px solid {CORES['borda']};
        border-left: 3px solid {CORES['primaria']};
        padding: 14px 18px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 10px;
        box-shadow: {CORES['app_sombra']};
        position: relative;
        z-index: 1;
    }}

    /* ═══ Schedule day ═══ */
    .schedule-day {{
        background: {CORES['app_card']};
        border: 1px solid {CORES['borda']};
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
        box-shadow: {CORES['app_sombra']};
    }}

    /* ═══ Timeline ═══ */
    .timeline-item {{
        background: {CORES['app_card']};
        border: 1px solid {CORES['borda']};
        border-left: 3px solid {CORES['primaria']};
        padding: 14px 18px;
        margin-bottom: 10px;
        border-radius: 0 8px 8px 0;
        box-shadow: {CORES['app_sombra']};
        position: relative;
        z-index: 1;
    }}
    .timeline-item:hover {{
        box-shadow: {CORES['app_sombra_hover']};
        z-index: 2;
    }}
    .timeline-item.carrossel {{ border-left-color: #818CF8; }}
    .timeline-item.stories   {{ border-left-color: #A78BFA; }}
    .timeline-item.reel      {{ border-left-color: #F87171; }}

    /* ═══ Flow progress ═══ */
    .flow-step {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        border-radius: 16px;
        font-size: 0.8em;
        font-weight: 500;
        margin: 2px;
        transition: all 0.3s cubic-bezier(0.32, 0.72, 0, 1);
    }}
    .flow-step.done    {{
        background: rgba(52, 211, 153, 0.12);
        color: #34D399;
        border: 1px solid rgba(52, 211, 153, 0.25);
    }}
    .flow-step.current {{
        background: rgba(129, 140, 248, 0.12);
        color: #818CF8;
        border: 1px solid rgba(129, 140, 248, 0.25);
    }}
    .flow-step.pending {{
        background: {CORES['app_card']};
        color: {CORES['texto_sec']};
        border: 1px solid {CORES['borda']};
    }}

    /* ═══ Expander ═══ */
    div[data-testid="stExpander"] {{
        background-color: {CORES['app_card']};
        border: 1px solid {CORES['borda']};
        border-radius: 8px;
        box-shadow: {CORES['app_sombra']};
        margin-bottom: 8px;
    }}

    /* ═══ Sidebar ═══ */
    section[data-testid="stSidebar"] {{
        background-color: {CORES['fundo_sec']};
        border-right: 1px solid {CORES['borda']};
    }}
    section[data-testid="stSidebar"] .stMarkdown p,
    section[data-testid="stSidebar"] .stMarkdown li,
    section[data-testid="stSidebar"] .stMarkdown span {{
        color: {CORES['texto']} !important;
        font-size: 0.85em;
        line-height: 1.5;
    }}

    /* ═══ Botões primários ═══ */
    .stButton > button[kind="primary"],
    div[data-testid="stForm"] button[kind="primary"] {{
        background-color: {CORES['primaria']};
        color: #0A0A0F;
        border: none;
        border-radius: 8px;
        font-weight: 600;
        padding: 8px 20px;
        transition: all 0.2s cubic-bezier(0.32, 0.72, 0, 1);
        box-shadow: 0 2px 8px rgba(108, 140, 255, 0.25);
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: #8AA4FF;
        box-shadow: 0 4px 16px rgba(108, 140, 255, 0.35);
        transform: translateY(-1px);
    }}

    /* ═══ Botões secundários ═══ */
    .stButton > button:not([kind="primary"]) {{
        background-color: {CORES['app_card']};
        color: {CORES['texto']};
        border: 1px solid {CORES['borda']};
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.2s cubic-bezier(0.32, 0.72, 0, 1);
    }}
    .stButton > button:not([kind="primary"]):hover {{
        background-color: {CORES['app_card2']};
        border-color: #3A3A4C;
    }}

    /* ═══ Inputs ═══ */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {{
        border-radius: 8px;
        border: 1px solid {CORES['borda']};
        background-color: {CORES['app_card']};
        color: {CORES['texto']};
        transition: border-color 0.2s cubic-bezier(0.32, 0.72, 0, 1);
    }}
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus {{
        border-color: {CORES['primaria']};
        box-shadow: 0 0 0 2px rgba(108, 140, 255, 0.15);
    }}

    /* ═══ Alerts ═══ */
    .stSuccess {{
        background-color: rgba(52, 211, 153, 0.1) !important;
        border: 1px solid rgba(52, 211, 153, 0.25) !important;
        color: #6EE7B7 !important;
    }}
    .stWarning {{
        background-color: rgba(251, 191, 36, 0.1) !important;
        border: 1px solid rgba(251, 191, 36, 0.25) !important;
        color: #FDE68A !important;
    }}
    .stError {{
        background-color: rgba(248, 113, 113, 0.1) !important;
        border: 1px solid rgba(248, 113, 113, 0.25) !important;
        color: #FCA5A5 !important;
    }}
    .stInfo {{
        background-color: rgba(129, 140, 248, 0.1) !important;
        border: 1px solid rgba(129, 140, 248, 0.25) !important;
        color: #A5B4FC !important;
    }}

    /* ═══ Dividers ═══ */
    hr {{
        border-color: {CORES['borda']} !important;
        margin: 1rem 0;
    }}

    /* ═══ Scrollbar ═══ */
    ::-webkit-scrollbar {{ width: 6px; }}
    ::-webkit-scrollbar-track {{ background: transparent; }}
    ::-webkit-scrollbar-thumb {{ background: #2A2A3C; border-radius: 3px; }}
    ::-webkit-scrollbar-thumb:hover {{ background: #3A3A4C; }}

    /* ═══ Download buttons ═══ */
    .stDownloadButton > button {{
        background-color: {CORES['app_card']} !important;
        color: {CORES['texto']} !important;
        border: 1px solid {CORES['borda']} !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
    }}

    /* ═══ Code blocks ═══ */
    .stCodeBlock {{
        border-radius: 8px;
        border: 1px solid {CORES['borda']};
    }}

    /* ═══ Progress bar ═══ */
    .stProgress > div > div > div {{
        background-color: {CORES['primaria']};
        border-radius: 4px;
    }}

    /* ═══ Multiselect chips ═══ */
    .stMultiSelect [data-baseweb="tag"] {{
        background-color: rgba(129, 140, 248, 0.15) !important;
        border-color: rgba(129, 140, 248, 0.3) !important;
        color: #818CF8 !important;
    }}

    /* ═══ Form submit ═══ */
    .stFormSubmitButton > button {{
        background-color: {CORES['primaria']} !important;
        color: #0A0A0F !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}

    /* ═══ Espaçamento ═══ */
    .stMarkdown > div {{
        margin-bottom: 0.5rem;
    }}
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
    """Renderiza um card de ideia com expander de roteiro e badges estratégicos."""
    eixo = idea.get("eixo", "Didático")
    color = EIXOS.get(eixo, {}).get("cor", CORES["destaque"])
    persona = idea.get("persona_alvo", "")
    tipo_hook = idea.get("tipo_hook", "")
    score = idea.get("score")
    score_just = idea.get("score_justificativa", "")

    badges_html = [
        f'<span style="background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.12); color:{color}; padding:3px 12px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.25); white-space:nowrap;">{eixo}</span>'
    ]
    if persona:
        badges_html.append(
            f'<span style="background:rgba(255,209,102,0.12); color:#FFD166; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(255,209,102,0.25); white-space:nowrap;">🎯 {persona}</span>'
        )
    if tipo_hook:
        badges_html.append(
            f'<span style="background:rgba(52,211,153,0.12); color:#34D399; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(52,211,153,0.25); white-space:nowrap;">⚡ {tipo_hook}</span>'
        )
    if score:
        badges_html.append(
            f'<span style="background:rgba(129,140,248,0.12); color:#818CF8; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(129,140,248,0.25); white-space:nowrap;">⭐ {score}/10 Retenção</span>'
        )

    badges_str = "".join(badges_html)

    score_html = ""
    if score_just:
        score_html = f'<div style="margin-top:10px; padding:6px 12px; background:rgba(255,255,255,0.03); border-left:2px solid {CORES["primaria"]}; font-size:0.78em; color:{CORES["texto_sec"]}; border-radius:0 4px 4px 0;"><strong>Estratégia de Retenção:</strong> {score_just}</div>'

    st.markdown(f"""
    <div class="idea-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
            <h3 style="margin:0; font-size:1.1rem; color:{CORES['primaria']};">{idea.get('titulo','Sem título')}</h3>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">{badges_str}</div>
        </div>
        <p style="color:{CORES['texto_sec']}; margin-bottom:10px; font-size:0.88em; line-height:1.5;">{idea.get('tema','')}</p>
        <div style="display:flex; flex-wrap:wrap; gap:20px;">
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">Público</div>
                <div style="color:{CORES['texto']}; font-size:0.88em;">{idea.get('publico_alvo','')}</div>
            </div>
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">KPI Alvo</div>
                <div style="color:{color}; font-weight:600; font-size:0.88em;">{idea.get('kpi_alvo','')}</div>
            </div>
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">CTA</div>
                <div style="color:{CORES['primaria']}; font-weight:600; font-size:0.88em;">
                    Comente "{idea.get('cta','')}"
                </div>
            </div>
        </div>
        {score_html}
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

    canal_color = "#818CF8" if "Carrossel" in tipo or "Feed" in canal else "#A78BFA" if "Stories" in canal else "#F87171" if "Reel" in tipo else CORES["texto_sec"]

    st.markdown(f"""
    <div class="timeline-item {css_class}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <strong style="color:{CORES['primaria']};">
                    {icon} {day.get('dia','')} — {day.get('data','')}
                </strong>
                <span style="color:{CORES['texto_sec']}; margin-left:8px; font-size:0.85em;">{day.get('horario','')}</span>
            </div>
            <span style="background:rgba({int(canal_color[1:3],16)},{int(canal_color[3:5],16)},{int(canal_color[5:7],16)},0.12); color:{canal_color};
                  padding:2px 10px; border-radius:12px; font-size:0.75em;
                  font-weight:500; border:1px solid rgba({int(canal_color[1:3],16)},{int(canal_color[3:5],16)},{int(canal_color[5:7],16)},0.25); white-space:nowrap;">{canal}</span>
        </div>
        <p style="color:{CORES['texto']}; margin:8px 0 4px 0; font-size:0.88em; line-height:1.5;">
            {day.get('conteudo_resumo','')}
        </p>
        <p style="color:{CORES['texto_sec']}; margin:0; font-size:0.82em;">
            📌 CTA: {day.get('cta','—')}
        </p>
    </div>
    """, unsafe_allow_html=True)


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configurações")

    api_key_input = st.text_input(
        "🔑 Chave API Gemini",
        value=st.session_state.get("gemini_key", ""),
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
# Motor de Carrosséis
### {UNIDADE['nome']}
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
                data = call_gemini_json(PROMPT_TENDENCIAS, temperature=TEMPERATURAS["tendencias"])
                if data:
                    st.session_state["tendencias"] = data
                    st.session_state["tendencias_texto"] = json.dumps(data, ensure_ascii=False)
                    save_geracao("tendencias", data)
                    st.success("✅ Tendências analisadas e salvas!")

    if st.session_state.get("tendencias"):
        data = st.session_state["tendencias"]

        st.markdown("### 🎬 Tendências de Conteúdo no Instagram")
        for t in data.get("tendencias_conteudo", []):
            pot = t.get("potencial_engajamento", "")
            cor = CORES["secundaria"] if pot == "alto" else CORES["destaque"] if pot == "médio" else CORES["texto_sec"]
            st.markdown(f"""
            <div class="metric-box">
                <strong style="color:{cor};">{t.get('nome','')}</strong>
                <span style="color:{CORES['texto_sec']}; font-size:0.85em; margin-left:8px;">[{pot}]</span>
                <br><span style="color:{CORES['texto']}; font-size:0.9em;">{t.get('descricao','')}</span>
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
                <strong style="color:{CORES['primaria']};">{t.get('tendencia','')}</strong>
                <br><span style="color:{CORES['texto']}; font-size:0.9em;">{t.get('aplicacao','')}</span>
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
                    dados = call_gemini_json(get_prompt_ideias(), ctx, temperature=TEMPERATURAS["ideias"])
                    if dados:
                        st.session_state["ideias"] = dados
                        save_geracao("ideias", dados)
                        st.success("✅ Ideias geradas com alto engajamento!")

    st.divider()

    # ── Opção: Usar ideias do NotebookLM diretamente ─────────────────────────
    if "nb_result" in st.session_state and st.session_state.get("nb_result"):
        st.markdown("### 📋 Usar Ideias do NotebookLM")
        st.info("💡 Você tem ideias prontas do NotebookLM. Use-as diretamente sem precisar gerar novas ideias.")
        
        if st.button("📤 Usar Ideias do NotebookLM", type="primary", use_container_width=True):
            # Converter o resultado do NotebookLM para formato de ideias
            nb_result = st.session_state["nb_result"]
            
            import re
            ideias_formatadas = []
            
            # Estratégia 0: Usar extract_json direto
            data = extract_json(nb_result)
            if data and "ideias" in data:
                ideias_formatadas = data["ideias"]
            
            # Estratégia 1: Extrair JSON do bloco de código ```json ... ```
            if not ideias_formatadas:
                json_match = re.search(r'```json\s*(\{.*?\})\s*```', nb_result, re.DOTALL)
                if json_match:
                    try:
                        data = json.loads(json_match.group(1))
                        if "ideias" in data:
                            ideias_formatadas = data["ideias"]
                    except json.JSONDecodeError:
                        pass
            
            # Estratégia 3: Extrair de Markdown com ## Ideia ou ### Ideia ou 1. Ideia
            if not ideias_formatadas:
                # Tenta vários padrões de divisão de tópicos
                blocos = []
                for pat in [
                    r"(?:##|###)?\s*Ideia\s*\d*[:\-]\s*(.+?)(?=(?:##|###)?\s*Ideia\s*\d*[:\-]|$)",
                    r"(\d+\.\s*\*\*[^*]+\*\*.*?)(?=\n\d+\.\s*\*\*|$)",
                    r"(###\s+[^\n]+.*?)(?=###\s+|$)",
                ]:
                    matches = re.findall(pat, nb_result, re.DOTALL | re.IGNORECASE)
                    if len(matches) >= 2:
                        blocos = matches
                        break
                
                if blocos:
                    for i, b_text in enumerate(blocos):
                        # Tenta achar título
                        t_match = re.search(r"(?:\*\*Título:?\*\*|Título:?)\s*(.+)", b_text, re.IGNORECASE)
                        if not t_match:
                            t_match = re.search(r"^\s*(?:#+\s*|\d+\.\s*)?\*?\*?([^\n*]+)\*?\*?", b_text)
                        
                        titulo = t_match.group(1).strip() if t_match else f"Ideia {i+1}"
                        titulo = re.sub(r"^Ideia\s*\d*[:\-]\s*", "", titulo, flags=re.IGNORECASE).strip()
                        
                        # Eixo
                        e_match = re.search(r"(?:\*\*Eixo:?\*\*|Eixo:?)\s*(Didático|Comportamental|Diagnóstico)", b_text, re.IGNORECASE)
                        eixo = e_match.group(1).capitalize() if e_match else ("Didático" if i % 3 == 0 else "Comportamental" if i % 3 == 1 else "Diagnóstico")
                        
                        # Tema
                        tema_match = re.search(r"(?:\*\*Tema:?\*\*|Tema:?)\s*(.+)", b_text, re.IGNORECASE)
                        tema = tema_match.group(1).strip() if tema_match else titulo
                        
                        # CTA
                        cta_match = re.search(r"(?:\*\*CTA:?\*\*|CTA:?)\s*`?([A-Z_0-9]+)`?", b_text, re.IGNORECASE)
                        cta = cta_match.group(1).strip() if cta_match else "DESAFIO"
                        
                        # Slides sugeridos
                        slides_sugeridos = []
                        slides_matches = re.findall(r"(?:Slide\s*\d*|Slide\s*\d*[:\-]|(?:\d+\.))\s*\*\*([^*]+)\*\*:?\s*(.+)", b_text, re.IGNORECASE)
                        if slides_matches:
                            slides_sugeridos = [{"slide": s_idx + 1, "tipo": s_tipo.strip(), "texto": s_txt.strip()} for s_idx, (s_tipo, s_txt) in enumerate(slides_matches[:8])]
                        else:
                            slides_sugeridos = [
                                {"slide": 1, "tipo": "Capa", "texto": titulo},
                                {"slide": 2, "tipo": "Problema", "texto": "A dificuldade comum que muitas famílias enfrentam no dia a dia escolar."},
                                {"slide": 3, "tipo": "Desenvolvimento", "texto": "A abordagem prática para resolver a questão com segurança."},
                                {"slide": 4, "tipo": "Dica prática", "texto": "Passo a passo testado com suporte pedagógico personalizado."},
                                {"slide": 5, "tipo": "Exemplo", "texto": "Caso real de superação e ganho de autonomia do aluno."},
                                {"slide": 6, "tipo": "Benefício", "texto": "Recuperação da autoestima e melhora nas avaliações."},
                                {"slide": 7, "tipo": "Método", "texto": "Ensina Mais Tatuapé: apoio focado na necessidade de cada estudante."},
                                {"slide": 8, "tipo": "CTA", "texto": f"Comente {cta} ou fale no WhatsApp (11) 94475-0009 para agendar uma avaliação gratuita."},
                            ]
                        
                        ideias_formatadas.append({
                            "titulo": titulo,
                            "eixo": eixo,
                            "tema": tema,
                            "publico_alvo": "Pais de classes A/B do Tatuapé",
                            "palavras_chave_seo": ["apoio escolar Tatuapé", "reforço escolar Tatuapé"],
                            "cta": cta,
                            "slides_sugeridos": slides_sugeridos,
                            "kpi_alvo": "Salvamentos/Envios/Leads",
                            "justificativa": "Baseado nas fontes do NotebookLM da unidade",
                            "fonte_notebook": "Estratégia Ensina Mais Tatuapé",
                        })

            # Estratégia 4: Se o NotebookLM retornou texto corrido com ideias, monta 6 ideias dividindo em tópicos
            if not ideias_formatadas and len(nb_result.strip()) > 100:
                linhas = [l.strip() for l in nb_result.split("\n") if l.strip() and not l.startswith("#")]
                paragrafos = [p for p in nb_result.split("\n\n") if len(p.strip()) > 30]
                fonte_base = paragrafos if len(paragrafos) >= 3 else linhas
                
                for idx, bloco in enumerate(fonte_base[:6]):
                    resumo = bloco[:80].strip().rstrip(".")
                    ideias_formatadas.append({
                        "titulo": resumo,
                        "eixo": "Didático" if idx % 3 == 0 else "Comportamental" if idx % 3 == 1 else "Diagnóstico",
                        "tema": resumo,
                        "publico_alvo": "Pais de classes A/B do Tatuapé",
                        "palavras_chave_seo": ["apoio escolar Tatuapé", "reforço escolar Tatuapé"],
                        "cta": "DESAFIO" if idx % 2 == 0 else "DIAGNOSTICO",
                        "slides_sugeridos": [
                            {"slide": 1, "tipo": "Capa", "texto": resumo},
                            {"slide": 2, "tipo": "Contexto", "texto": bloco[:180]},
                            {"slide": 3, "tipo": "Solução", "texto": "Acompanhamento focado nas disciplinas de base."},
                            {"slide": 4, "tipo": "CTA", "texto": "Fale com a equipe pedagógica no Tatuapé."},
                        ],
                        "kpi_alvo": "Salvamentos/Envios/Leads",
                        "justificativa": "Extraído diretamente da análise do NotebookLM",
                        "fonte_notebook": "Estratégia Ensina Mais Tatuapé",
                    })

            # Garantir campos padrão em todas
            for ideia in ideias_formatadas:
                for campo, default in [
                    ("palavras_chave_seo", ["apoio escolar Tatuapé"]),
                    ("kpi_alvo", "Salvamentos/Envios/Leads"),
                    ("publico_alvo", "Pais de classes A/B do Tatuapé"),
                    ("slides_sugeridos", [{"slide": 1, "tipo": "Capa", "texto": ideia.get("titulo", "")}]),
                ]:
                    if not ideia.get(campo):
                        ideia[campo] = default

            if ideias_formatadas:
                st.session_state["ideias"] = {"ideias": ideias_formatadas}
                st.session_state["ideias_selecionadas"] = ideias_formatadas
                save_geracao("ideias", {"ideias": ideias_formatadas})
                st.success(f"✅ {len(ideias_formatadas)} ideias do NotebookLM carregadas com sucesso!")
                st.rerun()
            else:
                st.warning("⚠️ Não foi possível identificar ideias no texto do notebook.")
        
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
                with st.spinner("🤖 Gerando 6 ideias estratégicas de alta retenção…"):
                    dados = call_gemini_json(get_prompt_ideias(), f"Tendências:\n{ctx}", temperature=TEMPERATURAS["ideias"])
                    if dados:
                        st.session_state["ideias"] = dados
                        save_geracao("ideias", dados)
                        st.success("✅ 6 ideias geradas com alta retenção e diversidade de ganchos!")

    if st.session_state.get("ideias"):
        dados_ideias = st.session_state["ideias"]
        ideias = dados_ideias.get("ideias", [])

        # Meta-análise estratégica do lote se fornecida
        meta_analise = dados_ideias.get("meta_analise")
        if meta_analise:
            st.info(f"🧭 **Visão Geral Estratégica:** {meta_analise}")

        # Validador de diversidade de ganchos e personas
        warnings_diversidade = validate_idea_diversity(ideias)
        if warnings_diversidade:
            with st.expander("⚠️ Alertas de Qualidade & Diversidade do Lote", expanded=False):
                for w in warnings_diversidade:
                    st.caption(w)

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
                    dados = call_gemini_json(PROMPT_PROMPTS_IMAGEM, ctx, temperature=TEMPERATURAS["prompts_imagem"])
                    if dados:
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
                            <div style="width:52px;height:52px;background:{cor};
                                 border-radius:8px;margin:0 auto 4px;
                                 border:1px solid {CORES['borda']};
                                 box-shadow:{CORES['app_sombra']};"></div>
                            <span style="color:{CORES['texto_sec']};font-size:0.72em;">{nome}<br>{cor}</span>
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
                    dados = call_gemini_json(PROMPT_LEGENDAS, ctx, temperature=TEMPERATURAS["legendas"])
                    if dados:
                        st.session_state["legendas"] = dados
                        save_geracao("legendas", dados)
                        st.success("✅ 3 legendas geradas!")

        if st.session_state.get("legendas"):
            legendas_data = st.session_state["legendas"]
            opcao_icons = {1: "🔴", 2: "🟡", 3: "🟢"}

            for leg in legendas_data.get("legendas", []):
                op = leg.get("opcao", 1)
                estilo = leg.get("estilo", "")
                tecnica = leg.get("tecnica", "")
                titulo_exp = f"{opcao_icons.get(op,'•')} Opção {op} — {estilo}"
                if tecnica:
                    titulo_exp += f" [{tecnica}]"
                legenda_completa = leg.get("legenda_completa", "")
                char_count = leg.get("char_count", 0)

                with st.expander(
                    titulo_exp,
                    expanded=(op == 1),
                ):
                    if leg.get("por_que_funciona"):
                        st.info(f"🧠 **Estratégia de Conversão:** {leg['por_que_funciona']}")

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
                        dados = call_gemini_json(PROMPT_PROMPTS_IMAGEM, ctx, temperature=TEMPERATURAS["prompts_imagem"])
                        if dados:
                            results[f"prompts_{idx}"] = {"titulo": titulo, "prompts": dados}

                    if fazer_slides:
                        tkey = eixo_para_template(ideia.get("eixo", "Didático"))
                        imgs = generate_all_slides(tkey, ideia.get("slides_sugeridos", []))
                        results[f"slides_{idx}"] = {"titulo": titulo, "images": imgs}

                    step += 1
                    progress_bar.progress(step / total_steps)

                if fazer_cronograma:
                    status_msg.text("📅 Gerando cronograma…")
                    ctx = f"Ideias:\n{json.dumps(ideias_sel, ensure_ascii=False)}"
                    cron_data = call_gemini_json(get_prompt_cronograma(), ctx, temperature=TEMPERATURAS["cronograma"])
                    if cron_data:
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

    # ── Helper: formata uma ideia (schema único para todas as origens) ──────
    def _format_ideia(ideia: dict) -> dict:
        """Normaliza uma ideia para o schema único compartilhado entre abas."""
        return {
            "titulo": ideia.get("titulo", ""),
            "eixo": ideia.get("eixo", "Didático"),
            "persona_alvo": ideia.get("persona_alvo", ""),
            "tipo_hook": ideia.get("tipo_hook", ""),
            "tema": ideia.get("tema", ""),
            "publico_alvo": ideia.get("publico_alvo", "Pais de classes A/B do Tatuapé"),
            "palavras_chave_seo": ideia.get("palavras_chave_seo", ["apoio escolar Tatuapé", "reforço escolar Tatuapé"]),
            "cta": ideia.get("cta", "DESAFIO"),
            "slides_sugeridos": ideia.get("slides_sugeridos", []),
            "kpi_alvo": ideia.get("kpi_alvo", ""),
            "justificativa": ideia.get("justificativa", ideia.get("fonte_notebook", "")),
            "fonte_notebook": ideia.get("fonte_notebook", ""),
            "score": ideia.get("score", 0),
            "score_justificativa": ideia.get("score_justificativa", ""),
        }

    # Verificar disponibilidade do CLI e autenticação
    if not nlm.is_nlm_available():
        st.error(
            "❌ CLI `notebooklm` não encontrado no sistema. "
            "Instale-o ou adicione-o ao PATH para usar esta aba. "
            "As outras abas do app funcionam normalmente via Gemini."
        )
        authenticated = False
    else:
        notebooks = []
        authenticated, auth_msg = nlm.check_auth()
        if authenticated:
            # Log exceções reais se a listagem falhar (diagnóstico)
            try:
                notebooks = nlm.list_notebooks()
            except Exception as exc:
                st.exception(exc)
                notebooks = []
        else:
            st.error(f"❌ NotebookLM não autenticado ({auth_msg}). Execute: `notebooklm login`")

    if authenticated:
        # ── Seletor de notebook (usa a lista REAL, não o ID fixo) ──────────
        notebook_options = {}
        for nb in notebooks:
            nb_id = nb.get("id") or nb.get("notebook_id")
            nb_title = nb.get("title") or nb.get("name") or nb_id
            if nb_id:
                notebook_options[str(nb_id)] = nb_title

        if notebook_options:
            # Garante que o notebook padrão apareça na lista mesmo se o CLI
            # retornar um schema diferente do esperado.
            if NOTEBOOK_ID_PADRAO not in notebook_options:
                notebook_options[NOTEBOOK_ID_PADRAO] = NOTEBOOK_TITULO_PADRAO
            selected_nb_id = st.selectbox(
                "📚 Notebook de origem:",
                options=list(notebook_options.keys()),
                format_func=lambda x: notebook_options[x],
                index=list(notebook_options.keys()).index(NOTEBOOK_ID_PADRAO)
                if NOTEBOOK_ID_PADRAO in notebook_options
                else 0,
            )
            notebook_titulo = notebook_options[selected_nb_id]
        else:
            # Fallback: nenhum notebook listado (pode ser schema inesperado).
            selected_nb_id = NOTEBOOK_ID_PADRAO
            notebook_titulo = NOTEBOOK_TITULO_PADRAO
            st.warning(
                "⚠️ Nenhum notebook foi listado. Usando o notebook padrão configurado. "
                "Verifique se há notebooks disponíveis na sua conta."
            )

        # Sidebar com info do notebook
        with st.sidebar:
            st.markdown("---")
            st.markdown("## 🔬 NotebookLM")
            st.markdown(f"**Notebook ativo:**")
            st.info(f"📚 {notebook_titulo}")
            st.caption(f"ID: {selected_nb_id[:12]}...")

        # ══════════════════════════════════════════════════════════════════════
        # PIPELINE AUTOMÁTICO: NLM → GEMINI (1 CLIQUE)
        # ══════════════════════════════════════════════════════════════════════
        st.markdown("### 🚀 Pipeline Automático")
        st.markdown(
            "Executa todo o fluxo de uma vez: **NotebookLM pesquisa** → "
            "**Gemini estrutura** → Tendências + Ideias + Prompts + Legendas + Cronograma"
        )

        pip_col1, pip_col2, pip_col3 = st.columns(3)
        with pip_col1:
            pip_prompts = st.checkbox("🎨 Gerar Prompts de Imagem", value=True, key="pip_prompts")
        with pip_col2:
            pip_legendas = st.checkbox("📝 Gerar Legendas", value=True, key="pip_legendas")
        with pip_col3:
            pip_cronograma = st.checkbox("📅 Gerar Cronograma", value=True, key="pip_cron")

        if st.button("🚀 Executar Pipeline Completo", type="primary", use_container_width=True, key="btn_pipeline"):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini na barra lateral.")
            else:
                # Calcular total de etapas para progress bar
                total_steps = 2  # trends + ideas (sempre)
                if pip_prompts:
                    total_steps += 1
                if pip_legendas:
                    total_steps += 1
                if pip_cronograma:
                    total_steps += 1

                progress = st.progress(0)
                status = st.empty()
                step = 0
                pipeline_ok = True

                # ── Etapa 1: Pesquisa no NotebookLM ──────────────────────────
                status.info("📚 **[1/{0}]** Pesquisando tendências no NotebookLM…".format(total_steps))
                nlm_context = ""
                try:
                    nlm_trends = nlm.get_trends(selected_nb_id)
                    nlm_competitor = nlm.get_competitor_analysis(selected_nb_id)
                    nlm_context_parts = []
                    if nlm_trends:
                        nlm_context_parts.append(f"=== TENDÊNCIAS (fonte: NotebookLM) ===\n{nlm_trends}")
                    if nlm_competitor:
                        nlm_context_parts.append(f"=== CONCORRÊNCIA (fonte: NotebookLM) ===\n{nlm_competitor}")
                    nlm_context = "\n\n".join(nlm_context_parts)
                except Exception as e:
                    st.warning(f"⚠️ NotebookLM indisponível ({str(e)[:80]}). Continuando com Gemini…")

                # Usar Gemini para estruturar as tendências em JSON
                if nlm_context:
                    trends_data = call_gemini_json(
                        PROMPT_TENDENCIAS,
                        f"Contexto pesquisado em fontes reais (NotebookLM):\n{nlm_context}",
                        temperature=TEMPERATURAS["tendencias"],
                    )
                else:
                    trends_data = call_gemini_json(PROMPT_TENDENCIAS, temperature=TEMPERATURAS["tendencias"])

                if trends_data:
                    st.session_state["tendencias"] = trends_data
                    st.session_state["tendencias_texto"] = json.dumps(trends_data, ensure_ascii=False)
                    save_geracao("tendencias", trends_data)
                else:
                    pipeline_ok = False

                step += 1
                progress.progress(step / total_steps)

                # ── Etapa 2: Gerar Ideias via Gemini (com contexto NLM) ──────
                if pipeline_ok:
                    status.info("💡 **[{0}/{1}]** Gerando 6 ideias estratégicas…".format(step + 1, total_steps))
                    ideas_context = f"Tendências:\n{json.dumps(trends_data, ensure_ascii=False)}"
                    if nlm_context:
                        ideas_context += f"\n\nPesquisa NotebookLM:\n{nlm_context[:3000]}"

                    ideas_data = call_gemini_json(get_prompt_ideias(), ideas_context, temperature=TEMPERATURAS["ideias"])

                    if ideas_data and "ideias" in ideas_data:
                        st.session_state["ideias"] = ideas_data
                        save_geracao("ideias", ideas_data)

                        # Auto-selecionar todas as ideias para o pipeline
                        ideias_formatadas = [_format_ideia(i) for i in ideas_data["ideias"]]
                        st.session_state["ideias_selecionadas"] = ideias_formatadas
                    else:
                        pipeline_ok = False

                step += 1
                progress.progress(step / total_steps)

                # ── Etapa 3: Prompts de Imagem (opcional) ────────────────────
                if pipeline_ok and pip_prompts:
                    status.info("🎨 **[{0}/{1}]** Gerando prompts visuais para {2} ideias…".format(
                        step + 1, total_steps, len(ideias_formatadas)
                    ))
                    # Gerar prompts para a primeira ideia selecionada
                    first_idea = ideias_formatadas[0]
                    ctx = (
                        f"Carrossel:\n{json.dumps(first_idea, ensure_ascii=False)}\n\n"
                        f"Slides:\n{json.dumps(first_idea.get('slides_sugeridos', []), ensure_ascii=False)}"
                    )
                    prompts_data = call_gemini_json(PROMPT_PROMPTS_IMAGEM, ctx, temperature=TEMPERATURAS["prompts_imagem"])
                    if prompts_data:
                        st.session_state["prompts"] = prompts_data
                        save_geracao("prompts", prompts_data)

                    step += 1
                    progress.progress(step / total_steps)

                # ── Etapa 4: Legendas (opcional) ─────────────────────────────
                if pipeline_ok and pip_legendas:
                    status.info("📝 **[{0}/{1}]** Gerando legendas Instagram…".format(step + 1, total_steps))
                    first_idea = ideias_formatadas[0]
                    ctx = f"Carrossel:\n{json.dumps(first_idea, ensure_ascii=False)}"
                    legendas_data = call_gemini_json(PROMPT_LEGENDAS, ctx, temperature=TEMPERATURAS["legendas"])
                    if legendas_data:
                        st.session_state["legendas"] = legendas_data
                        save_geracao("legendas", legendas_data)

                    step += 1
                    progress.progress(step / total_steps)

                # ── Etapa 5: Cronograma (opcional) ───────────────────────────
                if pipeline_ok and pip_cronograma:
                    status.info("📅 **[{0}/{1}]** Montando cronograma de 2 semanas…".format(step + 1, total_steps))
                    ctx = f"Ideias selecionadas:\n{json.dumps(ideias_formatadas, ensure_ascii=False)}"
                    cron_data = call_gemini_json(get_prompt_cronograma(), ctx, temperature=TEMPERATURAS["cronograma"])
                    if cron_data:
                        st.session_state["cronograma"] = cron_data
                        save_geracao("cronograma", cron_data)

                    step += 1
                    progress.progress(step / total_steps)

                # ── Resultado Final ──────────────────────────────────────────
                progress.progress(1.0)
                if pipeline_ok:
                    status.empty()
                    st.success("✅ **Pipeline concluído!** Todas as tabs foram populadas:")
                    result_cols = st.columns(5)
                    tabs_populated = ["📈 Tendências", "💡 Ideias"]
                    if pip_prompts:
                        tabs_populated.append("🎨 Prompts")
                    if pip_legendas:
                        tabs_populated.append("📝 Legendas")
                    if pip_cronograma:
                        tabs_populated.append("📅 Cronograma")
                    for i, tab_name in enumerate(tabs_populated):
                        with result_cols[i % 5]:
                            st.info(f"✅ {tab_name}")

                    n_ideias = len(ideias_formatadas)
                    st.markdown(
                        f"**{n_ideias} ideias** geradas e selecionadas. "
                        f"Navegue pelas tabs acima para ver os detalhes."
                    )
                    if nlm_context:
                        with st.expander("📚 Contexto usado do NotebookLM"):
                            st.markdown(nlm_context[:2000])
                            if len(nlm_context) > 2000:
                                st.caption(f"… {len(nlm_context) - 2000} caracteres adicionais omitidos")
                else:
                    status.empty()
                    st.error("❌ Pipeline interrompido. Verifique a chave API e tente novamente.")

        st.divider()

        # ══════════════════════════════════════════════════════════════════════
        # CONSULTA MANUAL (funcionalidade original preservada)
        # ══════════════════════════════════════════════════════════════════════
        st.markdown("### 🔍 Consulta Manual")
        
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

        # Botão de busca com streaming
        if st.button("🔍 Buscar no NotebookLM", type="primary", use_container_width=True):
            if not selected_nb_id:
                st.warning("⚠️ Selecione um notebook primeiro.")
            else:
                response_container = st.empty()
                streaming_chunks = []
                _last_render = [0.0]  # throttle: renderiza no máx 3x/seg

                def on_chunk(chunk):
                    """Callback throttled: acumula chunks e re-renderiza sob demanda."""
                    streaming_chunks.append(chunk)
                    now = time.time()
                    if now - _last_render[0] >= 0.33:  # ~3 renders/segundo
                        _last_render[0] = now
                        partial = "".join(streaming_chunks)
                        response_container.markdown(partial + " ▌")

                with st.status("🔍 Consultando NotebookLM…", expanded=True) as status_ctx:
                    # Chamar a variante streaming de cada tipo com fallback sync
                    if consulta_tipo == "📈 Tendências do Setor":
                        result = nlm.get_trends_streaming(selected_nb_id, callback=on_chunk)
                        if not result:
                            result = nlm.get_trends(selected_nb_id)
                    elif consulta_tipo == "💡 Ideias de Carrossel":
                        result = nlm.generate_ideas_streaming(selected_nb_id, callback=on_chunk)
                        if not result:
                            result = nlm.generate_ideas(selected_nb_id)
                    elif consulta_tipo == "🏢 Análise de Concorrência":
                        result = nlm.get_competitor_analysis_streaming(selected_nb_id, callback=on_chunk)
                        if not result:
                            result = nlm.get_competitor_analysis(selected_nb_id)
                    else:
                        pergunta_texto = st.session_state.get("nb_pergunta_livre", "").strip()
                        if not pergunta_texto:
                            st.warning("⚠️ Digite uma pergunta para consultar o notebook.")
                            result = None
                        else:
                            result = nlm.search_in_notebook_streaming(
                                selected_nb_id, pergunta_texto, callback=on_chunk
                            )
                            if not result:
                                result = nlm.search_in_notebook(selected_nb_id, pergunta_texto)

                    # ── Fallback Gemini quando NLM falha (opcional, só se há chave) ──
                    if not result and _api_key_ok():
                        tb = {
                            "📈 Tendências do Setor": PROMPT_TENDENCIAS,
                            "💡 Ideias de Carrossel": get_prompt_ideias(),
                        }
                        pergunta_texto = st.session_state.get("nb_pergunta_livre", "").strip()
                        if consulta_tipo in tb:
                            status_ctx.write("⚠️ NotebookLM indisponível. Usando Gemini como fallback…")
                            result = call_gemini(tb[consulta_tipo])
                        elif pergunta_texto:
                            status_ctx.write("⚠️ NotebookLM indisponível. Usando Gemini como fallback…")
                            result = call_gemini(pergunta_texto)

                    if result:
                        status_ctx.update(label="✅ Consulta concluída", state="complete")

                response_container.empty()

                if result:
                    st.session_state["nb_result"] = result
                    
                    # Se foram geradas ideias, popula automaticamente a aba Ideias e session_state
                    data_parsed = extract_json(result)
                    if not data_parsed:
                        try:
                            data_parsed = json.loads(result)
                        except Exception:
                            data_parsed = {}
                    
                    if isinstance(data_parsed, dict) and "ideias" in data_parsed:
                        ideias_list = data_parsed["ideias"]
                        st.session_state["ideias"] = {"ideias": ideias_list}
                        st.session_state["ideias_selecionadas"] = ideias_list
                        save_geracao("ideias", {"ideias": ideias_list})
                        st.success(f"✅ Consulta concluída! {len(ideias_list)} ideias foram enviadas para a aba '💡 Ideias'.")
                    elif isinstance(data_parsed, dict) and "tendencias" in data_parsed:
                        st.session_state["tendencias"] = data_parsed
                        st.session_state["tendencias_texto"] = json.dumps(data_parsed, ensure_ascii=False)
                        save_geracao("tendencias", data_parsed)
                        st.success("✅ Consulta concluída! Dados enviados para a aba '📈 Tendências'.")
                    else:
                        st.success("✅ Consulta concluída!")
                elif consulta_tipo != "❓ Pergunta Livre" or st.session_state.get("nb_pergunta_livre", "").strip():
                    st.error("❌ Não foi possível obter resposta do notebook.")
                    st.info("💡 Dica: Verifique se a sua sessão do NotebookLM precisa ser renovada executando `notebooklm login` no terminal, ou tente a opção '📈 Tendências do Setor'.")

        # Exibir resultado
        if "nb_result" in st.session_state and st.session_state["nb_result"]:
            result = st.session_state["nb_result"]
            
            # Tentar parsear como JSON estruturado usando extract_json
            data = extract_json(result)
            
            # Se não conseguiu parsear como JSON direto, tenta json.loads
            if not data:
                try:
                    data = json.loads(result)
                except Exception:
                    data = {}

            # Se temos dados estruturados, renderiza os cards
            if data:
                # Exibir tendências
                if "tendencias" in data:
                    st.markdown("### 📈 Tendências Identificadas")
                    for t in data["tendencias"]:
                        potencial = t.get("potencial", "médio")
                        cor = CORES["secundaria"] if potencial == "alto" else CORES["destaque"] if potencial == "médio" else CORES["texto_sec"]
                        st.markdown(f"""
                        <div class="metric-box">
                            <strong style="color:{cor};">{t.get('nome', '')}</strong>
                            <span style="color:{CORES['texto_sec']}; font-size:0.82em;">[{potencial}]</span>
                            <br><span style="color:{CORES['texto']}; font-size:0.88em;">{t.get('descricao', '')}</span>
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
                    
                    # Botões de ação para enviar ideias
                    col_act1, col_act2 = st.columns(2)
                    with col_act1:
                        if st.button("📥 Carregar na aba 💡 Ideias", type="primary", use_container_width=True):
                            ideias_formatadas = [_format_ideia(i) for i in data["ideias"]]
                            st.session_state["ideias"] = {"ideias": ideias_formatadas}
                            st.session_state["ideias_selecionadas"] = ideias_formatadas
                            save_geracao("ideias", {"ideias": ideias_formatadas})
                            st.success(f"✅ {len(ideias_formatadas)} ideias salvas! Abra a aba '💡 Ideias' para visualizar.")
                    
                    with col_act2:
                        if st.button("🎨 Enviar para Gerador de Prompts", use_container_width=True):
                            ideias_formatadas = [_format_ideia(i) for i in data["ideias"]]
                            st.session_state["ideias_selecionadas"] = ideias_formatadas
                            st.session_state["nb_ideias_para_prompts"] = True
                            st.success(f"✅ {len(ideias_formatadas)} ideias enviadas para Prompts!")
                    
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
                                ideia_formatada = _format_ideia(ideia)
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
            else:
                # Exibir como texto Markdown se não for JSON
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
