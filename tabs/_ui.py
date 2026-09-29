"""
tabs/_ui.py — Helpers compartilhados entre todas as abas.

Extraídos do app.py para eliminar duplicação e manter as tabs enxutas.
"""

import html as _html
import json

import streamlit as st

from config import CORES


def esc(texto) -> str:
    """html.escape para qualquer valor que vem do LLM e entra em HTML."""
    return _html.escape(str(texto or ""))


def clipboard_button(text: str, label: str, key: str) -> None:
    """Botão que copia para a área de transferência via navigator.clipboard."""
    if st.button(label, key=key, width="stretch"):
        st.html(
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
            unsafe_allow_javascript=True,
        )
        st.success("✅ Copiado para a área de transferência!")
        st.code(text, language=None)


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

    canal_color = (
        "#818CF8" if "Carrossel" in tipo or "Feed" in canal
        else "#A78BFA" if "Stories" in canal
        else "#F87171" if "Reel" in tipo
        else CORES["texto_sec"]
    )

    st.markdown(f"""
    <div class="timeline-item {css_class}">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <strong style="color:{CORES['primaria']};">
                    {icon} {esc(day.get('dia',''))} — {esc(day.get('data',''))}
                </strong>
                <span style="color:{CORES['texto_sec']}; margin-left:8px; font-size:0.85em;">{esc(day.get('horario',''))}</span>
            </div>
            <span style="background:rgba({int(canal_color[1:3],16)},{int(canal_color[3:5],16)},{int(canal_color[5:7],16)},0.12); color:{canal_color};
                  padding:2px 10px; border-radius:12px; font-size:0.75em;
                  font-weight:500; border:1px solid rgba({int(canal_color[1:3],16)},{int(canal_color[3:5],16)},{int(canal_color[5:7],16)},0.25); white-space:nowrap;">{esc(canal)}</span>
        </div>
        <p style="color:{CORES['texto']}; margin:8px 0 4px 0; font-size:0.88em; line-height:1.5;">
            {esc(day.get('conteudo_resumo',''))}
        </p>
        <p style="color:{CORES['texto_sec']}; margin:0; font-size:0.82em;">
            📌 CTA: {esc(day.get('cta','—'))}
        </p>
    </div>
    """, unsafe_allow_html=True)


def empty_state(key: str) -> None:
    """Renderiza um estado vazio premium."""
    from config import EMPTY_STATES
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


def api_key_ok() -> bool:
    """Verifica se há chave configurada sem expor o valor."""
    from gemini import _get_api_key
    return bool(_get_api_key())
