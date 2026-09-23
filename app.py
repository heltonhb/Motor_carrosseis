"""
Motor de Carrosséis — Ensina Mais Tatuapé
Gerador inteligente de carrosséis para Instagram com análise de tendências,
ideias estratégicas, prompts para Google Flow, geração de imagens e cronograma.
"""

# ─── Imports (todos no topo) ──────────────────────────────────────────────────
import html
import json
import os
import re
import time
import zipfile
from datetime import datetime
from io import BytesIO

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

import notebooklm_client as nlm
from batch_engine import (
    gerar_cronograma,
    gerar_legendas_ideia,
    gerar_prompts_ideia,
    processar_lote,
)
from config import (
    CORES,
    EIXOS,
    EMPTY_STATES,
    FORMATO,
    HERO,
    KPIS,
    NOTEBOOK_ID_PADRAO,
    NOTEBOOK_TITULO_PADRAO,
    UNIDADE,
)
from gemini import call_gemini, call_gemini_json, invalidate_cache
from ics_export import cronograma_para_ics
from image_utils import add_text_overlay, create_slide_from_template
from instagram_service import fetch_post_metrics
from parser_nlm import extract_json
from persistence import (
    importar_metricas,
    limpar_metricas_vazias,
    load_ideias_estado,
    load_metricas,
    save_geracao,
    save_metrica,
    sync_session_from_disk,
)
from prompts import (
    PROMPT_TENDENCIAS,
    PROMPT_VIDEO_CURTO,
    TEMPERATURAS,
    cor_eh_valida,
    get_prompt_cronograma,
    get_prompt_ideias,
    validate_idea_diversity,
    validate_prompts,
)
from templates import TEMPLATES, MetricaPost, eixo_para_template

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

import os
from dotenv import load_dotenv
load_dotenv()
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

    /* ═══ Hero header ═══ */
    .hero {{
        position: relative;
        background: {CORES['gradiente_hero']};
        border: 1px solid {CORES['borda']};
        border-radius: {CORES['raio_card']};
        padding: 28px 32px;
        margin-bottom: 18px;
        overflow: hidden;
    }}
    .hero::after {{
        content: "";
        position: absolute;
        top: -60px; right: -40px;
        width: 240px; height: 240px;
        background: {CORES['glow_primaria']};
        filter: blur(60px);
        border-radius: 50%;
        pointer-events: none;
    }}
    .hero-inner {{ position: relative; z-index: 1; }}
    .hero-badge {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 14px;
        border-radius: 999px;
        background: rgba(108, 140, 255, 0.14);
        color: {CORES['primaria']};
        border: 1px solid rgba(108, 140, 255, 0.30);
        font-size: 0.78em;
        font-weight: 600;
        letter-spacing: 0.01em;
        margin-bottom: 12px;
    }}
    .hero-title {{
        font-size: 2.1rem !important;
        font-weight: 800 !important;
        letter-spacing: -0.03em !important;
        line-height: 1.15 !important;
        margin: 0 0 6px 0 !important;
        background: {CORES['gradiente_texto']};
        -webkit-background-clip: text;
        background-clip: text;
        -webkit-text-fill-color: transparent;
        color: transparent !important;
    }}
    .hero-subtitle {{
        color: {CORES['texto_sec']} !important;
        font-size: 0.98em;
        margin: 0;
        line-height: 1.5;
    }}

    /* ═══ Empty state ═══ */
    .empty-state {{
        text-align: center;
        padding: 40px 24px;
        background: {CORES['app_card']};
        border: 1px dashed {CORES['borda']};
        border-radius: {CORES['raio_card']};
        margin: 12px 0;
    }}
    .empty-icon {{
        font-size: 2.2rem;
        margin-bottom: 10px;
        animation: float 3s ease-in-out infinite;
    }}
    .empty-title {{ font-size: 1.05rem; font-weight: 700; margin-bottom: 4px; }}
    .empty-desc {{ font-size: 0.88em; line-height: 1.5; max-width: 460px; margin: 0 auto; }}
    @keyframes float {{
        0%, 100% {{ transform: translateY(0); }}
        50% {{ transform: translateY(-6px); }}
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
        border-radius: {CORES['raio_card']};
        padding: 20px 24px;
        margin-bottom: 16px;
        box-shadow: {CORES['app_sombra']};
        transition: box-shadow 0.3s cubic-bezier(0.32, 0.72, 0, 1),
                    transform 0.3s cubic-bezier(0.32, 0.72, 0, 1),
                    border-color 0.3s cubic-bezier(0.32, 0.72, 0, 1);
        position: relative;
        z-index: 1;
    }}
    .idea-card:hover {{
        box-shadow: {CORES['app_sombra_hover']};
        transform: translateY(-1px);
        border-color: rgba(108, 140, 255, 0.28);
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
        background-color: #1A1A2E !important;
        color: #E8E8ED !important;
        border: 1px solid {CORES['primaria']} !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 8px 20px !important;
        transition: all 0.2s cubic-bezier(0.32, 0.72, 0, 1) !important;
        box-shadow: 0 2px 8px rgba(108, 140, 255, 0.15) !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: #242440 !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 18px rgba(108, 140, 255, 0.25) !important;
        transform: translateY(-1px);
    }}
    .stButton > button[kind="primary"]:active {{
        transform: translateY(0) !important;
        box-shadow: 0 2px 8px rgba(108, 140, 255, 0.15) !important;
    }}

    /* ═══ Botões secundários ═══ */
    .stButton > button:not([kind="primary"]),
    .stDownloadButton > button {{
        background-color: #141420 !important;
        color: #E8E8ED !important;
        border: 1px solid #2A2A3C !important;
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s cubic-bezier(0.32, 0.72, 0, 1) !important;
    }}
    .stButton > button:not([kind="primary"]):hover,
    .stDownloadButton > button:hover {{
        background-color: #1A1A2E !important;
        border-color: #3A3A4C !important;
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
        background-color: #1A1A2E !important;
        color: #E8E8ED !important;
        border: 1px solid {CORES['primaria']} !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
    }}

    /* ═══ Espaçamento ═══ */
    .stMarkdown > div {{
        margin-bottom: 0.5rem;
    }}
