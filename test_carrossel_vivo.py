"""Testes do V9 — o carrossel vivo (Pillow + ffmpeg).

Os testes de renderização real são pulados quando não há ffmpeg no PATH: o
projeto precisa continuar testável numa máquina sem ffmpeg, e a animação é
opcional por princípio (o modo PNG não pode depender dela).
"""

import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image

import carrossel_vivo as cv
from brief import FPS, montar_brief, montar_storyboard
from config import FORMATO

LARGURA, ALTURA = FORMATO["largura"], FORMATO["altura"]
COM_FFMPEG = pytest.mark.skipif(
    shutil.which("ffmpeg") is None, reason="ffmpeg ausente: animação é opcional"
)

IDEIA = {
    "id": "ideia_video",
    "titulo": "Por que o filho explode depois da prova",
    "eixo": "Comportamental",
    "slides_sugeridos": [
        {"slide": 1, "tipo": "Capa", "texto": "Ele errou três questões e perdeu a prova"},
        {"slide": 2, "tipo": "Segunda Capa", "texto": "A culpa parece ser da prova"},
        {"slide": 3, "tipo": "Entrega", "texto": "Primeiro passo"},
        {"slide": 4, "tipo": "Entrega", "texto": "Segundo passo"},
        {"slide": 5, "tipo": "Entrega", "texto": "Terceiro passo"},
        {"slide": 6, "tipo": "Ponte", "texto": "Ensino individualizado"},
        {"slide": 7, "tipo": "Prova", "texto": "Fachada da unidade"},
        {"slide": 8, "tipo": "CTA", "texto": "Commente FOCO"},
    ],
}


@pytest.fixture
def storyboard():
    return montar_storyboard(montar_brief(IDEIA, modo="vivo"))


@pytest.fixture
def pngs(tmp_path):
    """Imagens sintéticas com gradiente — cor chapada não prova crop."""
    caminhos = []
    for n in range(1, 9):
        img = Image.new("RGB", (LARGURA, ALTURA))
        pixels = img.load()
        for y in range(0, ALTURA, 16):
            for x in range(0, LARGURA, 16):
                cor = ((x + n * 40) % 256, (y * 3) % 256, 190)
                for dy in range(16):
                    for dx in range(16):
                        if x + dx < LARGURA and y + dy < ALTURA:
                            pixels[x + dx, y + dy] = cor
        caminho = tmp_path / f"slide_{n:02d}.png"
        img.save(caminho)
        caminhos.append(str(caminho))
    return caminhos


@pytest.fixture
def storyboard_curto(storyboard):
    """Storyboard de 2 slides curtos — o render completo é lento de propósito."""
    for slide in storyboard["slides"][:2]:
        slide["animacao"]["frames"] = 30
        slide["animacao"]["duracao_s"] = 1.0
    curto = {**storyboard, "slides": storyboard["slides"][:2]}
    curto["total_frames"] = 60
    curto["duracao_total_s"] = 2.0
    return curto


# ─── Ambiente ────────────────────────────────────────────────────────────────

def test_ambiente_reporta_ffmpeg():
    # A função tem que responder mesmo sem ffmpeg — é o que a aba usa para avisar.
    assert isinstance(cv.ffmpeg_disponivel(), bool)
    assert isinstance(cv.ffmpeg_versao(), str)


def test_render_exige_imagem_por_slide(storyboard, tmp_path, pngs):
    with pytest.raises(ValueError, match="uma imagem por slide"):
        cv.renderizar(storyboard, pngs[:-1], tmp_path / "x.mp4")


# ─── Camadas ─────────────────────────────────────────────────────────────────

def test_fundo_estatico_nao_faz_trabalho(tmp_path, pngs):
    prep = cv.preparar_fundo(pngs[0], "estatico", 0.0)
    assert prep["movimento"] == "estatico"
    assert prep["img"].size == (LARGURA, ALTURA)
    assert cv.quadro_fundo(prep, 0.0) is prep["img"]


def test_ken_burns_muda_o_quadro(tmp_path, pngs):
    prep = cv.preparar_fundo(pngs[0], "ken_burns", 0.08)
    assert prep["img"].width > LARGURA
    inicio = cv.quadro_fundo(prep, 0.0)
    fim = cv.quadro_fundo(prep, 1.0)
    assert inicio.size == fim.size == (LARGURA, ALTURA)
    assert inicio.tobytes() != fim.tobytes()


def test_camada_de_texto_respeita_a_area_segura():
    camada = cv._camada_texto("Ele errou três questões e perdeu a prova inteira")
    assert camada.width <= LARGURA
    assert camada.height <= ALTURA


def test_camada_de_texto_vazia_e_transparente():
    assert cv._camada_texto("").width <= 1


def test_cor_de_contraste_depende_do_fundo():
    claro = Image.new("RGB", (LARGURA, ALTURA), (245, 240, 225))
    escuro = Image.new("RGB", (LARGURA, ALTURA), (20, 25, 40))
    assert cv._cor_de_contraste(claro) == "#0B1220"
    assert cv._cor_de_contraste(escuro) == "#FFFFFF"


def test_frame_always_has_the_size_of_the_video():
    # Um resize que arredonda pode devolver 1079px e o ffmpeg rejeita o pacote
    # inteiro com "Invalid buffer size". O guard é o que evita isso.
    fundo = Image.new("RGB", (LARGURA - 3, ALTURA + 7), (200, 200, 200))
    frame = cv._compor_frame(fundo, cv._camada_texto("Texto"), {}, 5.0, "ease_out_cubic")
    assert frame.size == (LARGURA, ALTURA)


