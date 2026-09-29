"""
Motor de Carrosséis — Ensina Mais Tatuapé
Gerador inteligente de carrosséis para Instagram com análise de tendências,
ideias estratégicas, prompts para Google Flow, geração de imagens e cronograma.

v2 — Arquitetura modular: cada aba é um módulo em tabs/.
"""

# ─── Imports ────────────────────────────────────────────────────────────────
import os
import streamlit as st
from dotenv import load_dotenv

from config import CORES, HERO, KPIS, UNIDADE, FORMATO
from persistence import sync_session_from_disk

load_dotenv()

# ─── Configuração da página ─────────────────────────────────────────────────
st.set_page_config(
    page_title="Motor de Carrosséis — Ensina Mais Tatuapé",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ─── Auth ───────────────────────────────────────────────────────────────────
def _auth_required() -> bool:
    """Lê a chave de ativação do login OIDC sem quebrar o modo local."""
    try:
        configured = st.secrets.get("AUTH_REQUIRED")
    except Exception:
        configured = None
    if configured is None:
        configured = os.getenv("AUTH_REQUIRED", "false")
    return str(configured).strip().lower() in {"1", "true", "yes", "on"}


if _auth_required():
    if not st.user.is_logged_in:
        st.title("Acesso restrito")
        st.caption("Faça login para acessar o Motor de Carrosséis.")
        st.login()
        st.stop()

    with st.sidebar:
        usuario = getattr(st.user, "name", None) or getattr(st.user, "email", None)
        if usuario:
            st.caption(f"Usuário: {usuario}")
        if st.button("Sair", key="_logout_button"):
            st.logout()

# ─── Startup: sincronizar disco → session_state (uma vez por sessão) ────────
if "_synced" not in st.session_state:
    sync_session_from_disk(st.session_state)
    st.session_state["_synced"] = True


# ─── CSS customizado ────────────────────────────────────────────────────────
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

    /* ═══ Tabs ═══ */
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

    /* ═══ Cards ═══ */
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

    /* ═══ Botões ═══ */
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

# ─── Forçar cores nos botões via JS ────────────────────────────────────────
st.html("""
<script>
(function(){
    function fixButtons(){
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


# ─── UI Components ──────────────────────────────────────────────────────────
def flow_progress() -> None:
    """Barra de progresso do fluxo de trabalho no topo do app."""
    etapas = [
        ("tendencias",          "📈 Tendências"),
        ("ideias",              "💡 Ideias"),
        ("ideias_selecionadas", "✅ Seleção"),
        ("prompts_lote",        "🎨 Prompts"),
        ("legendas_lote",       "📝 Legendas"),
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


# ─── Sidebar ────────────────────────────────────────────────────────────────
from gemini import _get_api_key

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

    if _get_api_key():
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


# ─── Título + barra de progresso ───────────────────────────────────────────
hero_header()
flow_progress()

# ─── Tabs principais (routing para módulos) ────────────────────────────────
from tabs.tab_tendencias import render as render_tendencias
from tabs.tab_ideias import render as render_ideias
from tabs.tab_notebooklm import render as render_notebooklm
from tabs.tab_prompts import render as render_prompts
from tabs.tab_imagens import render as render_imagens
from tabs.tab_legendas import render as render_legendas
from tabs.tab_cronograma import render as render_cronograma
from tabs.tab_lote import render as render_lote
from tabs.tab_video import render as render_video
from tabs.tab_historico import render as render_historico

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

with tab1:
    render_tendencias()
with tab2:
    render_ideias()
with tab8:
    render_notebooklm()
with tab3:
    render_prompts()
with tab4:
    render_imagens()
with tab5:
    render_legendas()
with tab6:
    render_cronograma()
with tab7:
    render_lote()
with tab9:
    render_video()
with tab10:
    render_historico()
