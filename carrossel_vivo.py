"""
carrossel_vivo.py — V9: o carrossel animado (o "botão Animar").

Pillow desenha os frames; o ffmpeg do sistema costura em MP4. Nenhuma
dependência Python nova — Pillow já é do projeto e o ffmpeg já está instalado.

Por que código e não um modelo de vídeo: modelo acerta a cena viva e erra o
tempo; código acerta o tempo ao frame e erra a cena. Carrossel de Instagram são
8 slides de 3 segundos com texto por cima e loop curto — tempo é o que importa.

Quatro invariantes, todas herdadas do storyboard e reconferidas aqui:

1. Tempo em frames inteiros. Nada de arredondar no meio da renderização.
2. Texto rasterizado **uma vez** por slide e reaproveitado com matriz de
   transformação. Recompor glifos a cada frame é lento e produz serrilhado.
3. Nada de modelo no caminho do render. Se o resultado está estranho, o bug é do
   spec ou do renderer — nunca do prompt.
4. MP4 sempre em `yuv420p`: sem isso o player do Instagram recusa o arquivo.
"""

import json
import math
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from brief import FPS, resumo_storyboard, validar_storyboard
from config import FORMATO
from image_utils import _load_font, create_slide_from_template

LARGURA, ALTURA = FORMATO["largura"], FORMATO["altura"]

# Área segura: o texto sobreposto vive entre estas faixas (config.FORMATO pede
# 30-50 palavras de roteiro e o overlay é curto). Animação que empurra o texto
# para fora disso quebra o enquadramento no feed.
AREA_SEGURA = {"topo": 260, "base": 1070, "largura": 920}


@dataclass
class ResultadoRender:
    """Saída de uma renderização, seja ela mp4, pngs ou só diagnóstico."""

    frames: int
    duracao_s: float
    caminho_mp4: str | None = None
    caminho_trilha: str | None = None
    avisos: list[str] | None = None

    def ok(self) -> bool:
        return bool(self.caminho_mp4)


# ─── Ambiente ────────────────────────────────────────────────────────────────

def ffmpeg_disponivel() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def _exigir_ffmpeg() -> None:
    if not ffmpeg_disponivel():
        raise RuntimeError(
            "ffmpeg/ffprobe não encontrados no PATH. O modo PNG continua "
            "funcionando sozinho — a animação é opcional por princípio."
        )


# ─── Fontes de imagem ────────────────────────────────────────────────────────

def pngs_do_carrossel(ideia: dict, diretorio: str | Path) -> list[str]:
    """
    Devolve os PNGs na ordem dos slides.

    Usa as imagens que o operador já tem (Flow, pasta da geração) e, faltando
    alguma, desenha o rascunho do template local. O rascunho serve para
    validar a animação — o usuário precisa saber que não é o arte final.
    """
    from templates import eixo_para_template

    diretorio = Path(diretorio)
    arquivos = sorted(diretorio.glob("*.png")) if diretorio.is_dir() else []
    slides = ideia.get("slides_sugeridos") or []

    total = len(slides) or len(arquivos) or 8
    ordenados: list[str] = []
    for numero in range(1, total + 1):
        candidato = None
        for arquivo in arquivos:
            if str(numero) in arquivo.stem:
                candidato = arquivo
                break
        if candidato is None and numero <= len(arquivos):
            candidato = arquivos[numero - 1]
        if candidato is None:
            texto = ""
            if numero <= len(slides):
                texto = slides[numero - 1].get("texto", "")
            png = create_slide_from_template(eixo_para_template(ideia.get("eixo", "Didático")), numero, texto)
            diretorio.mkdir(parents=True, exist_ok=True)
            destino = diretorio / f"slide_{numero:02d}.png"
            destino.write_bytes(png if isinstance(png, bytes) else png[0])
            candidato = destino
        ordenados.append(str(candidato))
    return ordenados


# ─── Camadas ─────────────────────────────────────────────────────────────────

def _easing(t: float, curva: str) -> float:
    """Curvas de entrada. ease_out domina a leitura; linear é para demo técnica."""
    t = max(0.0, min(1.0, t))
    if curva == "ease_out_cubic":
        return 1 - (1 - t) ** 3
    if curva == "ease_out_quart":
        return 1 - (1 - t) ** 4
    if curva == "ease_in_out_quad":
        return 2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
    return t


