"""
tabs/tab_animacao.py — Aba "Animar Carrossel" (V9).

Pega a ideia selecionada, monta o brief e o storyboard e renderiza o MP4 com
Pillow + ffmpeg. É o "botão Animar" que fecha o nível 6 da escada.

A aba avisa quando está animando rascunhos do template local em vez das imagens
reais do Flow: o movimento é o mesmo, o resultado visual não é.
"""

import streamlit as st

from brief import montar_brief, montar_storyboard, resumo_storyboard, validar_brief
from carrossel_vivo import (
    ffmpeg_disponivel,
    ffmpeg_versao,
    renderizar_carrossel_vivo,
)
from config import FLOW_FOTOS
from tabs._ui import empty_state, seletor_fidelidade


def render() -> None:
    st.markdown("## 🎬 Animar Carrossel")
    st.caption(
        "Transforma os slides em um vídeo 4:5 com entrada de texto, movimento de "
        "câmera e trilha sincronizada no beat. Renderizado por código, com Pillow "
        "e ffmpeg — sem serviço pago."
    )

    if not ffmpeg_disponivel():
        st.error(
            "ffmpeg não encontrado no PATH. Sem ele não há MP4, mas o modo PNG "
            "continua funcionando normalmente em todas as outras abas."
        )
        st.code(f"$ which ffmpeg   # esperado: {ffmpeg_versao()}", language="bash")
        return

    if not st.session_state.get("ideias_selecionadas"):
        empty_state("selecao")
        return

    ideias_sel = st.session_state["ideias_selecionadas"]
    opcoes = {f"{i.get('eixo','?')} — {i.get('titulo','')}": i for i in ideias_sel}
    escolha = st.selectbox("Carrossel a animar:", list(opcoes.keys()), key="sel_animacao")
    ideia = opcoes[escolha]

    fidelidade = seletor_fidelidade("fidelidade_animacao")
    com_audio = st.checkbox("🎵 Trilha e efeitos sintetizados", value=True, key="anim_audio")
    texto_na_imagem = st.checkbox(
        "🅰️ O texto já está na arte (Flow)",
        value=True,
        key="anim_texto_na_imagem",
        help=(
            "Os prompts de imagem exigem o texto sobreposto na própria arte. "
            "Desmarque só quando os PNGs vierem sem texto (foto pura) — aí o "
            "renderer desenha o overlay."
        ),
    )

    brief = montar_brief(ideia, fidelidade=fidelidade, modo="vivo")
    avisos_brief = validar_brief(brief)
    for aviso in avisos_brief:
        st.warning(aviso)

    storyboard = montar_storyboard(brief, texto_na_imagem=texto_na_imagem)
    resumo = resumo_storyboard(storyboard)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slides", resumo["slides"])
    c2.metric("Duração", f"{resumo['duracao_total_s']}s")
    c3.metric("BPM", resumo["bpm"])
    c4.metric("Movimentos", ", ".join(f"{k}" for k in resumo["movimentos"]) or "—")
    for aviso in resumo["avisos"]:
        st.info(aviso)

    st.caption(
        f"Mood **{brief['trilha']['mood']}** · curva {brief['trilha']['curva']} · "
        f"overlay cortado em {sum(1 for s in storyboard['slides'] if s['overlay_cortado'])} slide(s)."
    )

    saida = st.session_state.get("video_gerado")
    col_render, col_video = st.columns([1, 2])

    with col_render:
        st.markdown("### ▶️ Renderizar")
        if st.button("🎬 Animar carrossel", type="primary", width="stretch", key="btn_animar"):
            if not ideias_sel:
                st.warning("Selecione uma ideia primeiro.")
            else:
                progresso = st.progress(0.0, text="Preparando frames…")
                with st.spinner("Renderizando o carrossel vivo…"):
                    resultado = renderizar_carrossel_vivo(
                        ideia,
                        storyboard,
                        saida=_caminho_saida(ideia),
                        com_audio=com_audio,
                        progresso=lambda i, n: progresso.progress(
                            i / n, text=f"Slide {i}/{n}"
                        ),
                    )
                    progresso.empty()
                if resultado.ok():
                    st.session_state["video_gerado"] = resultado.caminho_mp4
                    st.success(
                        f"✅ {resultado.frames} frames · {resultado.duracao_s}s · "
                        f"{resultado.caminho_mp4}"
                    )
                    for aviso in resultado.avisos or []:
                        st.info(aviso)
                    st.rerun()

        with st.expander("🎚️ Ajustes de trilha e movimento"):
            st.caption(
                "O mood e a curva vêm do eixo. Ajustar aqui vale para este vídeo "
                "apenas — o padrão do motor continua vindo do eixo."
            )
            st.json(
                {"trilha": brief["trilha"], "fps": storyboard["fps"],
                 "frames_beat": storyboard["frames_beat"]},
                expanded=False,
            )

    with col_video:
        st.markdown("### 🎞️ Resultado")
        if saida:
            st.video(saida)
            with open(saida, "rb") as f:
                st.download_button(
                    "⬇️ Baixar MP4",
                    data=f.read(),
                    file_name=str(saida).split("/")[-1],
                    mime="video/mp4",
                    width="stretch",
                )
            _avisar_rascunho()
        else:
            st.info("Renderize para ver o vídeo aqui.")
            _avisar_rascunho()


def _caminho_saida(ideia: dict):
    from carrossel_vivo import caminho_de_saida_padrao

    return caminho_de_saida_padrao(ideia.get("titulo", "carrossel"))


def _avisar_rascunho() -> None:
    """Deixa claro o que está sendo animado quando não há arte final."""
    st.caption(
        "⚠️ **Rascunho:** sem PNGs da geração na pasta de saída, o vídeo usa os "
        "slides do template local. Serve para validar o movimento e a sincronia — "
        "não é o arte final. Para animar o resultado do Google Flow, coloque os "
        "PNGs na pasta e renderize de novo."
    )
    if not FLOW_FOTOS:
        st.caption(
            "FLOW_FOTOS desligado: a fidelidade alta cai para média na geração "
            "de imagens, o que não afeta a animação, mas afeta a peça."
        )
