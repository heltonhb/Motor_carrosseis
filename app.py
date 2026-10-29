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
st.html(f"""
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">

<style>
    /* ═══ Base & Background (Google Stitch Dark Zinc) ═══ */
    .stApp {{
        background-color: {CORES['app_bg']};
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        color: {CORES['texto']};
    }}
    .main .block-container {{
        padding-top: 1.25rem;
        padding-bottom: 2.5rem;
        max-width: 1400px;
    }}

    /* ═══ Glass Panels & Cards ═══ */
    .glass-panel {{
        background: rgba(24, 24, 31, 0.72);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: {CORES['raio_card']};
    }}

    .glass-card {{
        background: rgba(28, 28, 37, 0.6);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
    }}

    /* ═══ Top Header Stitch ═══ */
    .stitch-header {{
        background: rgba(18, 18, 23, 0.85);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: {CORES['raio_card']};
        padding: 16px 24px;
        margin-bottom: 20px;
        box-shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.5);
    }}

    .stitch-kpi-card {{
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 8px 14px;
        display: flex;
        align-items: center;
        gap: 12px;
        transition: all 0.2s ease;
    }}
    .stitch-kpi-card:hover {{
        border-color: rgba(36, 99, 235, 0.4);
        background: rgba(15, 23, 42, 0.85);
        transform: translateY(-1px);
    }}

    /* ═══ Empty state ═══ */
    .empty-state {{
        text-align: center;
        padding: 44px 24px;
        background: rgba(24, 24, 31, 0.6);
        backdrop-filter: blur(12px);
        border: 1px dashed rgba(255, 255, 255, 0.12);
        border-radius: {CORES['raio_card']};
        margin: 14px 0;
    }}
    .empty-icon {{
        font-size: 2.4rem;
        margin-bottom: 12px;
        animation: float 3s ease-in-out infinite;
    }}
    .empty-title {{ font-size: 1.1rem; font-weight: 700; margin-bottom: 6px; }}
    .empty-desc {{ font-size: 0.9em; line-height: 1.55; max-width: 480px; margin: 0 auto; color: {CORES['texto_sec']}; }}
    @keyframes float {{
        0%, 100% {{ transform: translateY(0); }}
        50% {{ transform: translateY(-6px); }}
    }}

    /* ═══ Tipografia ═══ */
    h1, h2, h3, h4, h5, h6 {{
        color: #FFFFFF !important;
        font-family: 'Plus Jakarta Sans', sans-serif !important;
        font-weight: 700 !important;
        letter-spacing: -0.02em !important;
        line-height: 1.3;
    }}
    h1 {{ font-size: 1.85rem !important; margin-bottom: 0.5rem !important; }}
    h2 {{ font-size: 1.45rem !important; margin-bottom: 0.4rem !important; }}
    h3 {{ font-size: 1.2rem !important; margin-bottom: 0.3rem !important; }}

    p {{ color: {CORES['texto_sec']}; line-height: 1.6; margin-bottom: 0.5rem; }}

    /* ═══ Tabs Stitch ═══ */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 6px;
        background: rgba(18, 18, 23, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 14px;
        padding: 6px;
        margin-bottom: 1.5rem;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent;
        color: {CORES['texto_sec']};
        border-radius: 10px;
        padding: 8px 16px;
        font-weight: 600;
        font-size: 0.86em;
        border: 1px solid transparent;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        white-space: nowrap;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        color: #FFFFFF;
        background-color: rgba(255, 255, 255, 0.05);
    }}
    .stTabs [aria-selected="true"] {{
        color: #FFFFFF !important;
        background: linear-gradient(135deg, rgba(36, 99, 235, 0.25) 0%, rgba(0, 119, 153, 0.20) 100%) !important;
        border: 1px solid rgba(36, 99, 235, 0.5) !important;
        box-shadow: 0 0 15px -3px rgba(36, 99, 235, 0.3) !important;
        font-weight: 700 !important;
    }}

    /* ═══ Cards de Ideias ═══ */
    .idea-card {{
        background: rgba(24, 24, 31, 0.75);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: {CORES['raio_card']};
        padding: 22px 26px;
        margin-bottom: 16px;
        box-shadow: {CORES['app_sombra']};
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
    }}
    .idea-card:hover {{
        box-shadow: 0 10px 25px -3px rgba(36, 99, 235, 0.2), 0 4px 10px -2px rgba(0, 0, 0, 0.4);
        transform: translateY(-2px);
        border-color: rgba(36, 99, 235, 0.4);
    }}
    .idea-card h3 {{
        color: #60A5FA !important;
        margin-top: 0;
        margin-bottom: 8px;
    }}

    /* ═══ Metric box ═══ */
    .metric-box {{
        background: rgba(24, 24, 31, 0.75);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-left: 3px solid {CORES['primaria']};
        padding: 16px 20px;
        border-radius: 0 12px 12px 0;
        margin-bottom: 12px;
        box-shadow: {CORES['app_sombra']};
    }}

    /* ═══ Timeline ═══ */
    .timeline-item {{
        background: rgba(24, 24, 31, 0.75);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-left: 4px solid {CORES['primaria']};
        padding: 16px 20px;
        margin-bottom: 12px;
        border-radius: 0 12px 12px 0;
        box-shadow: {CORES['app_sombra']};
        transition: all 0.2s ease;
    }}
    .timeline-item:hover {{
        box-shadow: 0 8px 20px -3px rgba(0, 0, 0, 0.6);
        transform: translateY(-1px);
        border-color: rgba(255, 255, 255, 0.12);
    }}
    .timeline-item.carrossel {{ border-left-color: #2463eb; }}
    .timeline-item.stories   {{ border-left-color: #007799; }}
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

    /* ═══ Botões Google Stitch ═══ */
    .stButton > button[kind="primary"],
    div[data-testid="stForm"] button[kind="primary"] {{
        background: linear-gradient(135deg, #2463eb 0%, #1d4ed8 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(59, 130, 246, 0.5) !important;
        border-radius: 12px !important;
        font-weight: 700 !important;
        padding: 9px 22px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 0 20px -3px rgba(36, 99, 235, 0.4) !important;
        letter-spacing: 0.01em;
    }}
    .stButton > button[kind="primary"]:hover {{
        background: linear-gradient(135deg, #3b82f6 0%, #2463eb 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 0 25px -2px rgba(36, 99, 235, 0.6) !important;
        transform: translateY(-1px);
    }}
    .stButton > button:not([kind="primary"]),
    .stDownloadButton > button {{
        background-color: rgba(24, 24, 31, 0.85) !important;
        color: #F8FAFC !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 8px 18px !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}
    .stButton > button:not([kind="primary"]):hover,
    .stDownloadButton > button:hover {{
        background-color: rgba(34, 34, 45, 0.95) !important;
        border-color: rgba(255, 255, 255, 0.18) !important;
        color: #FFFFFF !important;
        transform: translateY(-1px);
    }}

    /* ═══ Inputs & Selects ═══ */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea,
    div[data-baseweb="select"] > div {{
        border-radius: 12px !important;
        border: 1px solid rgba(255, 255, 255, 0.09) !important;
        background-color: rgba(18, 18, 23, 0.8) !important;
        color: {CORES['texto']} !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    }}
    .stTextInput > div > div > input:focus,
    .stTextArea > div > div > textarea:focus,
    div[data-baseweb="select"] > div:focus-within {{
        border-color: {CORES['primaria']} !important;
        box-shadow: 0 0 0 3px rgba(36, 99, 235, 0.25) !important;
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
""")