def _movimento(slide: dict) -> str:
    return (slide.get("animacao", {}).get("movimento") or {}).get("tipo", "estatico")


def _intensidade(slide: dict) -> float:
    return float((slide.get("animacao", {}).get("movimento") or {}).get("intensidade", 0) or 0)


def preparar_fundo(png: str, movimento: str, intensidade: float) -> dict:
    """
    Pré-computa o fundo de um slide uma única vez.

    Redimensionar a imagem a cada frame é o que torna o render lento: 960 frames
    com LANCZOS em 1080x1350 dá minutos. Aqui a imagem é escalada uma vez no
    tamanho máximo do movimento, e cada frame vira só um recorte — que é
    operação barata.
    """
    base = Image.open(png).convert("RGB")
    if movimento == "estatico" or intensidade <= 0:
        central = _centralizar(base)
        return {"img": central, "movimento": "estatico", "frames": 1}

    escala = 1.0 + intensidade
    largura = max(LARGURA, int(LARGURA * escala))
    altura = max(ALTURA, int(ALTURA * escala))
    return {"img": base.resize((largura, altura), Image.LANCZOS), "movimento": movimento}


def quadro_fundo(prep: dict, progresso: float) -> Image.Image:
    """Recorte do frame a partir do fundo pré-computado. Operação barata."""
    img = prep["img"]
    if prep["movimento"] == "estatico":
        return img
    max_x = max(0, img.width - LARGURA)
    max_y = max(0, img.height - ALTURA)
    if prep["movimento"] == "parallax":
        x = int(max_x * 0.8)
        y = int(max_y * 0.5)
    else:
        x = int(max_x * 0.5 * progresso)
        y = int(max_y * 0.5 * progresso)
    return img.crop((x, y, x + LARGURA, y + ALTURA))


def _centralizar(img: Image.Image) -> Image.Image:
    """Cobre o frame 4:5 mantendo proporção, cortando o excedente."""
    escala = max(LARGURA / img.width, ALTURA / img.height)
    nova = img.resize((max(1, int(img.width * escala)), max(1, int(img.height * escala))), Image.LANCZOS)
    esq = (nova.width - LARGURA) // 2
    topo = (nova.height - ALTURA) // 2
    return nova.crop((esq, topo, esq + LARGURA, topo + ALTURA))


def _cor_de_contraste(fundo: Image.Image) -> str:
    """
    Escolhe a cor do texto pela luminância de onde ele vai ser escrito.

    Slide da Ensina Mais é claro (creme, azul-claro) e slide de foto é escuro.
    Texto branco fixo some no slide claro — e some no ponto do vídeo onde o
    espectador está lendo, que é o pior lugar possível.
    """
    regiao = fundo.crop((0, ALTURA - 520, LARGURA, ALTURA - 120)).resize((1, 1))
    r, g, b = regiao.getpixel((0, 0))[:3]
    luminancia = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return "#0B1220" if luminancia > 0.55 else "#FFFFFF"


def _camada_texto(texto: str, cor: str = "#FFFFFF") -> Image.Image:
    """
    Rasteriza o overlay uma vez por slide, em RGBA.

    Escalar um RGBA com BICUBIC é visualmente superior a redesenhar glifos a
    cada frame, e é isso que mantém o texto nítido durante todo o movimento.
    """
    if not (texto or "").strip():
        return Image.new("RGBA", (1, 1), (0, 0, 0, 0))

    fonte = _load_font(72)
    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    palavras = texto.split()
    linhas: list[str] = []
    atual = ""
    for palavra in palavras:
        tentativa = f"{atual} {palavra}".strip()
        largura = dummy.textlength(tentativa, font=fonte)
        if largura <= AREA_SEGURA["largura"] or not atual:
            atual = tentativa
        else:
            linhas.append(atual)
            atual = palavra
    if atual:
        linhas.append(atual)

    altura_linha = 86
    altura = max(1, len(linhas) * altura_linha + 40)
    camada = Image.new("RGBA", (LARGURA, altura), (0, 0, 0, 0))
    desenho = ImageDraw.Draw(camada)
    y = 20
    for linha in linhas:
        largura_texto = desenho.textlength(linha, font=fonte)
        x = max(0, (LARGURA - largura_texto) / 2)
        desenho.text((x + 4, y + 5), linha, font=fonte, fill=(0, 0, 0, 170))
        desenho.text((x, y), linha, font=fonte, fill=cor)
        y += altura_linha
    return camada