</style>
""", unsafe_allow_html=True)

# ─── Forçar cores nos botões via JS (override styled-components) ─────────────
st.html("""
<script>
(function(){
    function fixButtons(){
        // Primary buttons: dark bg, light text, blue border
        document.querySelectorAll(
            'button[data-testid="stBaseButton-primary"], ' +
            'button[data-testid="stBaseButton-primaryFormSubmit"]'
        ).forEach(function(btn){
            btn.style.setProperty('background-color', '#1A1A2E', 'important');
            btn.style.setProperty('color', '#E8E8ED', 'important');
            btn.style.setProperty('font-weight', '600', 'important');
            btn.style.setProperty('border', '1px solid #6C8CFF', 'important');
            btn.style.setProperty('border-radius', '10px', 'important');
            btn.querySelectorAll('p, span, div').forEach(function(el){
                el.style.setProperty('color', '#E8E8ED', 'important');
            });
        });
        // Secondary buttons
        document.querySelectorAll(
            'button[data-testid="stBaseButton-secondary"]'
        ).forEach(function(btn){
            btn.style.setProperty('background-color', '#141420', 'important');
            btn.style.setProperty('color', '#E8E8ED', 'important');
            btn.style.setProperty('border', '1px solid #2A2A3C', 'important');
            btn.style.setProperty('border-radius', '8px', 'important');
        });
    }

    fixButtons();
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', fixButtons);
    }
    setTimeout(fixButtons, 300);
    setTimeout(fixButtons, 800);
    setTimeout(fixButtons, 1500);
    setTimeout(fixButtons, 3000);

    var observer = new MutationObserver(function(){ fixButtons(); });
    observer.observe(document.body, {childList: true, subtree: true, attributes: true, attributeFilter: ['style','class']});
})();
</script>
""", unsafe_allow_javascript=True)

# ─── Helpers de UI ────────────────────────────────────────────────────────────

def _esc(texto) -> str:
    """html.escape para qualquer valor que vem do LLM e entra em HTML (P8)."""
    import html as _html
    return _html.escape(str(texto or ""))


def _api_key_ok() -> bool:
    """Verifica se há chave configurada sem expor o valor."""
    from gemini import _get_api_key  # noqa: PLC0415
    return bool(_get_api_key())


def clipboard_button(text: str, label: str, key: str) -> None:
    """
    Botão que copia direto para a área de transferência via
    navigator.clipboard (funciona em localhost, que é contexto seguro).
    Fallback: se a API falhar (ex.: HTTP não seguro), exibe o texto
    para copiar manualmente, como no comportamento antigo.
    """
    if st.button(label, key=key, use_container_width=True):
        components.html(
            f"""
            <script>
            (function() {{
                var texto = {json.dumps(text)};
                if (navigator.clipboard && window.isSecureContext) {{
                    navigator.clipboard.writeText(texto).then(function() {{
                        var d = parent.document.getElementById("clip-feedback-{key}");
                        d.textContent = "✅ Copiado!";
                        setTimeout(function(){{ d.textContent = ""; }}, 2000);
                    }}).catch(function() {{
                        fallback();
                    }});
                }} else {{
                    fallback();
                }}
                function fallback() {{
                    var ta = document.createElement("textarea");
                    ta.value = texto;
                    document.body.appendChild(ta);
                    ta.select();
                    try {{ document.execCommand("copy"); }} catch(e) {{}}
                    document.body.removeChild(ta);
                    var d = parent.document.getElementById("clip-feedback-{key}");
                    d.textContent = "✅ Copiado!";
                    setTimeout(function(){{ d.textContent = ""; }}, 2000);
                }}
            }})();
            </script>
            """,
            height=0,
        )
        st.success("✅ Copiado para a área de transferência!")
        st.code(text, language=None)


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


def empty_state(key: str) -> None:
    """Renderiza um estado vazio premium (ícone + título + descrição)."""
    estado = EMPTY_STATES.get(key)
    if not estado:
        return
    st.markdown(f"""
    <div class="empty-state">
        <div class="empty-icon">{estado['icon']}</div>
        <div class="empty-title" style="color:{CORES['texto']};">{estado['titulo']}</div>
        <div class="empty-desc" style="color:{CORES['texto_sec']};">{estado['desc']}</div>
    </div>
    """, unsafe_allow_html=True)


def hero_header() -> None:
    """Cabeçalho premium com badge, título em gradiente e subtítulo."""
    st.markdown(f"""
    <div class="hero">
        <div class="hero-inner">
            <span class="hero-badge">🎯 {HERO['badge']}</span>
            <h1 class="hero-title">{HERO['titulo']}</h1>
            <p class="hero-subtitle">{HERO['subtitulo']}</p>
        </div>
    </div>
    """, unsafe_allow_html=True)


def render_idea_card(idea: dict, idx: int) -> None:
    """Renderiza um card de ideia com expander de roteiro e badges estratégicos."""
    eixo = idea.get("eixo", "Didático")
    color = EIXOS.get(eixo, {}).get("cor", CORES["destaque"])
    persona = idea.get("persona_alvo", "")
    tipo_hook = idea.get("tipo_hook", "")
    score = idea.get("score")
    score_just = idea.get("score_justificativa", "")
    idea_id = idea.get("id", f"ideia_{idx}")

    # Carregar estado do ciclo de vida
    estados = load_ideias_estado()
    estado = estados.get(idea_id, {})
    status = estado.get("status", "rascunho")

    badges_html = [
        f'<span style="background:rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.12); color:{color}; padding:3px 12px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},0.25); white-space:nowrap;">{_esc(eixo)}</span>'
    ]
    if persona:
        badges_html.append(
            f'<span style="background:rgba(255,209,102,0.12); color:#FFD166; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(255,209,102,0.25); white-space:nowrap;">🎯 {_esc(persona)}</span>'
        )
    if tipo_hook:
        badges_html.append(
            f'<span style="background:rgba(52,211,153,0.12); color:#34D399; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(52,211,153,0.25); white-space:nowrap;">⚡ {_esc(tipo_hook)}</span>'
        )
    if score:
        badges_html.append(
            f'<span style="background:rgba(129,140,248,0.12); color:#818CF8; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(129,140,248,0.25); white-space:nowrap;">⭐ {_esc(score)}/10 Retenção</span>'
        )
    # Badge de status do ciclo de vida
    status_colors = {
        "rascunho": CORES["texto_sec"],
        "aprovado": CORES["secundaria"],
        "agendado": CORES["destaque"],
        "publicado": CORES["primaria"],
    }
    status_color = status_colors.get(status, CORES["texto_sec"])
    status_emoji = {"rascunho": "📝", "aprovado": "✅", "agendado": "📅", "publicado": "🚀"}.get(status, "📄")
    badges_html.append(
        f'<span style="background:rgba(255,255,255,0.05); color:{status_color}; padding:3px 10px; border-radius:16px; font-size:0.75em; font-weight:600; border:1px solid rgba(255,255,255,0.15); white-space:nowrap;">{status_emoji} {_esc(status)}</span>'
    )

    badges_str = "".join(badges_html)

    score_html = ""
    if score_just:
        score_html = f'<div style="margin-top:10px; padding:6px 12px; background:rgba(255,255,255,0.03); border-left:2px solid {CORES["primaria"]}; font-size:0.78em; color:{CORES["texto_sec"]}; border-radius:0 4px 4px 0;"><strong>Estratégia de Retenção:</strong> {_esc(score_just)}</div>'

    st.markdown(f"""
    <div class="idea-card">
        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px; margin-bottom:10px;">
            <h3 style="margin:0; font-size:1.1rem; color:{CORES['primaria']};">{_esc(idea.get('titulo','Sem título'))}</h3>
            <div style="display:flex; gap:6px; flex-wrap:wrap;">{badges_str}</div>
        </div>
        <p style="color:{CORES['texto_sec']}; margin-bottom:10px; font-size:0.88em; line-height:1.5;">{_esc(idea.get('tema',''))}</p>
        <div style="display:flex; flex-wrap:wrap; gap:20px;">
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">Público</div>
                <div style="color:{CORES['texto']}; font-size:0.88em;">{_esc(idea.get('publico_alvo',''))}</div>
            </div>
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">KPI Alvo</div>
                <div style="color:{color}; font-weight:600; font-size:0.88em;">{_esc(idea.get('kpi_alvo',''))}</div>
            </div>
            <div>
                <div style="font-size:0.72em; text-transform:uppercase; letter-spacing:0.06em; color:{CORES['texto_sec']}; margin-bottom:2px; font-weight:600;">CTA</div>
                <div style="color:{CORES['primaria']}; font-weight:600; font-size:0.88em;">
                    Comente "{_esc(idea.get('cta',''))}"
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
                    {icon} {_esc(day.get('dia',''))} — {_esc(day.get('data',''))}
                </strong>
                <span style="color:{CORES['texto_sec']}; margin-left:8px; font-size:0.85em;">{_esc(day.get('horario',''))}</span>
            </div>
            <span style="background:rgba({int(canal_color[1:3],16)},{int(canal_color[3:5],16)},{int(canal_color[5:7],16)},0.12); color:{canal_color};
                  padding:2px 10px; border-radius:12px; font-size:0.75em;
                  font-weight:500; border:1px solid rgba({int(canal_color[1:3],16)},{int(canal_color[3:5],16)},{int(canal_color[5:7],16)},0.25); white-space:nowrap;">{_esc(canal)}</span>
        </div>
        <p style="color:{CORES['texto']}; margin:8px 0 4px 0; font-size:0.88em; line-height:1.5;">
            {_esc(day.get('conteudo_resumo',''))}
        </p>
        <p style="color:{CORES['texto_sec']}; margin:0; font-size:0.82em;">
            📌 CTA: {_esc(day.get('cta','—'))}
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
hero_header()
flow_progress()