# ─── Forçar cores nos botões via JS ────────────────────────────────────────
st.html("""
<script>
(function(){
    function fixButtons(){
        document.querySelectorAll(
            'button[data-testid="stBaseButton-primary"], ' +
            'button[data-testid="stBaseButton-primaryFormSubmit"]'
        ).forEach(function(btn){
            btn.style.setProperty('background', 'linear-gradient(135deg, #2463eb 0%, #1d4ed8 100%)', 'important');
            btn.style.setProperty('color', '#FFFFFF', 'important');
            btn.style.setProperty('font-weight', '700', 'important');
            btn.style.setProperty('border', '1px solid rgba(59, 130, 246, 0.5)', 'important');
            btn.style.setProperty('border-radius', '12px', 'important');
            btn.style.setProperty('box-shadow', '0 0 20px -3px rgba(36, 99, 235, 0.4)', 'important');
            btn.querySelectorAll('p, span, div').forEach(function(el){
                el.style.setProperty('color', '#FFFFFF', 'important');
            });
        });
        document.querySelectorAll(
            'button[data-testid="stBaseButton-secondary"]'
        ).forEach(function(btn){
            btn.style.setProperty('background-color', 'rgba(24, 24, 31, 0.85)', 'important');
            btn.style.setProperty('color', '#F8FAFC', 'important');
            btn.style.setProperty('border', '1px solid rgba(255, 255, 255, 0.08)', 'important');
            btn.style.setProperty('border-radius', '10px', 'important');
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
    """Barra de progresso do fluxo de trabalho no topo do app estilo Google Stitch."""
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
    st.html(
        f"""
<div style="background:rgba(18, 18, 23, 0.65); backdrop-filter:blur(14px); -webkit-backdrop-filter:blur(14px); border:1px solid rgba(255,255,255,0.06); border-radius:14px; padding:10px 18px; margin-bottom:20px; display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:10px;">
    <div style="display:flex; flex-wrap:wrap; align-items:center; gap:8px;">
        {"".join(html_parts)}
    </div>
    <div style="font-family:'JetBrains Mono',monospace; font-size:0.75rem; color:#64748B; display:flex; align-items:center; gap:6px;">
        <span style="color:#76BC21;">📍</span>
        <span>Rua Coelho Lisboa, 783 &bull; Tatuapé</span>
    </div>
</div>
        """
    )


def hero_header() -> None:
    """Header premium com identidade oficial Ensina Mais Tatuapé + status de IA + KPIs Benchmark (Google Stitch)."""
    st.html(f"""
<div class="stitch-header">
    <div style="display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:16px;">
        <div style="display:flex; align-items:center; gap:14px;">
            <div style="width:44px; height:44px; border-radius:12px; background:linear-gradient(135deg, #2463eb 0%, #007799 100%); display:flex; align-items:center; justify-content:center; box-shadow:0 0 20px -3px rgba(36,99,235,0.45); font-size:22px;">
                🎓
            </div>
            <div>
                <div style="display:flex; align-items:center; gap:8px;">
                    <span style="font-weight:800; font-size:1.15rem; letter-spacing:-0.02em; color:#FFFFFF;">ENSINA MAIS</span>
                    <span style="background:rgba(36, 99, 235, 0.2); color:#60a5fa; border:1px solid rgba(36, 99, 235, 0.4); font-size:0.72rem; font-weight:700; padding:2px 8px; border-radius:9999px; letter-spacing:0.04em;">TATUAPÉ</span>
                </div>
                <p style="font-size:0.8rem; color:#94A3B8; margin:2px 0 0 0; font-weight:500;">Motor de Carrosséis & Growth Social</p>
            </div>
            <div style="display:inline-flex; align-items:center; gap:8px; background:rgba(15,23,42,0.8); border:1px solid rgba(255,255,255,0.08); padding:6px 12px; border-radius:10px; margin-left:6px;">
                <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background:#76BC21; box-shadow:0 0 8px #76BC21;"></span>
                <span style="font-size:0.75rem; font-weight:600; color:#E2E8F0;">Gemini IA</span>
                <span style="font-family:'JetBrains Mono',monospace; font-size:0.65rem; color:#76BC21; background:rgba(118,188,33,0.15); padding:1px 5px; border-radius:4px; font-weight:700;">ONLINE</span>
            </div>
        </div>

        <div style="display:flex; flex-wrap:wrap; align-items:center; gap:10px;">
            <div class="stitch-kpi-card">
                <div style="width:32px; height:32px; border-radius:8px; background:rgba(36,99,235,0.15); display:flex; align-items:center; justify-content:center; color:#60A5FA; font-size:15px;">
                    💾
                </div>
                <div>
                    <div style="font-size:0.72rem; color:#94A3B8; font-weight:500;">Salvamento <span style="font-family:'JetBrains Mono',monospace; color:#64748B;">(&ge;4%)</span></div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span style="font-size:0.95rem; font-weight:800; color:#FFFFFF;">4.8%</span>
                        <span style="font-size:0.7rem; font-weight:700; color:#76BC21;">+0.8%</span>
                    </div>
                </div>
            </div>
            <div class="stitch-kpi-card">
                <div style="width:32px; height:32px; border-radius:8px; background:rgba(0,119,153,0.15); display:flex; align-items:center; justify-content:center; color:#38BDF8; font-size:15px;">
                    📤
                </div>
                <div>
                    <div style="font-size:0.72rem; color:#94A3B8; font-weight:500;">Envios DM <span style="font-family:'JetBrains Mono',monospace; color:#64748B;">(&ge;2.5%)</span></div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span style="font-size:0.95rem; font-weight:800; color:#FFFFFF;">3.2%</span>
                        <span style="font-size:0.7rem; font-weight:700; color:#76BC21;">Meta OK</span>
                    </div>
                </div>
            </div>
            <div class="stitch-kpi-card">
                <div style="width:32px; height:32px; border-radius:8px; background:rgba(118,188,33,0.15); display:flex; align-items:center; justify-content:center; color:#76BC21; font-size:15px;">
                    🆕
                </div>
                <div>
                    <div style="font-size:0.72rem; color:#94A3B8; font-weight:500;">Não Seguid. <span style="font-family:'JetBrains Mono',monospace; color:#64748B;">(&ge;20%)</span></div>
                    <div style="display:flex; align-items:center; gap:6px;">
                        <span style="font-size:0.95rem; font-weight:800; color:#FFFFFF;">34.6%</span>
                        <span style="font-size:0.7rem; font-weight:700; color:#76BC21;">Alta</span>
                    </div>
                </div>
            </div>

            <a href="https://wa.me/5511944750009" target="_blank" style="text-decoration:none; display:inline-flex; align-items:center; gap:8px; background:rgba(118,188,33,0.18); border:1px solid rgba(118,188,33,0.4); color:#FFFFFF; padding:8px 14px; border-radius:12px; font-size:0.8rem; font-weight:700; transition:all 0.2s ease;">
                <span style="color:#76BC21; font-size:16px;">📲</span>
                <span>(11) 94475-0009</span>
            </a>
        </div>
    </div>
</div>
    """)


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
from tabs.tab_animacao import render as render_animacao
from tabs.tab_video import render as render_video
from tabs.tab_historico import render as render_historico

tab1, tab2, tab8, tab3, tab4, tab5, tab6, tab7, tab11, tab9, tab10 = st.tabs([
    "📈 Tendências",
    "💡 Ideias",
    "🔬 NotebookLM",
    "🎨 Prompts Google Flow",
    "🖼️ Gerador de Imagens",
    "📝 Legendas",
    "📅 Cronograma & Métricas",
    "📦 Lote",
    "🎬 Animar Carrossel",
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
with tab11:
    render_animacao()
with tab9:
    render_video()
with tab10:
    render_historico()