def _compor_frame(
    fundo: Image.Image,
    texto_rgba: Image.Image,
    slide: dict,
    tempo_local: float,
    curva: str,
) -> Image.Image:
    """Aplica entrada ao texto e devolve o frame RGB pronto."""
    frame = fundo.convert("RGB")
    if frame.size != (LARGURA, ALTURA):
        # Defense em profundidade: um resize que arredonda pode devolver 1079px
        # e o ffmpeg rejeita o pacote inteiro ("Invalid buffer size"). Melhor
        # um resize a mais do que um vídeo que não sai.
        frame = frame.resize((LARGURA, ALTURA), Image.BICUBIC)
    if texto_rgba.width <= 1:
        return frame

    if slide.get("texto_na_imagem", True):
        # A arte já traz o texto (regra 8 dos prompts de imagem). Redesenhar
        # aqui duplicaria a frase no meio do vídeo.
        return frame

    entrada = slide.get("animacao", {}).get("entrada", {})
    duracao_ms = float(entrada.get("duracao_ms", 400))
    progresso = 1.0 if duracao_ms <= 0 else min(1.0, (tempo_local * 1000) / duracao_ms)
    e = _easing(progresso, curva)
    if e <= 0:
        return frame

    tipo = entrada.get("tipo", "fade_subida")
    deslocamento = int(40 * (1 - e))
    escala = 1.0 + 0.06 * (1 - e) if tipo == "zoom_saia" else 1.0

    camada = texto_rgba
    if escala != 1.0:
        w = max(1, int(camada.width * escala))
        h = max(1, int(camada.height * escala))
        camada = camada.resize((w, h), Image.BICUBIC)

    if tipo == "slide_esquerda":
        deslocamento = -int(60 * (1 - e))

    # Encosta o texto na base da área segura: ele desce até 1070 e nunca sobe
    # acima de 260, onde o slide já tem título. Push-lo ao topo colidia com o
    # cabeçalho e escondia o texto da própria régua.
    y = AREA_SEGURA["base"] - camada.height + deslocamento
    y = max(AREA_SEGURA["topo"], min(ALTURA - camada.height, y))
    x = max(0, min(LARGURA - camada.width, (LARGURA - camada.width) // 2))

    # A camada é cacheada por slide (rasterizada uma vez). Aplicar a opacidade
    # nela mesma deixaria o alfa em 0 para sempre depois do primeiro frame — o
    # texto sumia do vídeo inteiro. Copia e multiplica.
    if e < 1.0:
        camada = camada.copy()
        camada.putalpha(camada.getchannel("A").point(lambda a: int(a * e)))
    frame.paste(camada, (x, y), camada)
    return frame


# ─── Trilha ──────────────────────────────────────────────────────────────────

def sintetizar_trilha(storyboard: dict, caminho: str | Path) -> str:
    """
    Gera a trilha e os cues de áudio direto no numpy — sem arquivo externo.

    Não é música de produção: é um pad harmônico no grid de beats mais um blip
    por cue. Serve para validar a sincronia antes de gastar tempo com faixa
    licenciada, e para ter áudio quando não existe áudio.
    """
    import numpy as np

    _exigir_ffmpeg()
    fps = storyboard.get("fps", FPS)
    total_frames = int(storyboard.get("total_frames", 0))
    taxa = 22050
    total_amostras = int(total_frames / fps * taxa)
    audio = np.zeros(total_amostras, dtype=np.float64)

    # Pad: fundamental grave + quinta, com envelope suave e leve batimento.
    t = np.arange(total_amostras) / taxa
    batimento = 1.0 + 0.002 * np.sin(2 * math.pi * 2.0 * t)
    fundamental = 110.0 if storyboard.get("bpm", 100) <= 100 else 130.81
    pad = (
        0.18 * np.sin(2 * math.pi * fundamental * t * batimento)
        + 0.09 * np.sin(2 * math.pi * fundamental * 1.5 * t)
        + 0.05 * np.sin(2 * math.pi * fundamental * 2.0 * t)
    )
    audio += pad

    # Cues: um blip curto em cada tempo do beat grade.
    for slide in storyboard.get("slides", []):
        cue = (slide.get("audio") or {}).get("cue", "pad")
        if cue == "pad":
            continue
        inicio = int(float(slide["audio"]["tempo_s"]) * taxa)
        duracao = int(0.12 * taxa) if cue == "click" else int(0.28 * taxa)
        if inicio + duracao >= total_amostras:
            continue
        trecho = np.arange(duracao) / taxa
        freq = 880.0 if cue == "click" else 165.0
        env = np.exp(-trecho * (28 if cue == "click" else 9))
        audio[inicio:inicio + duracao] += 0.35 * env * np.sin(2 * math.pi * freq * trecho)

    # Ducking: a trilha abaixa onde o cue toca, senão o efeito é engolido — e
    # vídeo sem efeito audível parece vídeo sem som.
    for slide in storyboard.get("slides", []):
        inicio = int(float(slide["audio"]["tempo_s"]) * taxa)
        janela = int(0.35 * taxa)
        if inicio >= len(audio):
            continue
        audio[inicio:inicio + janela] *= 0.5

    pico = float(np.max(np.abs(audio))) or 1.0
    audio = audio / pico * 0.7
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    import wave

    pcm = (audio * 32767).astype("int16")
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(taxa)
        w.writeframes(pcm.tobytes())
    return str(caminho)


# ─── Render ──────────────────────────────────────────────────────────────────

def renderizar(
    storyboard: dict,
    pngs: list[str],
    saida: str | Path,
    trilha: str | Path | None = None,
    com_audio: bool = True,
    progresso=None,
) -> ResultadoRender:
    """
    Renderiza o storyboard em MP4.

    Os frames vão por pipe rawvideo direto para o ffmpeg — sem arquivos
    intermediários no disco, sem nome de frame para embolar na ordem, e sem
    milhares de PNGs ocupando o tmp.
    """
    _exigir_ffmpeg()
    avisos = validar_storyboard(storyboard)
    slides = storyboard.get("slides", [])
    if len(pngs) != len(slides):
        raise ValueError(
            f"{len(pngs)} imagens para {len(slides)} slides — o render exige uma "
            "imagem por slide, na ordem."
        )

    saida = Path(saida)
    saida.parent.mkdir(parents=True, exist_ok=True)
    # O ffmpeg roda com cwd num diretório temporário, então caminho relativo
    # resolveria lá dentro e o processo morria sem motivo aparente. Absoluto
    # sempre: é a diferença entre "não achou o arquivo" e "renderizou".
    saida = saida.resolve()
    fps = storyboard.get("fps", FPS)
    curva = "ease_out_cubic"

    # Camadas de texto: uma por slide, rasterizadas uma única vez.
    textos: list[Image.Image] = []

    caminho_trilha = str(Path(trilha).resolve()) if trilha else None
    if caminho_trilha and not Path(caminho_trilha).exists():
        # Melhor uma mensagem clara do que um ffmpeg que sai com 254 e log vazio.
        caminho_trilha = None
    # stderr vai para arquivo: o log do ffmpeg é a única pista quando o processo
    # morre no meio da renderização, e um BrokenPipeError sozinho não diz nada.
    log_ffmpeg = tempfile.NamedTemporaryFile(suffix=".log", delete=False)
    comando = [
        "ffmpeg", "-y", "-loglevel", "warning",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{LARGURA}x{ALTURA}", "-r", str(fps),
        "-i", "-",
    ]
    if com_audio and caminho_trilha and Path(caminho_trilha).exists():
        comando += ["-i", caminho_trilha, "-c:a", "aac", "-b:a", "192k"]
    comando += [
        # threads limitadas: o x264 sozinho abre uma thread por core e, num servidor
        # com pouca RAM livre, o encoder é o primeiro a ser morto.
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "veryfast",
        "-threads", "2",
        "-movflags", "+faststart", str(saida),
    ]

    inicio_total = 0
    # A cor do texto depende do fundo, e o fundo é o mesmo durante o slide
    # inteiro (só o crop muda): rasterizar por slide continua correto e basta.
    for png, slide in zip(pngs, slides, strict=True):
        fundo_ref = preparar_fundo(
            png,
            (slide.get("animacao", {}).get("movimento") or {}).get("tipo", "estatico"),
            float((slide.get("animacao", {}).get("movimento") or {}).get("intensidade", 0) or 0),
        )
        quadro_inicial = quadro_fundo(fundo_ref, 0.0)
        textos.append(_camada_texto(slide.get("texto_overlay", ""), _cor_de_contraste(quadro_inicial)))

    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.Popen(comando, stdin=subprocess.PIPE, cwd=tmp)
        try:
            for indice, slide in enumerate(slides):
                anim = slide.get("animacao", {})
                frames = int(anim.get("frames", 0))
                prep = preparar_fundo(pngs[indice], _movimento(slide), _intensidade(slide))
                for f in range(frames):
                    progresso_local = f / max(1, frames - 1)
                    tempo_local = f / fps
                    fundo = quadro_fundo(prep, progresso_local)
                    frame = _compor_frame(fundo, textos[indice], slide, tempo_local, curva)
                    proc.stdin.write(frame.tobytes())
                prep["img"].close()  # fecha antes do próximo slide: pico de memória
                inicio_total += frames
                if progresso:
                    progresso(indice + 1, len(slides))
            proc.stdin.close()
        except BrokenPipeError as erro:
            # ffmpeg morreu (parâmetro inválido, disco cheio). Sem isto o
            # processo fica esperando por um stdin que ninguém vai fechar.
            proc.kill()
            codigo = proc.wait()
            log_ffmpeg.close()
            raise RuntimeError(
                f"ffmpeg encerrou durante a renderização (código {codigo}; "
                f"negativo = morto por sinal, tipicamente OOM). Log:\n"
                + Path(log_ffmpeg.name).read_text(errors="replace")[-2000:]
            ) from erro
        finally:
            codigo = proc.wait()
    log_ffmpeg.close()
    if codigo != 0:
        raise RuntimeError(
            f"ffmpeg saiu com código {codigo}:\n"
            + Path(log_ffmpeg.name).read_text(errors="replace")[-2000:]
        )

    return ResultadoRender(
        frames=inicio_total,
        duracao_s=round(inicio_total / fps, 3),
        caminho_mp4=str(saida),
        caminho_trilha=caminho_trilha,
        avisos=avisos,
    )


def renderizar_carrossel_vivo(
    ideia: dict,
    storyboard: dict,
    saida: str | Path,
    diretorio_pngs: str | Path | None = None,
    trilha: str | Path | None = None,
    com_audio: bool = True,
    progresso=None,
) -> ResultadoRender:
    """
    Atalho do fluxo inteiro: garante as imagens, sintetiza a trilha e renderiza.

    `storyboard["modo"] == "png"` não impede o render — o usuário pode querer o
    vídeo mesmo assim. O que impede é a falta de ffmpeg, e aí o modo PNG segue
    funcionando sozinho.
    """
    _exigir_ffmpeg()
    saida = Path(saida)
    base_pngs = Path(diretorio_pngs) if diretorio_pngs else saida.parent / "pngs"
    pngs = pngs_do_carrossel(ideia, base_pngs)

    trilha_caminho = Path(trilha).resolve() if trilha else None
    if trilha_caminho is None and com_audio:
        trilha_caminho = Path(sintetizar_trilha(storyboard, saida.with_suffix(".wav")))

    return renderizar(
        storyboard, pngs, saida, trilha=trilha_caminho, com_audio=com_audio, progresso=progresso
    )


def descrever(storyboard: dict) -> str:
    """Resumo textual do storyboard, para log e para a interface."""
    r = resumo_storyboard(storyboard)
    linhas = [
        f"{r['slides']} slides · {r['duracao_total_s']}s · {r['bpm']} bpm",
        "movimentos: " + ", ".join(f"{k}×{v}" for k, v in r["movimentos"].items()),
    ]
    linhas += [f"⚠️ {a}" for a in r.get("avisos", [])]
    return "\n".join(linhas)


def salvar_storyboard_json(storyboard: dict, caminho: str | Path) -> str:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(caminho)


def caminho_de_saida_padrao(titulo: str) -> Path:
    """Pasta de saída datada, no padrão das gerações manuais do projeto."""
    from datetime import datetime

    from acervo import slugify

    pasta = Path(f"{datetime.now().strftime('%d-%m-%Y')}_animado")
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta / f"{slugify(titulo) or 'carrossel'}.mp4"


def ffmpeg_versao() -> str:
    """Versão do ffmpeg, para diagnóstico na interface."""
    if not shutil.which("ffmpeg"):
        return "não encontrado"
    try:
        saida = subprocess.run(
            ["ffmpeg", "-version"], capture_output=True, text=True, timeout=10
        ).stdout
        return saida.splitlines()[0]
    except (OSError, subprocess.SubprocessError, IndexError):
        return "desconhecida"
