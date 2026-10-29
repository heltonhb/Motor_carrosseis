"""
tabs/_ui.py — Helpers compartilhados entre todas as abas.

Extraídos do app.py para eliminar duplicação e manter as tabs enxutas.
"""

import html as _html
import json

import streamlit as st

from config import CORES, FLOW_FOTOS, TONES, TONES_PADRAO


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
    """Renderiza um item de cronograma alinhado ao visual Google Stitch."""
    canal_icons = {
        "Stories": "📱", "Feed": "📸", "Reels": "🎬", "Feed (Carrossel)": "🎠",
    }
    canal = day.get("canal", "")
    icon = canal_icons.get(canal, "📱")
    tipo = day.get("tipo", "")

    if "Carrossel" in tipo or "Feed" in canal:
        css_class = "carrossel"
        badge_bg = "rgba(36, 99, 235, 0.15)"
        badge_border = "rgba(36, 99, 235, 0.35)"
        badge_text = "#60A5FA"
    elif "Stories" in canal:
        css_class = "stories"
        badge_bg = "rgba(0, 119, 153, 0.15)"
        badge_border = "rgba(0, 119, 153, 0.35)"
        badge_text = "#38BDF8"
    elif "Reel" in tipo:
        css_class = "reel"
        badge_bg = "rgba(248, 113, 113, 0.15)"
        badge_border = "rgba(248, 113, 113, 0.35)"
        badge_text = "#FCA5A5"
    else:
        css_class = ""
        badge_bg = "rgba(148, 163, 184, 0.12)"
        badge_border = "rgba(148, 163, 184, 0.25)"
        badge_text = "#94A3B8"

    st.html(f"""
<div class="timeline-item {css_class}">
    <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
        <div style="display:flex; align-items:center; gap:10px;">
            <span style="display:inline-flex; align-items:center; justify-content:center; width:28px; height:28px; border-radius:8px; background:{badge_bg}; border:1px solid {badge_border}; font-size:14px;">
                {icon}
            </span>
            <div>
                <strong style="color:#FFFFFF; font-weight:700; font-size:0.95em;">
                    {esc(day.get('dia',''))} — {esc(day.get('data',''))}
                </strong>
                <span style="color:{CORES['texto_sec']}; margin-left:8px; font-family:'JetBrains Mono',monospace; font-size:0.82em; background:rgba(255,255,255,0.04); padding:2px 6px; border-radius:4px;">
                    {esc(day.get('horario',''))}
                </span>
            </div>
        </div>
        <span style="background:{badge_bg}; color:{badge_text};
              padding:3px 10px; border-radius:9999px; font-size:0.75em;
              font-weight:600; border:1px solid {badge_border}; white-space:nowrap; letter-spacing:0.02em;">
            {esc(canal)}
        </span>
    </div>
    <p style="color:#E2E8F0; margin:10px 0 6px 0; font-size:0.9em; line-height:1.55;">
        {esc(day.get('conteudo_resumo',''))}
    </p>
    <div style="display:flex; align-items:center; gap:8px; margin-top:6px; padding-top:6px; border-top:1px solid rgba(255,255,255,0.05); font-size:0.82em; color:{CORES['texto_sec']};">
        <span style="color:{CORES['secundaria']}; font-weight:600;">📌 CTA:</span>
        <span>{esc(day.get('cta','—'))}</span>
    </div>
</div>
    """)


def empty_state(key: str) -> None:
    """Renderiza um estado vazio premium estilo Google Stitch."""
    from config import EMPTY_STATES
    estado = EMPTY_STATES.get(key)
    if not estado:
        return
    st.html(f"""
<div class="empty-state">
    <div class="empty-icon">{estado['icon']}</div>
    <div class="empty-title" style="color:#FFFFFF; font-weight:700;">{estado['titulo']}</div>
    <div class="empty-desc" style="color:{CORES['texto_sec']};">{estado['desc']}</div>
</div>
    """)


def api_key_ok() -> bool:
    """Verifica se há chave configurada sem expor o valor."""
    from gemini import _get_api_key
    return bool(_get_api_key())


def seletor_tom(key: str = "tom_selecionado") -> str:
    """
    Selectbox de tom de voz, compartilhado pelas abas que geram texto.

    A chave é única por aba (ex.: "tom_selecionado_ideias") para não haver
    colisão de session_state quando o usuário navega entre abas. Devolve a
    chave do tom, não o rótulo — é a chave que prompts.py entende.
    """
    return st.selectbox(
        "\U0001f399️ Tom de voz (ghostwriter)",
        list(TONES.keys()),
        index=list(TONES.keys()).index(TONES_PADRAO),
        format_func=lambda k: TONES[k],
        key=key,
        help=(
            "A persona CAROL define quem fala; o tom define como ela fala neste "
            "carrossel. Automático usa o registro que melhor converte no eixo."
        ),
    )


# ─── Fidelidade à referência ──────────────────────────────────────────────
FIDELIDADES = {
    "baixa": "Baixa — só clima e paleta da referência",
    "media": "Média — paleta, tipografia e grid (padrão)",
    "alta": "Alta — mesma composição e enquadramento",
}


def seletor_fidelidade(key: str = "fidelidade_selecionada") -> str:
    """
    Selectbox de fidelidade à referência visual.

    Alta fidelidade sem imagem anexada não existe: o modelo receberia só o texto
    da cena e não teria o que copiar. Em vez de esconder a opção, deixamos
    visível e avisamos na hora — o usuário precisa saber por que o resultado
    ficou menos parecido do que ele esperava.
    """
    nivel = st.selectbox(
        "\N{FRAME WITH PICTURE} Fidelidade à referência",
        list(FIDELIDADES.keys()),
        index=list(FIDELIDADES.keys()).index("media"),
        format_func=lambda k: FIDELIDADES[k],
        key=key,
        help=(
            "Quanto o modelo copia da foto de referência. Sem referência anexada "
            "(FLOW_FOTOS desligado), alta cai para média."
        ),
    )
    if nivel == "alta" and not FLOW_FOTOS:
        st.info(
            "🔍 FLOW_FOTOS está desligado: a foto não está sendo anexada ao "
            "Gemini, então alta fidelidade vai cair para média. Ligue FLOW_FOTOS "
            "no .env para usar alta de verdade."
        )
    return nivel