# ─── Tabs principais ──────────────────────────────────────────────────────────
tab1, tab2, tab8, tab3, tab4, tab5, tab6, tab7, tab9, tab10 = st.tabs([
    "📈 Tendências",
    "💡 Ideias",
    "🔬 NotebookLM",
    "🎨 Prompts Google Flow",
    "🖼️ Gerador de Imagens",
    "📝 Legendas",
    "📅 Cronograma & Métricas",
    "📦 Lote",
    "🎬 Vídeo Curto",
    "🗂️ Histórico",
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
                linhas = [ln.strip() for ln in nb_result.split("\n") if ln.strip() and not ln.startswith("#")]
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
                st.warning("⚠️ Fallback: ideias genéricas criadas a partir do texto (não foram extraídas diretamente do NotebookLM).")

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
    # Semáforo do feedback loop: sem métricas úteis, o Gemini gera sem
    # aprendizado real e nada avisava
    _metricas_uteis = [
        m for m in load_metricas()
        if m.get("alcance", 0) > 0 and str(m.get("titulo", "")).strip()
    ]
    if _metricas_uteis:
        st.success(
            f"🟢 **Feedback loop ATIVO** — {len(_metricas_uteis)} post(s) com métricas reais "
            "alimentando a geração de ideias."
        )
    else:
        st.info(
            "🔴 **Feedback loop INATIVO** — nenhuma métrica útil registrada. "
            "Registre métricas na aba 📅 Cronograma & Métricas para que as novas ideias "
            "aprendam com o que performou melhor."
        )

    c1, c2 = st.columns([3, 1])
    with c1:
        foco = st.selectbox(
            "Filtrar por eixo:",
            ["Todos", "Didático (Salvamentos)", "Comportamental (Envios DM)", "Diagnóstico (Leads WhatsApp)"],
        )
    with c2:
        col_gerar, col_nova = st.columns(2)
        with col_gerar:
            gerar_ideias_btn = st.button("🎲 Gerar Ideias", type="primary", use_container_width=True)
        with col_nova:
            if st.button("🔄 Forçar novas", use_container_width=True,
                         help="Ignora o cache e gera ideias novas"):
                invalidate_cache(get_prompt_ideias())
                st.session_state.pop("ideias", None)
                st.rerun()

    if gerar_ideias_btn:
        if not _api_key_ok():
            st.warning("⚠️ Configure a chave API Gemini.")
        else:
            # Invalida o cache SEMPRE no clique — cada clique = lote novo (M6)
            invalidate_cache(get_prompt_ideias())
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
        empty_state("selecao")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opcoes_p = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
        escolha = st.selectbox("Ideia para gerar prompts:", list(opcoes_p.keys()), key="sel_prompt")

        if st.button("🎨 Gerar Prompts", type="primary", use_container_width=True):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ideia = opcoes_p[escolha]
                # Guarda com índice para não sobrescrever prompts de outras ideias (P3)
                with st.spinner("🤖 Gerando prompts de imagem…"):
                    dados = gerar_prompts_ideia(ideia, forcar=True)
                    if dados:
                        titulo = ideia.get("titulo", "Ideia")
                        st.session_state.setdefault("prompts_lote", []).append(
                            {"titulo": titulo, "prompts": dados, "ideia": ideia}
                        )
                        save_geracao("prompts", {"titulo": titulo, "prompts": dados})
                        avisos_novos = validate_prompts(dados, ideia)
                        if avisos_novos:
                            st.warning(f"⚠️ {len(avisos_novos)} aviso(s) na validação dos prompts gerados.")
                        else:
                            st.success("✅ Prompts gerados e validados!")

        if st.session_state.get("prompts_lote"):
            prompts_items = st.session_state["prompts_lote"]
            # Seletor quando há várias gerações (P3 — nada se sobrescreve)
            idx_p = len(prompts_items) - 1
            if len(prompts_items) > 1:
                labels_p = [f"{n + 1}. {it.get('titulo', 'Ideia')}" for n, it in enumerate(prompts_items)]
                csel, cdel = st.columns([5, 1])
                with csel:
                    idx_p = labels_p.index(st.selectbox("Geração de prompts:", labels_p, key="sel_prompts_lote"))
                with cdel:
                    st.write("")  # alinha o botão ao selectbox
                    if st.button("🗑️", key="del_prompts_lote", help="Remover esta geração"):
                        prompts_items.pop(idx_p)
                        if not prompts_items:
                            st.session_state.pop("prompts_lote", None)
                        st.rerun()
            item_p = prompts_items[idx_p]
            # Entradas legadas do histórico podem ter o payload cru ({slides, paleta...})
            prompts = item_p.get("prompts") if "prompts" in item_p else item_p
            if not isinstance(prompts, dict):
                prompts = {}

            # Validação na exibição (cobre gerações restauradas do histórico)
            avisos_p = validate_prompts(prompts, item_p.get("ideia"))
            if avisos_p:
                with st.expander(f"⚠️ Avisos de validação ({len(avisos_p)})", expanded=True):
                    for a in avisos_p:
                        st.warning(a)

            # Paleta de cores — cores vêm do LLM: só entram no style se forem hex
            # válidos (cor_eh_valida) e nome/valor passam por html.escape (anti-XSS)
            paleta = prompts.get("paleta_cores", {})
            if paleta:
                st.markdown("### 🎨 Paleta")
                pcols = st.columns(len(paleta))
                for i, (nome, cor) in enumerate(paleta.items()):
                    nome_seg = html.escape(str(nome))
                    cor_txt = html.escape(str(cor))
                    swatch = ""
                    if cor_eh_valida(cor):
                        swatch = (
                            f'<div style="width:52px;height:52px;background:{str(cor).strip()};'
                            f" border-radius:8px;margin:0 auto 4px;"
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

            # Base prompt — estilo compartilhado entre as 8 lâminas (regra 9)
            base_prompt = (prompts.get("base_prompt") or "").strip()
            if base_prompt:
                st.markdown("### 🧩 Base Prompt (consistência entre as 8 lâminas)")
                st.code(base_prompt, language=None)
                clipboard_button(
                    base_prompt, "📋 Copiar Base Prompt", key="clip_base_prompt"
                )

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

    # Modo 3: Todos os slides de um carrossel
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

        # ── M1: revisão dos textos ANTES de gerar ─────────────────────────
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

        if st.button("🎠 Gerar Todos os Slides", type="primary", use_container_width=True):
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


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5 — LEGENDAS
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("## 📝 Gerador de Legendas")
    st.markdown("Gera 3 opções de legenda conectadas ao tema do carrossel selecionado.")

    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opts_l = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
        escolha_l = st.selectbox("Carrossel:", list(opts_l.keys()), key="sel_legenda")

        if st.button("📝 Gerar Legendas", type="primary", use_container_width=True):
            if not _api_key_ok():
                st.warning("⚠️ Configure a chave API Gemini.")
            else:
                ideia = opts_l[escolha_l]
                with st.spinner("🤖 Gerando 3 opções de legenda…"):
                    dados = gerar_legendas_ideia(ideia, forcar=True)
                    if dados:
                        dados["titulo"] = ideia.get("titulo", "Ideia")
                        st.session_state.setdefault("legendas_lote", []).append(dados)
                        save_geracao("legendas", dados)
                        st.success("✅ 3 legendas geradas!")

        if st.session_state.get("legendas_lote"):
            legendas_items = st.session_state["legendas_lote"]
            # Seletor quando há várias gerações (P3 — nada se sobrescreve)
            idx_l = len(legendas_items) - 1
            if len(legendas_items) > 1:
                labels_l = [f"{n + 1}. {it.get('titulo') or 'Geração'}" for n, it in enumerate(legendas_items)]
                csel_l, cdel_l = st.columns([5, 1])
                with csel_l:
                    idx_l = labels_l.index(st.selectbox("Geração de legendas:", labels_l, key="sel_legendas_lote"))
                with cdel_l:
                    st.write("")  # alinha o botão ao selectbox
                    if st.button("🗑️", key="del_legendas_lote", help="Remover esta geração"):
                        legendas_items.pop(idx_l)
                        if not legendas_items:
                            st.session_state.pop("legendas_lote", None)
                        st.rerun()
            legendas_data = legendas_items[idx_l]
            opcao_icons = {1: "🔴", 2: "🟡", 3: "🟢"}

            for leg in legendas_data.get("legendas", []):
                op = leg.get("opcao", 1)
                estilo = leg.get("estilo", "")
                tecnica = leg.get("tecnica", "")
                titulo_exp = f"{opcao_icons.get(op,'•')} Opção {op} — {estilo}"
                if tecnica:
                    titulo_exp += f" [{tecnica}]"
                legenda_completa = leg.get("legenda_completa", "")
                # Contagem local: o número do modelo (char_count) só entra como
                # fallback quando o texto completo não veio na resposta.
                char_count = (
                    len(legenda_completa)
                    if legenda_completa
                    else int(leg.get("char_count") or 0)
                )

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
                    f"OPÇÃO {leg.get('opcao','?')} — {leg.get('estilo','')}\n\n{leg.get('legenda_completa','')}"
                    for leg in legendas_data.get("legendas", [])
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
        empty_state("selecao")
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

        submitted = st.form_submit_button("💾 Salvar Métricas", use_container_width=True)

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
        import csv
        from io import StringIO

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
    st.caption("Preencha as credenciais no .env. A API busca impressões, salvamentos, shares e comentários.")

    # Leitura de variáveis de ambiente
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN", "")
    page_id = os.getenv("INSTAGRAM_PAGE_ID", "")

    if not token or not page_id:
        st.warning("⚠️ Configure `INSTAGRAM_ACCESS_TOKEN` e `INSTAGRAM_PAGE_ID` no arquivo .env.")
    else:
        if st.button("⬇️ Buscar Métricas do Instagram", key="btn_fetch_instagram", use_container_width=True):
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
                    st.error("❌ Não foi possível buscar métricas. Verifique token e page_id.")

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
        st.dataframe(df, use_container_width=True)

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


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7 — PROCESSADOR EM LOTE
# ═══════════════════════════════════════════════════════════════════════════════
with tab7:
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

        if st.button("🚀 Processar Tudo em Lote", type="primary", use_container_width=True):
            if not _api_key_ok():
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
                    with st.expander(f"📋 {item['titulo']}", expanded=False):
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
            if st.button("📥 Exportar Lote Completo (ZIP)", use_container_width=True):
                zip_buf = BytesIO()
                with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                    for _key, item in prompts_items.items():
                        fname = item["titulo"][:50].replace(" ", "_")
                        zf.writestr(
                            f"prompts/{fname}.json",
                            json.dumps(item["prompts"], ensure_ascii=False, indent=2),
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
            "❌ CLI `notebooklm` não encontrado no sistema. \n"
            "Instale com: `pip install google-notebooklm-cli`\n"
            "Ou siga o guia em: https://github.com/googlegoogle/notebooklm-cli\n"
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

        # Persiste o notebook ativo para as demais abas (ex.: Vídeo Curto)
        st.session_state["_nb_active_id"] = selected_nb_id

        # Sidebar com info do notebook
        with st.sidebar:
            st.markdown("---")
            st.markdown("## 🔬 NotebookLM")
            st.markdown("**Notebook ativo:**")
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
                status.info(f"📚 **[1/{total_steps}]** Pesquisando tendências no NotebookLM…")
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
                    status.info(f"💡 **[{step + 1}/{total_steps}]** Gerando 6 ideias estratégicas…")
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
                    status.info(f"🎨 **[{step + 1}/{total_steps}]** Gerando prompts visuais para {len(ideias_formatadas)} ideias…")
                    # Gerar prompts para a primeira ideia selecionada
                    first_idea = ideias_formatadas[0]
                    prompts_data = gerar_prompts_ideia(first_idea, forcar=True)
                    if prompts_data:
                        # Mesmo formato da aba 3 ({titulo, prompts, ideia}) — exibição compatível
                        st.session_state.setdefault("prompts_lote", []).append(
                            {
                                "titulo": first_idea.get("titulo", "Ideia"),
                                "prompts": prompts_data,
                                "ideia": first_idea,
                            }
                        )
                        save_geracao("prompts", {"titulo": first_idea.get("titulo", "Ideia"), "prompts": prompts_data})

                    step += 1
                    progress.progress(step / total_steps)

                # ── Etapa 4: Legendas (opcional) ─────────────────────────────
                if pipeline_ok and pip_legendas:
                    status.info(f"📝 **[{step + 1}/{total_steps}]** Gerando legendas Instagram…")
                    first_idea = ideias_formatadas[0]
                    legendas_data = gerar_legendas_ideia(first_idea, forcar=True)
                    if legendas_data:
                        legendas_data["titulo"] = first_idea.get("titulo", "Ideia")
                        st.session_state.setdefault("legendas_lote", []).append(legendas_data)
                        save_geracao("legendas", legendas_data)

                    step += 1
                    progress.progress(step / total_steps)

                # ── Etapa 5: Cronograma (opcional) ───────────────────────────
                if pipeline_ok and pip_cronograma:
                    status.info(f"📅 **[{step + 1}/{total_steps}]** Montando cronograma de 2 semanas…")
                    cron_data = gerar_cronograma(ideias_formatadas, forcar=True)
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

                # Mapear tipos de consulta para builders de prompt.
                # A execução usa ask_notebook_streaming/ask_notebook direto com
                # o prompt já montado (as funções get_*_streaming esperam o
                # argumento cru, não o prompt pronto).
                consulta_config = {
                    "📈 Tendências do Setor": {
                        "prompt_builder": nlm._build_trends_prompt,
                        "args": {"context": "educação infantil e reforço escolar"},
                        "result_key": "tendencias",
                        "tab_name": "📈 Tendências"
                    },
                    "💡 Ideias de Carrossel": {
                        "prompt_builder": nlm._build_ideas_prompt,
                        "args": {},
                        "result_key": "ideias",
                        "tab_name": "💡 Ideias"
                    },
                    "🏢 Análise de Concorrência": {
                        "prompt_builder": nlm._build_competitor_prompt,
                        "args": {},
                        "result_key": "concorrentes",
                        "tab_name": "🏢 Análise de Concorrência"
                    },
                    "❓ Pergunta Livre": {
                        "prompt_builder": nlm._build_search_prompt,
                        "args": {},
                        "result_key": None,
                        "tab_name": "🔍 Consulta Livre"
                    }
                }

                with st.status("🔍 Consultando NotebookLM…", expanded=True) as status_ctx:
                    config = consulta_config[consulta_tipo]

                    # Preparar argumentos
                    prompt_args = config["args"].copy()
                    if consulta_tipo == "❓ Pergunta Livre":
                        pergunta_texto = st.session_state.get("nb_pergunta_livre", "").strip()
                        if not pergunta_texto:
                            st.warning("⚠️ Digite uma pergunta para consultar o notebook.")
                            result = None
                        else:
                            prompt_args["query"] = pergunta_texto
                            result = None  # Will be set below
                    else:
                        result = None  # Will be set below

                    # Executar consulta se ainda não definida
                    if result is None:
                        prompt = config["prompt_builder"](**prompt_args)
                        result = nlm.ask_notebook_streaming(selected_nb_id, prompt, callback=on_chunk)
                        if not result:
                            result = nlm.ask_notebook(selected_nb_id, prompt)

                    # Fallback Gemini quando NLM falha (opcional, só se há chave)
                    if not result and _api_key_ok() and consulta_tipo in ["📈 Tendências do Setor", "💡 Ideias de Carrossel"]:
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
                    # Salvar resultado bruto para exibição
                    st.session_state["nb_result"] = result

                    # Processar resultado baseado no tipo
                    data_parsed = extract_json(result)
                    if not data_parsed:
                        try:
                            data_parsed = json.loads(result)
                        except Exception:
                            data_parsed = {}

                    # Persistir resultados estruturados para uso em outras abas
                    if config["result_key"] and isinstance(data_parsed, dict) and config["result_key"] in data_parsed:
                        key_data = data_parsed[config["result_key"]]

                        if config["result_key"] == "ideias":
                            ideias_list = key_data
                            ideias_formatadas = [_format_ideia(i) for i in ideias_list]
                            st.session_state["ideias"] = {"ideias": ideias_formatadas}
                            st.session_state["ideias_selecionadas"] = ideias_formatadas
                            save_geracao("ideias", {"ideias": ideias_formatadas})
                            st.success(f"✅ Consulta concluída! {len(ideias_formatadas)} ideias foram enviadas para a aba '{config['tab_name']}'.")

                        elif config["result_key"] == "tendencias":
                            st.session_state["tendencias"] = key_data
                            st.session_state["tendencias_texto"] = json.dumps(key_data, ensure_ascii=False)
                            save_geracao("tendencias", key_data)
                            st.success(f"✅ Consulta concluída! Dados enviados para a aba '{config['tab_name']}'.")

                        else:
                            # Para outros tipos, salvar genéricamente
                            st.session_state[config["result_key"]] = key_data
                            save_geracao(config["result_key"], key_data)
                            st.success(f"✅ Consulta concluída! Dados enviados para a aba '{config['tab_name']}'.")
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
                            if st.button("📤 Enviar para Prompts", key=f"send_idea_{i}"):
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
            st.markdown("### 🔗 Link direto para o notebook")
            st.markdown(f"[Abrir no NotebookLM](https://notebooklm.google.com/notebook/{selected_nb_id})")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 9 — VÍDEO CURTO (requisição para Gemini Notebook — Video Overview "Short")
# ═══════════════════════════════════════════════════════════════════════════════
with tab9:
    st.markdown("## 🎬 Requisição de Vídeo Curto — Gemini Notebook")
    st.markdown(
        "Monta uma **requisição detalhada** para gerar um **Video Overview no formato \"Short\"** "
        "no Gemini Notebook (Studio): um vídeo vertical 9:16 de ~60s que condensa o tema central "
        "da ideia, **fiel ao roteiro dos slides**."
    )

    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opcoes_v = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
        escolha_v = st.selectbox("Ideia de origem:", list(opcoes_v.keys()), key="sel_video")

        ideia = opcoes_v[escolha_v]
        slides_list = ideia.get("slides_sugeridos", [])

        # ── Prévia do roteiro (fonte da fidelidade) ──────────────────────────
        if slides_list:
            with st.expander(f"📄 Roteiro de origem ({len(slides_list)} slides)", expanded=False):
                for slide in slides_list:
                    st.markdown(f"**Slide {slide.get('slide','?')} — {slide.get('tipo','')}**")
                    st.markdown(f"_{slide.get('texto','')}_")
                    st.divider()
        else:
            st.warning("⚠️ Esta ideia não possui roteiro de slides. Gere os slides antes de montar a requisição.")

        # ── Opção: gravar a requisição no Notebook ───────────────────────────
        salvar_nlm = st.checkbox(
            "🔬 Gravar também a requisição no notebook do Gemini Notebook (via CLI)",
            value=True,
            key="video_salvar_nlm",
            help="Grava a requisição completa como pergunta no notebook ativo do Gemini Notebook.",
        )

        if st.button("🎬 Montar Requisição de Vídeo", type="primary", use_container_width=True, key="btn_video"):
            if not _api_key_ok():
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

        # ── Exibição do resultado ────────────────────────────────────────────
        if st.session_state.get("video_curto"):
            vd = st.session_state["video_curto"]

            # Parâmetros de geração
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
                        st.markdown(f"""
                        <div class="metric-box">
                            <strong style="color:{CORES['texto_sec']};font-size:0.72em;text-transform:uppercase;">{label}</strong><br>
                            <span style="color:{CORES['primaria']};font-weight:600;">{valor}</span>
                        </div>
                        """, unsafe_allow_html=True)

            # Steering prompt
            steering = vd.get("steering_prompt", "")
            if steering:
                st.markdown("### 🎯 Steering Prompt (cole no campo de tópico/foco)")
                st.code(steering, language=None)
                clipboard_button(steering, "📋 Copiar Steering Prompt", key="clip_video_steering")

            # Narrativa
            narrativa = vd.get("narrativa", "")
            if narrativa:
                st.markdown("### 📖 Narrativa do Short (fiel ao roteiro)")
                st.markdown(narrativa)

            # Requisição completa (registro / gravação no notebook)
            requisicao_completa = vd.get("requisicao_completa", "")
            if requisicao_completa:
                st.markdown("### 📦 Requisição Completa (para registro/gravação)")
                st.code(requisicao_completa, language=None)
                clipboard_button(requisicao_completa, "📋 Copiar Requisição Completa", key="clip_video_req")

                # Gravar no Notebook via CLI
                if salvar_nlm and nlm.is_nlm_available():
                    if st.button("🔬 Gravar Requisição no Gemini Notebook", use_container_width=True, key="btn_video_nlm"):
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

            # Exportações
            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ Exportar JSON",
                    data=json.dumps(vd, ensure_ascii=False, indent=2),
                    file_name="requisicao_video_curto.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with c2:
                st.download_button(
                    "⬇️ Exportar Requisição (.txt)",
                    data=requisicao_completa,
                    file_name="requisicao_video_curto.txt",
                    mime="text/plain",
                    use_container_width=True,
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 10 — HISTÓRICO DE GERAÇÕES (M3)
# ═══════════════════════════════════════════════════════════════════════════════
with tab10:
    st.markdown("## 🗂️ Histórico de Gerações")
    st.markdown("Últimas 50 gerações salvas em disco. Expanda para ver o conteúdo e restaure qualquer uma.")

    from persistence import load_historico_geracoes  # noqa: PLC0415

    historico = load_historico_geracoes()

    if not historico:
        st.info("Nenhuma geração salva ainda. Gere conteúdo nas outras abas e ele aparecerá aqui.")
    else:
        # Filtro por tipo
        tipos_disponiveis = ["Todos"] + sorted({e.get("tipo", "?") for e in historico})
        filtro_tipo = st.selectbox("Filtrar por tipo:", tipos_disponiveis)
        filtrado = [e for e in historico if filtro_tipo == "Todos" or e.get("tipo") == filtro_tipo]

        st.caption(f"Mostrando {len(filtrado)} de {len(historico)} gerações (mais recentes primeiro).")

        # Mapeamento tipo → session_state key + ícone
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
            session_key = _TIPO_META.get(tipo, (tipo, "📦"))[0]
            icon = _TIPO_META.get(tipo, (tipo, "📦"))[1]

            # Resumo amigável por tipo
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
                # Botão restaurar (M3)
                if session_key:
                    if st.button("↩️ Restaurar esta geração", key=f"restaurar_hist_{pos}", use_container_width=True):
                        if session_key == "prompts_lote":
                            st.session_state.setdefault("prompts_lote", []).append(dados)
                        elif session_key == "legendas_lote":
                            st.session_state.setdefault("legendas_lote", []).append(dados)
                        elif session_key == "ideias":
                            st.session_state["ideias"] = dados
                            st.session_state["ideias_selecionadas"] = dados.get("ideias", [])
                        else:
                            st.session_state[session_key] = dados
                        st.success(f"✅ Restaurado! Veja na aba correspondente ({tipo}).")
                        st.rerun()

                st.json(dados, expanded=False)