def test_entrada_e_continua_e_texto_some_com_o_tempo():
    # Regressão do alfa em cache: aplicar opacidade na camada compartilhada
    # deixava o texto invisível a partir do segundo frame.
    fundo = Image.new("RGB", (LARGURA, ALTURA), (245, 240, 225))
    camada = cv._camada_texto("Texto que precisa continuar aparecendo", "#0B1220")
    slide = {"texto_na_imagem": False, "animacao": {"entrada": {"tipo": "fade_subida", "duracao_ms": 400}}}
    primeiro = cv._compor_frame(fundo, camada, slide, 0.0, "ease_out_cubic")
    depois = cv._compor_frame(fundo, camada, slide, 3.0, "ease_out_cubic")
    assert primeiro.tobytes() != depois.tobytes()
    assert camada.getchannel("A").getextrema()[1] == 255  # camada cacheada intacta


def test_overlay_nao_duplica_texto_quando_a_arte_ja_tem():
    # A arte do Google Flow já recebe o texto sobreposto (regra 8 dos prompts).
    # Redesenhar aqui duplicaria a frase no meio do vídeo.
    fundo = Image.new("RGB", (LARGURA, ALTURA), (245, 240, 225))
    camada = cv._camada_texto("Texto que já está na arte", "#0B1220")
    com_texto = cv._compor_frame(fundo, camada, {"texto_na_imagem": True}, 3.0, "ease_out_cubic")
    sem_texto = cv._compor_frame(fundo, camada, {"texto_na_imagem": False}, 3.0, "ease_out_cubic")
    assert com_texto.tobytes() == fundo.tobytes()
    assert sem_texto.tobytes() != fundo.tobytes()


def test_easing_respeita_faixa():
    for curva in ("ease_out_cubic", "ease_out_quart", "ease_in_out_quad", "linear"):
        assert cv._easing(0.0, curva) == 0.0
        assert cv._easing(1.0, curva) == 1.0
        assert cv._easing(2.0, curva) == 1.0  # clamp


# ─── Trilha ──────────────────────────────────────────────────────────────────

@COM_FFMPEG
def test_trilha_sintetizada_tem_a_duracao_do_video(storyboard, tmp_path):
    import wave

    caminho = cv.sintetizar_trilha(storyboard, tmp_path / "trilha.wav")
    with wave.open(caminho) as w:
        segundos = w.getnframes() / w.getframerate()
    esperado = storyboard["total_frames"] / storyboard["fps"]
    assert abs(segundos - esperado) < 0.1


@COM_FFMPEG
def test_trilha_nao_e_silencio(storyboard, tmp_path):
    import wave

    caminho = cv.sintetizar_trilha(storyboard, tmp_path / "trilha.wav")
    with wave.open(caminho) as w:
        amostras = w.readframes(w.getnframes())
    assert max(amostras) > 0  # trilha muda; vídeo sem som é pior que sem efeito


# ─── Render ──────────────────────────────────────────────────────────────────

@COM_FFMPEG
def test_render_gera_mp4_com_audio(storyboard_curto, tmp_path, pngs):
    import json as _json

    storyboard = storyboard_curto
    saida = tmp_path / "carrossel.mp4"
    trilha = cv.sintetizar_trilha(storyboard, tmp_path / "t.wav")
    resultado = cv.renderizar(storyboard, pngs[:2], saida, trilha=trilha)

    assert resultado.ok()
    assert resultado.frames == storyboard["total_frames"]
    assert saida.exists()

    info = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", str(saida)],
        capture_output=True, text=True, check=True,
    )
    dados = _json.loads(info.stdout)
    video = next(s for s in dados["streams"] if s["codec_type"] == "video")
    audio = next((s for s in dados["streams"] if s["codec_type"] == "audio"), None)

    assert video["width"] == LARGURA and video["height"] == ALTURA
    assert video["pix_fmt"] == "yuv420p"  # sem isso o Instagram recusa o arquivo
    assert audio is not None
    assert abs(float(dados["format"]["duration"]) - storyboard["duracao_total_s"]) < 0.5


@COM_FFMPEG
def test_render_sem_audio_funciona(storyboard_curto, tmp_path, pngs):
    resultado = cv.renderizar(
        storyboard_curto, pngs[:2], tmp_path / "mudo.mp4", com_audio=False
    )
    assert resultado.ok()
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(resultado.caminho_mp4)],
        capture_output=True, text=True, check=True,
    )
    assert "video" in info.stdout
    assert "audio" not in info.stdout


@COM_FFMPEG
def test_render_completo_do_fluxo(tmp_path):
    """O caminho que a aba usa: garantir PNGs + trilha + MP4."""
    saida = tmp_path / "saida" / "video.mp4"
    resultado = cv.renderizar_carrossel_vivo(
        IDEIA, montar_storyboard(montar_brief(IDEIA, modo="vivo")),
        saida=saida, diretorio_pngs=tmp_path / "pngs",
    )
    assert resultado.ok()
    assert Path(resultado.caminho_mp4).exists()


# ─── Metadados ───────────────────────────────────────────────────────────────

def test_descrever_resume_o_storyboard(storyboard):
    texto = cv.descrever(storyboard)
    assert "slides" in texto and "bpm" in texto


def test_json_do_storyboard_e_salvo(storyboard, tmp_path):
    import json

    caminho = cv.salvar_storyboard_json(storyboard, tmp_path / "sb.json")
    assert json.loads(Path(caminho).read_text(encoding="utf-8"))["fps"] == FPS


def test_caminho_de_saida_padrao(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    caminho = cv.caminho_de_saida_padrao("Post Teste / Com Acento")
    assert caminho.suffix == ".mp4"
    assert "post-teste" in caminho.name
