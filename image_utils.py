"""
image_utils.py — Geração e composição de imagens HD para os slides do carrossel.

Motor visual v2 (Estilo Editorial / AutoFlow HD):
- Renderização com supersampling 2x e downscale LANCZOS para 1080×1350 px
- Fotos reais com EXIF corrigido, auto-contrast, crop com viés ao terço superior
  e nitidez aplicada à foto (não ao resultado final)
- Scrim e glassmorphism adaptativos à luminância da foto de base
- Grifo marca-texto com match por fronteira de palavra; frases opcionais via campo
  "destaques" no JSON de prompts
- Integração direta com o catálogo fotográfico real da unidade (refs/catalogo.json)
- Layouts específicos por função de lâmina (1 a 8):
  * Slides 1, 4, 5: Fotografia real da unidade intocada + scrim/card editorial + ícones line-art
  * Slide 2: Segunda Capa em Brand Blue (#007799) com moldura flutuante, grifo e ícones em círculos
  * Slide 3: Entrega / Comparativo com cards flutuantes e destaque na solução ativa
  * Slide 6: Ponte / Infográfico 2×2 com fotos reais da unidade + selo Rua Coelho Lisboa, 783 • Tatuapé
  * Slide 7: Prova Social na Fachada real intocada + card Caso Real • Ensino Fundamental
  * Slide 8: CTA Final com arco Brand Blue, logo oficial, botão Action Green (#58B947) WhatsApp e barra Direct/Save
- Preserva integralmente a API pública (fit_slide_text, add_text_overlay, create_slide_from_template,
  generate_all_slides) e adiciona render_carousel_from_prompts para renderizar direto do JSON/txt do Flow.
"""

from __future__ import annotations

import logging
import math
import os
import re
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Literal, overload

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageOps

from config import FONTES, FORMATO, PROJECT_DIR, TAG_NAVEGACAO, UNIDADE
from refs_catalog import REFS_DIR, arquivos
from templates import TEMPLATES, SlideEstrutura

logger = logging.getLogger(__name__)

# ─── Layout do slide 1080×1350 (px) ───────────────────────────────────────────
_TEXTO_Y_INI = 260                     # início da área do texto principal
_TEXTO_Y_FIM = 1070                    # fim (deixa folga antes do CTA em h-210)
_TEXTO_LARGURA = 920                   # 1080 - 2×80 de margem
_ENTRELINHAS = 14                      # espaçamento extra entre linhas

# Escada de auto-redução da fonte principal (P1)
_LADDER_FONT_MAIN = (60, 54, 48, 42, 36, 30)

# Supersampling 2x para anti-aliasing perfeito em curvas, sombras e ícones
_SCALE = 2
_W2, _H2 = FORMATO["largura"] * _SCALE, FORMATO["altura"] * _SCALE

# Paleta oficial Ensina Mais Tatuapé
HEX_BRAND_BLUE = "#007799"
HEX_DARK_NAVY = "#1E293B"
HEX_ACTION_GREEN = "#58B947"
HEX_YELLOW = "#FFC20E"
HEX_ORANGE = "#F58220"
HEX_BG_SOFT = "#F7F9FF"
HEX_PASTEL_ORANGE = "#FFEDD5"
HEX_PASTEL_BLUE = "#E0F2FE"
HEX_PASTEL_ROSE = "#FFE4E6"
HEX_PASTEL_GREEN = "#ECFCCB"
HEX_WHITE = "#FFFFFF"


# ─── Carregamento de Fonte ────────────────────────────────────────────────────

@lru_cache(maxsize=64)
def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Tenta carregar uma fonte TrueType da lista em FONTES (config.py).
    Retorna a fonte padrão do Pillow se todas falharem.
    """
    for path in FONTES:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


# ─── Word-wrap correto (em pixels) ───────────────────────────────────────────

def _wrap_text_pixels(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width_px: int,
) -> list[str]:
    """
    Quebra o texto em linhas que cabem dentro de max_width_px.
    Usa draw.textlength() para medir a largura real em pixels de cada linha,
    garantindo que o wrapping seja correto independente do tamanho da fonte.
    """
    words = text.split()
    lines: list[str] = []
    current: list[str] = []

    for word in words:
        candidate = " ".join(current + [word])
        try:
            width = draw.textlength(candidate, font=font)
        except AttributeError:
            width = draw.textsize(candidate, font=font)[0]  # type: ignore[attr-defined]

        if width <= max_width_px:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
            current = [word]

    if current:
        lines.append(" ".join(current))

    return lines


def _measure_lines(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    spacing: int,
) -> tuple[list[int], int]:
    """Altura de cada linha e altura total do bloco (com espaçamento)."""
    heights: list[int] = []
    for line in lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=font)
            heights.append(int(bbox[3] - bbox[1]))
        except AttributeError:
            heights.append(70)
    total = sum(heights) + spacing * max(0, len(lines) - 1)
    return heights, total


# ─── Ajuste automático do texto principal (P1) ────────────────────────────────

def fit_slide_text(
    texto: str,
    max_width: int = _TEXTO_LARGURA,
    avail_height: int = _TEXTO_Y_FIM - _TEXTO_Y_INI,
) -> dict:
    """
    Escolhe o maior tamanho de fonte da escada em que o texto, com
    word-wrap, cabe na área útil do slide.

    Returns:
        dict com font, font_size, lines, block_height, auto_shrunk,
        truncated e dropped (linhas cortadas).
    """
    meas = ImageDraw.Draw(Image.new("RGB", (8, 8)))

    if not texto.strip():
        return {
            "font": _load_font(_LADDER_FONT_MAIN[0]),
            "font_size": _LADDER_FONT_MAIN[0],
            "lines": [],
            "block_height": 0,
            "auto_shrunk": False,
            "truncated": False,
            "dropped": 0,
        }

    for size in _LADDER_FONT_MAIN:
        font = _load_font(size)
        lines = _wrap_text_pixels(meas, texto, font, max_width)
        _, total = _measure_lines(meas, lines, font, _ENTRELINHAS)
        if total <= avail_height:
            return {
                "font": font,
                "font_size": size,
                "lines": lines,
                "block_height": total,
                "auto_shrunk": size != _LADDER_FONT_MAIN[0],
                "truncated": False,
                "dropped": 0,
            }

    # Nem no menor tamanho coube: trunca o que passa e sinaliza.
    size = _LADDER_FONT_MAIN[-1]
    font = _load_font(size)
    lines = _wrap_text_pixels(meas, texto, font, max_width)
    heights, _ = _measure_lines(meas, lines, font, _ENTRELINHAS)

    kept: list[str] = []
    used = 0
    for line, h_line in zip(lines, heights, strict=True):
        if kept and used + h_line > avail_height:
            break
        kept.append(line)
        used += h_line + _ENTRELINHAS

    dropped = len(lines) - len(kept)
    if dropped and kept:
        kept[-1] = kept[-1].rstrip() + "…"
    logger.warning(
        "Slide truncado: %d de %d linhas couberam (texto de %d caracteres).",
        len(kept), len(lines), len(texto),
    )
    return {
        "font": font,
        "font_size": size,
        "lines": kept,
        "block_height": used,
        "auto_shrunk": True,
        "truncated": bool(dropped),
        "dropped": dropped,
    }


# ─── Texto sobreposto numa imagem existente (P2) ─────────────────────────────

def add_text_overlay(
    image_bytes: bytes,
    text: str,
    font_size: int = 48,
    position: str = "center",
) -> bytes:
    """
    Adiciona texto sobreposto em PT-BR numa imagem existente, com quebra de
    linha automática (o texto nunca ultrapassa a largura da imagem).
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size

    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    font = _load_font(font_size)

    padding = 40
    max_text_width = width - padding * 2 - 40
    lines = _wrap_text_pixels(draw, text, font, max_text_width)
    joined = "\n".join(lines)

    try:
        bbox = draw.multiline_textbbox((0, 0), joined, font=font, spacing=10)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        heights, total = _measure_lines(draw, lines, font, 10)
        text_height = total
        text_width = max(
            (draw.textlength(ln, font=font) for ln in lines), default=0
        )

    if position == "center":
        y = (height - text_height) // 2
    elif position == "bottom":
        y = height - text_height - padding * 2
    else:
        y = padding
    x = (width - text_width) // 2

    bg_pad = 24
    bg_box = [
        x - bg_pad,
        y - bg_pad,
        x + text_width + bg_pad,
        y + text_height + bg_pad,
    ]
    draw.rounded_rectangle(bg_box, radius=18, fill=(255, 255, 255, 242))
    draw.multiline_text((x, y), joined, font=font, fill=(0, 119, 153, 255),
                        spacing=10, align="center")

    result = Image.alpha_composite(img, txt_layer)

    output = BytesIO()
    result.convert("RGB").save(output, format="PNG", quality=95)
    return output.getvalue()


def _fundo_e_claro(img: Image.Image) -> bool:
    """Diz se a base do slide é clara (luminância média alta)."""
    w, h = img.size
    amostras = [0.35, 0.5, 0.65]
    lums = []
    for fracao in amostras:
        regiao = img.crop((0, int(h * fracao), w, int(h * fracao) + 8)).convert("RGB").resize((1, 1))
        r, g, b = regiao.getpixel((0, 0))
        lums.append((0.299 * r + 0.587 * g + 0.114 * b) / 255)
    return (sum(lums) / len(lums)) > 0.55


# ─── Primitivas Gráficas HD (Supersampling 2x) ────────────────────────────────

def _hex_rgba(h: str, alpha: int = 255) -> tuple[int, int, int, int]:
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), alpha)


def _luminancia(img: Image.Image) -> float:
    """Luminância média normalizada (0–1) de uma imagem RGBA/RGB."""
    amostra = img.convert("RGB").resize((6, 8))
    lums = [
        (0.299 * r + 0.587 * g + 0.114 * b) / 255
        for r, g, b in amostra.getdata()
    ]
    return sum(lums) / len(lums)


def _cover_crop(img_path: Path, target_w: int, target_h: int) -> Image.Image:
    try:
        img = Image.open(img_path)
        img = ImageOps.exif_transpose(img).convert("RGB")
        img = ImageOps.autocontrast(img, cutoff=1).convert("RGBA")
        scale = max(target_w / img.width, target_h / img.height)
        nw, nh = max(1, int(img.width * scale)), max(1, int(img.height * scale))
        img = img.resize((nw, nh), Image.LANCZOS)
        left = (nw - target_w) // 2
        # Viés para o terço superior: em fotos de cena, rostos ficam acima do centro geométrico
        top = int((nh - target_h) * 0.35)
        crop = img.crop((left, top, left + target_w, top + target_h))
        # Nitidez aplicada à foto (em espaço 2x), não ao resultado final composto
        return crop.filter(ImageFilter.UnsharpMask(radius=2.0, percent=70, threshold=3))
    except Exception:
        return Image.new("RGBA", (target_w, target_h), _hex_rgba(HEX_BRAND_BLUE))


def _selecionar_foto_cena(chave_cena: str, indice_variacao: int = 0) -> Path:
    """Escolhe um arquivo real do catálogo refs/catalogo.json para a cena."""
    lista = arquivos(chave_cena)
    if lista:
        return lista[indice_variacao % len(lista)]
    fallback = REFS_DIR / "Fachada.png"
    if fallback.is_file():
        return fallback
    for padrao in ("*.jpg", "*.png"):
        encontrados = sorted(REFS_DIR.glob(padrao))
        if encontrados:
            return encontrados[0]
    return fallback


def _desenhar_scrim(
    base: Image.Image,
    start_frac: float,
    rgb: tuple[int, int, int],
    alpha_max: int,
    expo: float = 1.3,
) -> None:
    """Gradiente vertical suave (sem banding) do transparente até alpha_max."""
    y0 = int(_H2 * start_frac)
    h = _H2 - y0
    rampa = Image.new("L", (1, 256))
    pixels = rampa.load()
    for i in range(256):
        pixels[0, i] = int(alpha_max * ((i / 255) ** expo))
    alpha = rampa.resize((_W2, h), Image.BILINEAR)
    scrim = Image.new("RGBA", (_W2, h), (*rgb, 0))
    scrim.putalpha(alpha)
    base.alpha_composite(scrim, (0, y0))


def _scrim_alpha_adaptativo(lum: float) -> int:
    """Foto clara pede scrim mais forte (senão o card branco "flutua" sem contraste);
    foto escura pede mais leve (senão vira mancha preta e mata a imagem)."""
    return int(max(95.0, min(205.0, 100 + 130 * lum)))


def _glass_fill_radial(
    base: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    rgb: tuple[int, int, int],
    center_alpha: int = 245,
    edge_alpha: int = 25,
) -> None:
    """Preenchimento do card de vidro com degradê de BORDA (retangular): platô
    opaco em ~70% do centro — onde o texto fica — e fade até quase transparência
    total apenas na faixa periférica, de todos os lados."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    depth = 0.14  # fração da meia-dimensão ocupada pelo fade

    def _alpha_na_distancia(d: float) -> int:
        t = min(1.0, max(0.0, d / depth))
        curve = t * t * (3.0 - 2.0 * t)  # smoothstep
        return int(edge_alpha + (center_alpha - edge_alpha) * curve)

    ramp_x = Image.new("L", (w, 1))
    px = ramp_x.load()
    for xx in range(w):
        px[xx, 0] = _alpha_na_distancia(min(xx, w - 1 - xx) / max(1, w - 1) * 0.5)
    ramp_y = Image.new("L", (1, h))
    py = ramp_y.load()
    for yy in range(h):
        py[0, yy] = _alpha_na_distancia(min(yy, h - 1 - yy) / max(1, h - 1) * 0.5)
    grad = ImageChops.darker(ramp_x.resize((w, h)), ramp_y.resize((w, h)))
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    card = Image.new("RGBA", (w, h), (*rgb, 0))
    card.putalpha(ImageChops.multiply(grad, mask))
    base.alpha_composite(card, (x0, y0))


def _draw_glass_sheen(base: Image.Image, box: tuple[int, int, int, int], radius: int) -> None:
    """Reflexo diagonal (brilho de chapa de vidro) sobre o card translúcido."""
    x0, y0, x1, y1 = box
    w, h = x1 - x0, y1 - y0
    rampa = Image.new("L", (64, 64))
    px = rampa.load()
    for yy in range(64):
        for xx in range(64):
            t = xx / 63 * 0.6 + yy / 63 * 0.4
            px[xx, yy] = int(85 * max(0.0, 1.0 - t * 1.5))
    grad = rampa.resize((w, h), Image.BILINEAR)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=255)
    sheen = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    sheen.putalpha(ImageChops.multiply(grad, mask))
    base.alpha_composite(sheen, (x0, y0))


def _draw_rounded_card_with_shadow(
    base: Image.Image,
    box: tuple[int, int, int, int],
    radius: int,
    fill: tuple[int, int, int, int],
    shadow_alpha: int = 38,
    shadow_blur: int = 26,
    shadow_offset_y: int = 12,
    outline: tuple[int, int, int, int] | None = None,
    outline_width: int = 0,
    glass: bool = False,
    glass_blur: int = 18,
) -> None:
    x0, y0, x1, y1 = [v * _SCALE for v in box]
    r = radius * _SCALE
    blur = shadow_blur * _SCALE
    off_y = shadow_offset_y * _SCALE

    if shadow_alpha > 0:
        shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
        s_draw = ImageDraw.Draw(shadow)
        s_draw.rounded_rectangle(
            [x0 + 6 * _SCALE, y0 + off_y, x1 - 6 * _SCALE, y1 + off_y],
            radius=r,
            fill=(15, 23, 42, shadow_alpha),
        )
        shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
        base.alpha_composite(shadow)

    if glass:
        # Glassmorphism: blur da região do fundo + tint branco mais forte sobre áreas escuras
        region = base.crop((x0, y0, x1, y1)).filter(ImageFilter.GaussianBlur(glass_blur * _SCALE))
        lum = _luminancia(region)
        tint_strength = 0.10 + 0.14 * (1.0 - lum)
        tinted = Image.blend(region, Image.new("RGBA", region.size, (255, 255, 255, 255)), tint_strength)
        mask = Image.new("L", region.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle(
            [0, 0, region.width - 1, region.height - 1], radius=r, fill=255
        )
        layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        layer.paste(tinted, (x0, y0), mask)
        base.alpha_composite(layer)
        # Centro quase opaco (legibilidade); o fade de transparência fica só na
        # faixa das bordas (ver _glass_fill_radial)
        fill = (*fill[:3], 248)
        if outline is None:
            outline = (255, 255, 255, 190)
            outline_width = 3

    if glass:
        _glass_fill_radial(base, (x0, y0, x1, y1), r, fill[:3], center_alpha=250, edge_alpha=48)

    card_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    c_draw = ImageDraw.Draw(card_layer)
    c_draw.rounded_rectangle(
        [x0, y0, x1, y1],
        radius=r,
        fill=None if glass else fill,
        outline=outline,
        width=outline_width * _SCALE if outline else 0,
    )
    base.alpha_composite(card_layer)

    if glass:
        _draw_glass_sheen(base, (x0, y0, x1, y1), r)


_STOPWORDS_GRIFO = frozenset({
    "a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "da", "do", "das",
    "dos", "em", "no", "na", "nos", "nas", "num", "numa", "para", "pra", "pro",
    "por", "com", "sem", "que", "e", "é", "se", "ao", "aos", "à", "às", "entre",
    "mais", "menos", "muito", "muita", "quando", "como", "onde", "qual", "quais",
    "ser", "são", "está", "estão", "foi", "será", "tem", "não", "sim", "ou",
})


def _auto_highlight_phrases(text: str) -> list[str]:
    """Detecta 1–2 expressões-chave do texto para grifo marca-texto, ignorando stopwords."""
    palavras = text.strip().split()
    if not palavras:
        return []
    limpas = [w.strip(".,!?:;\"'") for w in palavras]
    caps = [w for w in limpas if len(w) >= 4 and w.isupper()]
    if caps:
        return caps[:2]

    conteudo = [i for i, w in enumerate(limpas) if w and w.lower() not in _STOPWORDS_GRIFO]
    if not conteudo:
        return []
    pega = conteudo[-1:]
    anterior = conteudo[-2] if len(conteudo) >= 2 else None
    if anterior is not None and anterior == pega[0] - 1:
        dupla = f"{limpas[anterior]} {limpas[pega[0]]}"
        if len(dupla) <= 18:
            pega = [anterior, pega[0]]
    return [" ".join(limpas[i] for i in pega)]


def _highlight_spans(line: str, phrases: list[str]) -> list[tuple[int, int]]:
    """
    Spans de caracteres em `line` que merecem grifo. Casa a frase inteira dentro
    da linha, o prefixo da frase terminando na quebra e o sufixo continuando no
    início da linha seguinte (frases que atravessam o word-wrap).
    """
    words = [
        (m.start(), m.end(), m.group().strip(".,!?:;\"'").lower())
        for m in re.finditer(r"\S+", line)
    ]
    n = len(words)
    spans: list[tuple[int, int]] = []
    for p in phrases:
        pws = p.lower().split()
        L = len(pws)
        if not L or not n:
            continue
        for i in range(n):
            k = 0
            while i + k < n and k < L and words[i + k][2] == pws[k]:
                k += 1
            if k and (k == L or i + k == n):
                spans.append((words[i][0], words[i + k - 1][1]))
        for j in range(1, L):  # continuação de frase quebrada na linha anterior
            k = 0
            while k < n and j + k < L and words[k][2] == pws[j + k]:
                k += 1
            if k and j + k == L and k <= n:
                spans.append((words[0][0], words[k - 1][1]))
    return spans


# ─── Tipografia editorial (grade, kicker, baseline uniforme) ─────────────────

_MARGEM = 96                                   # margem da grade (1x)
_LARGURA_UTIL = FORMATO["largura"] - 2 * _MARGEM  # 888 px
_Y_BASE = 1080                                 # base da área segura de texto
_Y_RODAPE = 1284                               # baseline do rodapé de série
_PAD_CARD = 44                                 # padding interno dos cards
_TIPO_KICKER = 19


def _linhas_de_texto(
    draw: ImageDraw.ImageDraw,
    texto: str,
    fonte: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    largura_px: int,
) -> list[str]:
    """Quebra por parágrafo (\\n) respeitando a largura real em pixels."""
    linhas: list[str] = []
    for paragrafo in texto.split("\n"):
        paragrafo = re.sub(r"[ \t]+", " ", paragrafo).strip()
        if paragrafo:
            linhas.extend(_wrap_text_pixels(draw, paragrafo, fonte, largura_px))
    return linhas


def _medir_bloco(
    draw: ImageDraw.ImageDraw,
    texto: str,
    largura_px: int,
    max_h_px: int,
    size: int,
    min_size: int,
    leading: float,
    max_lines: int | None = None,
) -> tuple[int, ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], bool, bool, int]:
    """Escolhe o maior corpo da escada em que o bloco cabe.

    A altura é calculada com entrelinha constante (`size × leading`) e métricas
    da fonte, não com a altura de tinta de cada linha: acentos e descendentes
    deixam de empurrar a linha seguinte e as baselines ficam regulares.
    """
    escada = list(range(size, min_size - 1, -4)) or [min_size]
    for tam in escada:
        fonte = _load_font(tam * _SCALE)
        linhas = _linhas_de_texto(draw, texto, fonte, largura_px)
        if max_lines and len(linhas) > max_lines:
            continue
        asc, desc = fonte.getmetrics()
        entrelinha = int(round(tam * leading * _SCALE))
        bloco = asc + desc + entrelinha * (len(linhas) - 1)
        if bloco <= max_h_px:
            return tam, fonte, linhas, tam != size, False, 0

    # Nem no menor corpo coube: trunca sinalizando quantas linhas caíram.
    tam = escada[-1]
    fonte = _load_font(tam * _SCALE)
    linhas = _linhas_de_texto(draw, texto, fonte, largura_px)
    asc, desc = fonte.getmetrics()
    entrelinha = int(round(tam * leading * _SCALE))
    mantidas: list[str] = []
    usado = asc + desc
    for linha in linhas:
        if mantidas and usado + entrelinha > max_h_px:
            break
        mantidas.append(linha)
        usado += entrelinha
    cortadas = len(linhas) - len(mantidas)
    if cortadas and mantidas:
        mantidas[-1] = mantidas[-1].rstrip(" .,;:") + "…"
    return tam, fonte, mantidas, True, bool(cortadas), cortadas


def _texto_com_tracking(
    draw: ImageDraw.ImageDraw,
    x: int,
    baseline: int,
    texto: str,
    fonte: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    cor: tuple,
    tracking: int,
) -> int:
    """Escreve caixa alta espaçada (tracking) e devolve a largura usada em px."""
    cursor = x
    for caractere in texto:
        draw.text((cursor, baseline), caractere, font=fonte, fill=cor, anchor="ls")
        cursor += draw.textlength(caractere, font=fonte) + tracking
    return int(cursor - tracking - x) if texto else 0


def _draw_kicker(
    base: Image.Image,
    texto: str,
    x: int,
    baseline: int,
    *,
    color: str = HEX_BRAND_BLUE,
    size: int = _TIPO_KICKER,
    tracking: float = 2.4,
    rule: bool = True,
    rule_w: int = 26,
    rule_color: str | None = None,
) -> int:
    """Sobrancelha editorial: filete curto + caixa alta espaçada.

    É o elemento que dá hierarquia à lâmina (olho → sobrancelha → manchete) sem
    gastar espaço vertical; devolve a largura total ocupada.
    """
    draw = ImageDraw.Draw(base)
    fonte = _load_font(size * _SCALE)
    cursor = x * _SCALE
    if rule:
        largura_filete = rule_w * _SCALE
        draw.line(
            [(cursor, baseline * _SCALE), (cursor + largura_filete, baseline * _SCALE)],
            fill=_hex_rgba(rule_color or color),
            width=2 * _SCALE,
        )
        cursor += largura_filete + 12 * _SCALE
    largura = _texto_com_tracking(
        draw, int(cursor), baseline * _SCALE, texto.upper(), fonte, _hex_rgba(color), int(tracking * _SCALE)
    )
    return int((cursor + largura) / _SCALE - x)


def _draw_text_block(
    base: Image.Image,
    texto: str,
    box: tuple[int, int, int, int],
    *,
    align: str = "left",
    size: int = 58,
    min_size: int = 30,
    color: str = HEX_BRAND_BLUE,
    highlight_phrases: list[str] | None = None,
    highlight_color: str = HEX_YELLOW,
    leading: float = 1.14,
    uppercase: bool = False,
    vertical: str = "top",
    max_lines: int | None = None,
) -> dict:
    """Bloco de texto com grade tipográfica de verdade.

    Entrelinha constante, linhas assentadas na mesma baseline, grifo de canto
    quase reto (marca-texto, não pílula) e alinhamento à esquerda (padrão
    editorial) ou ao centro. Auto-reduz o corpo e trunca avisando no retorno.
    """
    draw = ImageDraw.Draw(base)
    texto = re.sub(r"[ \t]+", " ", (texto or "").strip())
    if uppercase:
        texto = texto.upper()
    x0, y0, x1, y1 = [int(v * _SCALE) for v in box]
    if not texto:
        return {"font_size": size, "auto_shrunk": False, "truncated": False, "dropped": 0, "lines": 0}

    tam, fonte, linhas, auto, truncado, cortadas = _medir_bloco(
        draw, texto, x1 - x0, y1 - y0, size, min_size, leading, max_lines
    )
    asc, desc = fonte.getmetrics()
    entrelinha = int(round(tam * leading * _SCALE))
    bloco = asc + desc + entrelinha * (len(linhas) - 1)

    if vertical == "center":
        baseline = y0 + max(0, (y1 - y0 - bloco) // 2) + asc
    elif vertical == "bottom":
        baseline = y1 - desc - entrelinha * (len(linhas) - 1)
    else:
        baseline = y0 + asc

    anchor = "ls" if align == "left" else "ms"
    x = x0 if align == "left" else (x0 + x1) // 2
    frases = [
        p.lower()
        for p in (
            highlight_phrases if highlight_phrases is not None else _auto_highlight_phrases(texto)
        )
        if p
    ]

    for linha in linhas:
        bbox = draw.textbbox((x, baseline), linha, font=fonte, anchor=anchor)
        for s0, s1 in _highlight_spans(linha, frases):
            inicio = bbox[0] + draw.textlength(linha[:s0], font=fonte)
            fim = inicio + draw.textlength(linha[s0:s1], font=fonte)
            draw.rounded_rectangle(
                [
                    inicio - 9 * _SCALE,
                    bbox[1] - 3 * _SCALE,
                    fim + 9 * _SCALE,
                    bbox[3] + 4 * _SCALE,
                ],
                radius=3 * _SCALE,
                fill=_hex_rgba(highlight_color),
            )
        draw.text((x, baseline), linha, font=fonte, fill=_hex_rgba(color), anchor=anchor)
        baseline += entrelinha

    return {
        "font_size": tam,
        "auto_shrunk": auto,
        "truncated": truncado,
        "dropped": cortadas,
        "lines": len(linhas),
    }


def _draw_centered_multiline(
    base: Image.Image,
    text: str,
    center_x: int,
    start_y: int,
    max_w: int,
    max_h: int,
    initial_font_size: int,
    color: str,
    highlight_phrases: list[str] | None = None,
    highlight_color: str = HEX_YELLOW,
    line_spacing: int = 16,
    vertical_center: bool = False,
) -> dict:
    """Compatibilidade: mesma assinatura antiga, agora sobre `_draw_text_block`."""
    leading = 1.0 + (line_spacing / max(1, initial_font_size))
    return _draw_text_block(
        base,
        text,
        (center_x - max_w // 2, start_y, center_x + max_w // 2, start_y + max_h),
        align="center",
        size=initial_font_size,
        min_size=26,
        color=color,
        highlight_phrases=highlight_phrases,
        highlight_color=highlight_color,
        leading=leading,
        vertical="center" if vertical_center else "top",
    )


def _gradiente_vertical(cor_topo: str, cor_base: str) -> Image.Image:
    """Fundo com gradiente vertical sutil — profundidade sem parecer plástico."""
    c1 = _hex_rgba(cor_topo)[:3]
    c2 = _hex_rgba(cor_base)[:3]
    faixa = Image.new("RGB", (1, _H2))
    px = faixa.load()
    for y in range(_H2):
        t = y / max(1, _H2 - 1)
        px[0, y] = tuple(int(a + (b - a) * t) for a, b in zip(c1, c2, strict=True))
    return faixa.resize((_W2, _H2), Image.BILINEAR).convert("RGBA")


def _cor_sobre_regiao(
    base: Image.Image,
    box: tuple[int, int, int, int],
    cor_escura: str = HEX_DARK_NAVY,
    cor_clara: str = HEX_WHITE,
) -> tuple[int, int, int, int]:
    """Cor de texto que sobrevive ao fundo real daquela faixa da lâmina."""
    regiao = base.crop([int(v * _SCALE) for v in box]).convert("RGB").resize((1, 1))
    r, g, b = regiao.getpixel((0, 0))
    lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255
    return _hex_rgba(cor_clara if lum < 0.55 else cor_escura)


def _draw_rodape(base: Image.Image, slide_num: int, total: int) -> None:
    """Assinatura de série: @ da unidade + índice da lâmina, à esquerda."""
    draw = ImageDraw.Draw(base)
    cor = _cor_sobre_regiao(base, (60, 1215, 660, 1330))
    fonte = _load_font(20 * _SCALE)
    x = _MARGEM * _SCALE
    y = _Y_RODAPE * _SCALE
    marca = UNIDADE.get("instagram", "@ensinamais.tatuape")
    largura = _texto_com_tracking(draw, x, y, marca, fonte, cor, int(1.2 * _SCALE))
    draw.text(
        (x + largura + 16 * _SCALE, y),
        f"·  {slide_num:02d}/{total:02d}",
        font=fonte,
        fill=(*cor[:3], 190),
        anchor="ls",
    )


def _icone_linha(
    draw: ImageDraw.ImageDraw, nome: str, cx: int, cy: int, tam: int, cor: tuple
) -> None:
    if nome == "gamepad":
        _draw_icon_gamepad(draw, cx, cy, tam, cor)
    elif nome == "code":
        _draw_icon_code_window(draw, cx, cy, tam, cor)
    elif nome == "brain":
        _draw_icon_brain_logic(draw, cx, cy, tam, cor)
    elif nome == "tablet":
        _draw_icon_tablet_passive(draw, cx, cy, tam, cor)


def _card_sobre_foto(
    base: Image.Image,
    mapa: tuple[list[list[float]], list[list[bool]]],
    texto: str,
    *,
    kicker: str,
    destaques: list[str] | None,
    hl_color: str,
    lado_ctr: str | None = None,
    icone: str | None = None,
    cor_texto: str = HEX_BRAND_BLUE,
    max_text_h: int = 320,
) -> tuple[dict, dict]:
    """Card editorial ancorado na base da foto.

    A altura é calculada pelo conteúdo (kicker + bloco + ícones), então não há
    vão interno nem texto boiando: o card encolhe até o texto e a foto ganha o
    espaço que sobrava. Texto alinhado à esquerda, ícones opcionais e posição
    final escolhida para não cobrir rostos (`_posicionar_card_sem_rosto`).
    """
    draw = ImageDraw.Draw(base)
    extra = {"triade": 96, "brain_topo": 92}.get(icone or "", 0)

    def _altura_para(largura_card: int, max_h: int) -> int:
        tam, _f, linhas, _a, _t, _c = _medir_bloco(
            draw, texto.strip(), (largura_card - 2 * _PAD_CARD) * _SCALE,
            max_h * _SCALE, 56, 30, 1.12,
        )
        fonte = _load_font(tam * _SCALE)
        asc, desc = fonte.getmetrics()
        entrelinha = int(round(tam * 1.12 * _SCALE))
        bloco = max(40.0, (asc + desc + entrelinha * (len(linhas) - 1)) / _SCALE)
        return int(84 + bloco + extra + 52)

    # Rosto/cabelo é restrição dura: varremos pé, topo e laterais procurando
    # faixa livre. Se o texto não couber em nenhuma, ele encolhe (até 30px) e
    # o card fica mais baixo — nunca aceitamos cobrir rosto por não ter espaço.
    # Só se nem assim houver faixa livre o card aceita a menor sobreposição.
    largura_lateral = int(round(_LARGURA_UTIL * 0.62))
    tentativas_h = [max_text_h]
    for mh in (240, 200):
        if mh < max_text_h:
            tentativas_h.append(mh)

    escolhido: tuple[tuple, tuple[int, int, int, int], int, int] | None = None
    for max_h in tentativas_h:
        for largura in (_LARGURA_UTIL, largura_lateral):
            altura = _altura_para(largura, max_h)
            box_card, chave = _melhor_posicao_editorial(
                mapa, largura, altura, lado_ctr=lado_ctr or None
            )
            if escolhido is None or chave < escolhido[0]:
                escolhido = (chave, box_card, max_h, altura)
        if escolhido is not None and escolhido[0][0] == 0:
            break

    _, box_card, max_h_usado, altura = escolhido
    topo_kicker = 62 + (extra if icone == "brain_topo" else 0)
    topo_texto = 84 + (extra if icone == "brain_topo" else 0)
    dy = box_card[1] - (_Y_BASE - altura)
    sc_a = _score_rosto(mapa[0], (_MARGEM, _Y_BASE - altura, 1080 - _MARGEM, _Y_BASE))
    sc_d = _score_rosto(mapa[0], box_card)

    _draw_rounded_card_with_shadow(
        base, box=box_card, radius=28, fill=(255, 255, 255, 234),
        shadow_alpha=72, shadow_blur=34, shadow_offset_y=18, glass=True, glass_blur=26,
    )
    draw = ImageDraw.Draw(base)
    x0, y0, x1, y1 = box_card

    if icone == "brain_topo":
        icx, icy = (x0 + x1) // 2, y0 + 66
        draw.ellipse(
            [(icx - 48) * _SCALE, (icy - 48) * _SCALE, (icx + 48) * _SCALE, (icy + 48) * _SCALE],
            fill=_hex_rgba(HEX_PASTEL_BLUE),
        )
        _draw_icon_brain_logic(draw, icx, icy, 30, _hex_rgba(HEX_BRAND_BLUE))

    _draw_kicker(
        base, kicker, x0 + _PAD_CARD, y0 + topo_kicker,
        color=HEX_BRAND_BLUE, rule_color=HEX_YELLOW, rule_w=24,
    )
    info = _draw_text_block(
        base, texto, (x0 + _PAD_CARD, y0 + topo_texto, x1 - _PAD_CARD, y0 + topo_texto + max_h_usado),
        size=56, min_size=30, color=cor_texto, highlight_phrases=destaques,
        highlight_color=hl_color, leading=1.12,
    )

    if icone == "triade":
        iy = y1 - 40 - 44
        for i, nome in enumerate(("gamepad", "brain", "code")):
            _icone_linha(
                draw, nome, x0 + _PAD_CARD + 44 + i * 132, iy, 40, _hex_rgba(HEX_BRAND_BLUE)
            )

    return info, {"antes": round(sc_a, 3), "depois": round(sc_d, 3), "dy": dy}


def _draw_nav_tag(base: Image.Image, style: str = "dark_on_light") -> None:
    """Desenha a tag de navegação 'Mova para o próximo ➔' no canto inferior direito."""
    draw = ImageDraw.Draw(base)
    font = _load_font(23 * _SCALE)
    label = TAG_NAVEGACAO.replace("➔", "").strip()
    tw = draw.textlength(label, font=font)
    arrow_w = 32 * _SCALE
    total_w = tw + arrow_w + 14 * _SCALE

    if style == "pill_white":
        px0 = _W2 - total_w - 86 * _SCALE
        py0 = _H2 - 102 * _SCALE
        px1 = _W2 - 42 * _SCALE
        py1 = _H2 - 44 * _SCALE
        _draw_rounded_card_with_shadow(
            base,
            (int(px0 / _SCALE), int(py0 / _SCALE), int(px1 / _SCALE), int(py1 / _SCALE)),
            radius=28,
            fill=(255, 255, 255, 246),
            shadow_alpha=45,
            shadow_blur=14,
            shadow_offset_y=4,
        )
        draw = ImageDraw.Draw(base)
        tx = px0 + 22 * _SCALE
        ty = py0 + 13 * _SCALE
        col = _hex_rgba(HEX_BRAND_BLUE)
    elif style == "white_on_dark":
        tx = _W2 - total_w - 60 * _SCALE
        ty = _H2 - 84 * _SCALE
        col = (255, 255, 255, 238)
    elif style == "yellow_on_blue":
        tx = _W2 - total_w - 135 * _SCALE
        ty = _H2 - 295 * _SCALE
        col = _hex_rgba(HEX_YELLOW)
    else:
        tx = _W2 - total_w - 64 * _SCALE
        ty = _H2 - 84 * _SCALE
        col = _hex_rgba(HEX_DARK_NAVY)

    draw.text((tx, ty), label, font=font, fill=col)
    ax0 = tx + tw + 14 * _SCALE
    ay = ty + 16 * _SCALE
    ax1 = ax0 + 22 * _SCALE
    w_line = 4 * _SCALE
    draw.line([(ax0, ay), (ax1, ay)], fill=col, width=w_line)
    draw.line([(ax1 - 9 * _SCALE, ay - 8 * _SCALE), (ax1, ay)], fill=col, width=w_line)
    draw.line([(ax1 - 9 * _SCALE, ay + 8 * _SCALE), (ax1, ay)], fill=col, width=w_line)


# ─── Ícones vetoriais minimalistas (Line-Art) ─────────────────────────────────

def _draw_icon_gamepad(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: tuple) -> None:
    cx, cy, s = cx * _SCALE, cy * _SCALE, size * _SCALE
    w = 5 * _SCALE
    draw.rounded_rectangle([cx - s, cy - int(s * 0.65), cx + s, cy + int(s * 0.65)], radius=int(s * 0.45), outline=color, width=w)
    dx, dy = cx - int(s * 0.42), cy
    d = int(s * 0.22)
    draw.line([(dx - d, dy), (dx + d, dy)], fill=color, width=w)
    draw.line([(dx, dy - d), (dx, dy + d)], fill=color, width=w)
    bx, by = cx + int(s * 0.42), cy
    r = int(s * 0.09)
    draw.ellipse([bx - r, by - int(s * 0.22) - r, bx + r, by - int(s * 0.22) + r], fill=color)
    draw.ellipse([bx + int(s * 0.22) - r, by - r, bx + int(s * 0.22) + r, by + r], fill=color)


def _draw_icon_code_window(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: tuple) -> None:
    cx, cy, s = cx * _SCALE, cy * _SCALE, size * _SCALE
    w = 5 * _SCALE
    draw.rounded_rectangle([cx - s, cy - int(s * 0.75), cx + s, cy + int(s * 0.75)], radius=14 * _SCALE, outline=color, width=w)
    draw.line([(cx - s, cy - int(s * 0.4)), (cx + s, cy - int(s * 0.4))], fill=color, width=w)
    y_mid = cy + int(s * 0.15)
    draw.line([(cx - int(s * 0.25), y_mid - int(s * 0.22)), (cx - int(s * 0.5), y_mid)], fill=color, width=w)
    draw.line([(cx - int(s * 0.5), y_mid), (cx - int(s * 0.25), y_mid + int(s * 0.22))], fill=color, width=w)
    draw.line([(cx + int(s * 0.25), y_mid - int(s * 0.22)), (cx + int(s * 0.5), y_mid)], fill=color, width=w)
    draw.line([(cx + int(s * 0.5), y_mid), (cx + int(s * 0.25), y_mid + int(s * 0.22))], fill=color, width=w)
    draw.line([(cx - int(s * 0.08), y_mid + int(s * 0.26)), (cx + int(s * 0.08), y_mid - int(s * 0.26))], fill=color, width=w)


def _draw_icon_brain_logic(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: tuple) -> None:
    cx, cy, s = cx * _SCALE, cy * _SCALE, size * _SCALE
    w = 5 * _SCALE
    draw.ellipse([cx - s, cy - s, cx + s, cy + s], outline=color, width=w)
    r_in = int(s * 0.48)
    draw.ellipse([cx - r_in, cy - r_in, cx + r_in, cy + r_in], outline=color, width=w)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = cx + int(math.cos(rad) * r_in)
        y1 = cy + int(math.sin(rad) * r_in)
        x2 = cx + int(math.cos(rad) * (s * 0.76))
        y2 = cy + int(math.sin(rad) * (s * 0.76))
        draw.line([(x1, y1), (x2, y2)], fill=color, width=w)


def _draw_icon_tablet_passive(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: tuple) -> None:
    cx, cy, s = cx * _SCALE, cy * _SCALE, size * _SCALE
    w = 5 * _SCALE
    tw, th = int(s * 0.65), int(s * 0.9)
    draw.rounded_rectangle([cx - tw, cy - th, cx + tw, cy + th], radius=14 * _SCALE, outline=color, width=w)
    p = int(s * 0.25)
    draw.polygon([(cx - int(p * 0.6), cy - p), (cx - int(p * 0.6), cy + p), (cx + p, cy)], outline=color, width=w)


def _paste_logo(base: Image.Image, center_x: int, top_y: int, target_w: int, invert_white_box: bool = False) -> None:
    logo_path = REFS_DIR / "LOGO ENSINA TM ASS PRETA.png"
    if not logo_path.exists():
        return
    try:
        logo = Image.open(logo_path).convert("RGBA")
        tw = target_w * _SCALE
        th = int(logo.height * (tw / logo.width))
        logo = logo.resize((tw, th), Image.LANCZOS)
        x = center_x * _SCALE - tw // 2
        y = top_y * _SCALE
        if invert_white_box:
            pad = 18 * _SCALE
            _draw_rounded_card_with_shadow(
                base,
                (int((x - pad) / _SCALE), int((y - pad) / _SCALE), int((x + tw + pad) / _SCALE), int((y + th + pad) / _SCALE)),
                radius=18,
                fill=(255, 255, 255, 248),
                shadow_alpha=35,
                shadow_blur=16,
                shadow_offset_y=6,
            )
        base.alpha_composite(logo, (x, y))
    except Exception:
        pass


def _inferir_cena_padrao(slide_num: int, texto: str, prompt_en: str = "", referencias: list[str] | None = None) -> str:
    """Escolhe a melhor cena de refs/catalogo.json para o slide."""
    if referencias:
        for r in referencias:
            if r and r != "logo":
                return r
    if slide_num == 7:
        return "fachada"
    combinado = f"{texto} {prompt_en}".lower()
    if any(k in combinado for k in ("game", "código", "codigo", "program", "algoritm", "code", "coding", "tela")):
        return "aluno_programacao"
    if any(k in combinado for k in ("robó", "robo", "lego", "kit", "robotics")):
        return "alunos_robotica"
    if any(k in combinado for k in ("fração", "fracao", "matemática", "português", "prova", "nota", "estudo", "reforço", "apoio")):
        return "alunos_apoio"
    rodizio = {1: "recepcao_unidade", 4: "aluno_programacao", 5: "alunos_apoio", 6: "laboratorio"}
    return rodizio.get(slide_num, "recepcao_unidade")


# ─── Renderizador Editorial HD por Lâmina (1 a 8) ─────────────────────────────

_RE_HEX6 = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _ctr_cor_destaque(ctr: dict | None, padrao: str) -> str:
    """Cor de grifo do CTR estruturado (paleta_complementar.destaque); hex
    ausente/inválido cai no padrão da lâmina."""
    if isinstance(ctr, dict):
        paleta = ctr.get("paleta_complementar")
        if isinstance(paleta, dict):
            cor = paleta.get("destaque")
            if isinstance(cor, str):
                m = _RE_HEX6.match(cor.strip())
                if m:
                    return f"#{m.group(1)}"
    return padrao


def _box_lateral(
    box: tuple[int, int, int, int], lado: str, largura_frac: float = 0.62, max_largura: int = 850
) -> tuple[int, int, int, int]:
    """Re-ancora o card glass para o lado do negative space (regra 17): o card
    encolhe e o lado oposto fica dominado pela foto. Clamp de largura preserva
    a safe zone 1:1 do carrossel."""
    x0, y0, x1, y1 = box
    novo_w = min(max_largura, int(round((x1 - x0) * largura_frac)))
    if lado == "direita":
        return (x1 - novo_w, y0, x1, y1)
    return (x0, y0, x0 + novo_w, y1)


# ─── Detecção de rostos (Haar/OpenCV + cabelo por blob escuro) ───────────────
# O card glass não pode cobrir a cabeça das pessoas na foto. Rostos visíveis
# saem da cascata Haar do OpenCV (frontal + perfil, nas duas orientações): é
# preciso e mata os falsos positivos de braço/mão que o tom de pele sozinho
# gerava (a cadeia testa→queixo descia pelo braço contíguo). Cabeça de costas —
# só cabelo, nenhum rosto para a câmera — não tem detector que pegue (nem Haar,
# nem neural), então completamos com um blob escuro compacto contíguo a pele
# real (orelha/nuca). Tudo é rasterizado na grade 18×22 que o posicionamento já
# consome, então `_score_rosto`, `_mascara_protegida` e a busca de posição
# continuam iguais. Sem OpenCV instalado, cai só no blob de cabelo (nunca quebra).

_PELE_LIMITE = 0.035       # densidade média de pele dentro do box ainda aceitável
_PELE_MELHORIA_MIN = 0.01  # só muda o layout se a melhoria for real
_PELE_PASSO = 40           # granularidade do deslocamento vertical (px)
_PELE_COLS, _PELE_LINHAS = 18, 22
_PELE_MARGEM = 28          # folga em px ao redor do bloco de rosto/cabelo
_PELE_Y_CABELO = 70        # luminância abaixo disso conta como cabelo/bloco escuro
_PELE_DENS_CABELO = 0.55   # fração de pixels escuros p/ célula ser cabelo
_PELE_SKIN_MIN = 0.30      # pele genuína ao redor do blob: é cabeça, não móvel
_PELE_HAIR_VIZ = 2         # vizinhos escuros mínimos: cabelo é bloco, não listra
_PELE_TOPO_FRAC = 0.45     # blob de cabelo só vale na parte de cima (cabeça fica
                           # acima; manga/torre de PC ficam embaixo e dariam falso)
_PELE_NAPE_LINHAS = 3      # linhas de pescoço/nuca protegidas abaixo do cabelo
_PELE_NAPE_MIN = 0.18      # pele (mesmo na sombra) que continua a nuca abaixo do cabelo
_FACE_CIMA = 0.65          # expansão do retângulo de rosto p/ cima (cabelo+testa)
_FACE_LADO = 0.20          # expansão p/ os lados (orelhas)
_FACE_BAIXO = 0.10         # expansão p/ baixo (queixo/mandíbula)


@lru_cache(maxsize=1)
def _cascatas():
    """(cv2, frontal, perfil) ou None se OpenCV não estiver disponível."""
    try:
        import os

        import cv2
    except Exception:
        return None
    d = os.path.join(os.path.dirname(cv2.__file__), "data")
    frontal = cv2.CascadeClassifier(os.path.join(d, "haarcascade_frontalface_default.xml"))
    perfil = cv2.CascadeClassifier(os.path.join(d, "haarcascade_profileface.xml"))
    if frontal.empty() or perfil.empty():
        return None
    return cv2, frontal, perfil


def _rostos_haar(base: Image.Image) -> list[tuple[int, int, int, int]]:
    """Retângulos de rosto (x, y, w, h) em espaço 1× (1080×1350)."""
    cc = _cascatas()
    if cc is None:
        return []
    cv2, frontal, perfil = cc
    import numpy as np

    arr = np.asarray(base.convert("RGB"))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    gray = cv2.resize(gray, (540, 675), interpolation=cv2.INTER_AREA)
    gray = cv2.equalizeHist(gray)
    kw = {"scaleFactor": 1.12, "minNeighbors": 5, "minSize": (34, 34)}
    espelho = cv2.flip(gray, 1)
    rects: list[tuple[int, int, int, int]] = []
    for cascade, img, flip in ((frontal, gray, False), (perfil, gray, False), (perfil, espelho, True)):
        for (x, y, w, h) in cascade.detectMultiScale(img, **kw):
            xx = (540 - x - w) if flip else x
            rects.append((xx * 2, y * 2, w * 2, h * 2))  # 540 → 1080 (espaço 1×)
    return rects


def _mapa_pele(base: Image.Image) -> tuple[list[list[float]], list[list[bool]]]:
    """Mapa de cobertura de ROSTO (0..1 por célula) + máscara de CABEÇA.

    `mapa[j][i]` é a fração da célula coberta por um retângulo de rosto Haar —
    alimenta `_score_rosto` (que só conta célula com ≥0.5). `cabeca[j][i]` marca
    o que o card jamais pode cobrir: a cabeça inteira de cada rosto detectado
    (retângulo expandido para cima/lados para incluir cabelo e orelha) mais os
    blobs de cabelo de costas. É restrição categórica na escolha da posição.
    """
    # Grade de pele e escuro (YCbCr) — só usada pelo blob de cabelo; Autocontrast
    # na luminância pega rosto/cabelo na sombra sem destruir a crominância.
    small = base.convert("RGB").resize(
        (_PELE_COLS * 4, _PELE_LINHAS * 4), Image.BILINEAR
    )
    _y, _cb, _cr = small.convert("YCbCr").split()
    small = Image.merge("YCbCr", (ImageOps.autocontrast(_y, cutoff=2), _cb, _cr))
    px = small.load()
    pele: list[list[float]] = []
    escuro: list[list[float]] = []
    for j in range(_PELE_LINHAS):
        linha_s: list[float] = []
        linha_d: list[float] = []
        for i in range(_PELE_COLS):
            n_s = n_d = 0
            for yy in range(j * 4, j * 4 + 4):
                for xx in range(i * 4, i * 4 + 4):
                    y, cb, cr = px[xx, yy]
                    if y < _PELE_Y_CABELO:
                        n_d += 1
                    elif 77 <= cb <= 127 and 133 <= cr <= 173:
                        n_s += 1
            linha_s.append(n_s / 16.0)
            linha_d.append(n_d / 16.0)
        pele.append(linha_s)
        escuro.append(linha_d)

    cw, ch = 1080 / _PELE_COLS, 1350 / _PELE_LINHAS
    mapa: list[list[float]] = [[0.0] * _PELE_COLS for _ in range(_PELE_LINHAS)]
    cabeca: list[list[bool]] = [[False] * _PELE_COLS for _ in range(_PELE_LINHAS)]

    # 1) Rostos Haar: cobertura no mapa + cabeça expandida na máscara.
    for (x, y, w, h) in _rostos_haar(base):
        i0, i1 = max(0, int(x / cw)), min(_PELE_COLS - 1, int((x + w - 1) / cw))
        j0, j1 = max(0, int(y / ch)), min(_PELE_LINHAS - 1, int((y + h - 1) / ch))
        for j in range(j0, j1 + 1):
            for i in range(i0, i1 + 1):
                ox = max(0, min(i * cw + cw, x + w) - max(i * cw, x))
                oy = max(0, min(j * ch + ch, y + h) - max(j * ch, y))
                mapa[j][i] = max(mapa[j][i], (ox * oy) / (cw * ch))
        hx0, hy0 = x - _FACE_LADO * w, y - _FACE_CIMA * h
        hx1, hy1 = x + w + _FACE_LADO * w, y + h + _FACE_BAIXO * h
        for j in range(max(0, int(hy0 / ch)), min(_PELE_LINHAS, int((hy1 - 1) / ch) + 1)):
            for i in range(max(0, int(hx0 / cw)), min(_PELE_COLS, int((hx1 - 1) / cw) + 1)):
                cabeca[j][i] = True

    # 2) Blob de cabelo de costas (nuca sem rosto para a câmera — nenhum detector
    #    de rosto pega). Distinguir cabelo de roupa escura é o ponto: cabelo fica
    #    NA PARTE DE CIMA da foto e tem pele (nuca/queixo) DIRETAMENTE ABAIXO dele;
    #    camiseta e blusa ficam embaixo e têm pele ACIMA, não abaixo. Então: blob
    #    escuro compacto (≥_PELE_HAIR_VIZ vizinhos), acima de ~60% da altura, com
    #    pele genuína nas 2 linhas seguintes. Sem essas três condições, o cabelo
    #    vira a roupa escura inteira e o card fica sem faixa livre.
    topo_max = int(_PELE_LINHAS * _PELE_TOPO_FRAC)
    for j in range(topo_max):
        for i in range(_PELE_COLS):
            if escuro[j][i] < _PELE_DENS_CABELO:
                continue
            viz = sum(
                1 for dj, di in ((1, 0), (-1, 0), (0, 1), (0, -1))
                if 0 <= j + dj < _PELE_LINHAS and 0 <= i + di < _PELE_COLS
                and escuro[j + dj][i + di] >= _PELE_DENS_CABELO
            )
            if viz < _PELE_HAIR_VIZ:
                continue
            # pele genuína logo abaixo (nuca/rosto), nas 2 linhas seguintes
            abaixo = any(
                0 <= i + di < _PELE_COLS and pele[jj][i + di] >= _PELE_SKIN_MIN
                for jj in (j + 1, j + 2)
                for di in (-1, 0, 1)
                if jj < _PELE_LINHAS
            )
            if not abaixo:
                continue
            cabeca[j][i] = True
            # Nuca: desce a proteção pela pele contígua abaixo do cabelo (o
            # pescoço de quem está de costas). Para no primeiro vão sem pele —
            # ombro/torso abaixo já pode receber card. Limitado a 3 linhas.
            for jj in range(j + 1, min(j + 1 + _PELE_NAPE_LINHAS, _PELE_LINHAS)):
                if pele[jj][i] >= _PELE_NAPE_MIN or escuro[jj][i] >= _PELE_DENS_CABELO:
                    cabeca[jj][i] = True
                else:
                    break

    return mapa, cabeca


def _box_toc_cabeca(cabeca: list[list[bool]], box: tuple[int, int, int, int]) -> bool:
    x0, y0, x1, y1 = box
    i0 = max(0, int(x0 * _PELE_COLS / 1080))
    i1 = min(_PELE_COLS - 1, int((x1 - 1) * _PELE_COLS / 1080))
    j0 = max(0, int(y0 * _PELE_LINHAS / 1350))
    j1 = min(_PELE_LINHAS - 1, int((y1 - 1) * _PELE_LINHAS / 1350))
    return any(cabeca[j][i] for j in range(j0, j1 + 1) for i in range(i0, i1 + 1))


def _score_rosto(mapa: list[list[float]], box: tuple[int, int, int, int]) -> float:
    """Pontuação de "cobrir rosto" dentro do box (espaço 1080×1350). Mistura
    média e pico por célula: o pico é o que importa — um único célula com rosto
    vale mais que várias com braço/torso."""
    x0, y0, x1, y1 = box
    i0 = max(0, int(x0 * _PELE_COLS / 1080))
    i1 = min(_PELE_COLS - 1, int((x1 - 1) * _PELE_COLS / 1080))
    j0 = max(0, int(y0 * _PELE_LINHAS / 1350))
    j1 = min(_PELE_LINHAS - 1, int((y1 - 1) * _PELE_LINHAS / 1350))
    if i1 < i0 or j1 < j0:
        return 0.0
    vals = [mapa[j][i] for j in range(j0, j1 + 1) for i in range(i0, i1 + 1)]
    # Só conta como rosto a célula densa (≥0.5): braço/tronco atravessam a
    # célula pela metade, rosto preenchido passa de 0.6 quase sempre.
    pico = max((v for v in vals if v >= 0.5), default=0.0)
    return 0.6 * (sum(vals) / len(vals)) + 0.4 * pico


def _mascara_protegida(
    mapas: tuple[list[list[float]], list[list[bool]]],
) -> list[list[bool]]:
    """Máscara de células que o card não pode cobrir (rosto + cabelo),
    dilatada em 1 célula — a folga cobre queixo, orelha e topo da cabeça.

    Máscara em células, não bbox: agrupar pele conectada num único retângulo
    juntava cabeça + pescoço + braço + mesa e virava uma área impossível de
    desviar. A célula é a unidade certa para "aqui tem gente".
    """
    mapa, cabeca = mapas
    base = [
        [bool(cabeca[j][i]) or mapa[j][i] >= 0.5 for i in range(_PELE_COLS)]
        for j in range(_PELE_LINHAS)
    ]
    mascara = [[False] * _PELE_COLS for _ in range(_PELE_LINHAS)]
    for j in range(_PELE_LINHAS):
        for i in range(_PELE_COLS):
            if not base[j][i]:
                continue
            for dj in (-1, 0, 1):
                for di in (-1, 0, 1):
                    jj, ii = j + dj, i + di
                    if 0 <= jj < _PELE_LINHAS and 0 <= ii < _PELE_COLS:
                        mascara[jj][ii] = True
    return mascara


def _penalidade(
    mapas: tuple[list[list[float]], list[list[bool]]],
    box: tuple[int, int, int, int],
    *,
    mascara: list[list[bool]] | None = None,
) -> tuple[int, int, float]:
    """(células de rosto cobertas, área coberta em px², score de pele).
    A folga `_PELE_MARGEM` entra como expansão do box antes da contagem."""
    if mascara is None:
        mascara = _mascara_protegida(mapas)
    cel_w = 1080 / _PELE_COLS
    cel_h = 1350 / _PELE_LINHAS
    x0 = max(0, box[0] - _PELE_MARGEM)
    y0 = max(0, box[1] - _PELE_MARGEM)
    x1 = min(1080, box[2] + _PELE_MARGEM)
    y1 = min(1350, box[3] + _PELE_MARGEM)
    i0 = max(0, int(x0 / cel_w))
    i1 = min(_PELE_COLS - 1, int((x1 - 1) / cel_w))
    j0 = max(0, int(y0 / cel_h))
    j1 = min(_PELE_LINHAS - 1, int((y1 - 1) / cel_h))
    celulas = 0
    for j in range(j0, j1 + 1):
        for i in range(i0, i1 + 1):
            if mascara[j][i]:
                celulas += 1
    return celulas, int(celulas * cel_w * cel_h), _score_rosto(mapas[0], box)


def _melhor_posicao_editorial(
    mapas: tuple[list[list[float]], list[list[bool]]],
    largura: int,
    altura: int,
    *,
    lado_ctr: str | None = None,
    passo: int = 20,
) -> tuple[tuple[int, int, int, int], tuple]:
    """Posição do card em qualquer faixa da foto que não cubra rosto/cabelo.

    Antes o card era ancorado no pé e só deslizava um pouco; se o rosto estava
    embaixo, não havia saída. Agora varremos a altura inteira (pé → topo) e as
    duas laterais, com preferência por: pé da foto, largura cheia e posição
    mais baixa. Devolve (box, chave) — chave é comparável entre tentativas.
    """
    mascara = _mascara_protegida(mapas)
    x_esq = _MARGEM
    x_dir = 1080 - _MARGEM - largura
    largura_cheia = largura >= _LARGURA_UTIL - 1
    if largura_cheia:
        xs = [x_esq]
    elif lado_ctr == "esquerda":
        xs = [x_esq]
    elif lado_ctr == "direita":
        xs = [x_dir]
    else:
        xs = [x_esq, x_dir]

    altura_max = 1080 - altura
    ys = list(range(200, altura_max + 1, passo))
    if not ys or ys[-1] != altura_max:
        ys.append(altura_max)

    melhor: tuple[tuple[int, int, int, int], tuple] | None = None
    for x0 in xs:
        for y0 in ys:
            box = (x0, y0, x0 + largura, y0 + altura)
            toca, area, sc = _penalidade(mapas, box, mascara=mascara)
            # faixa: 0 = pé da foto, 1 = topo (abaixo do logo), 2 = meio
            tier = 0 if box[3] >= 880 else (1 if y0 <= 340 else 2)
            chave = (
                toca,
                0 if area == 0 else 1,
                tier,
                0 if largura_cheia else 1,
                -y0,
                round(sc * 200),
            )
            if melhor is None or chave < melhor[1]:
                melhor = (box, chave)
    assert melhor is not None
    return melhor


def _posicionar_card_sem_rosto(
    mapas: tuple[list[list[float]], list[list[bool]]],
    box: tuple[int, int, int, int],
    dy_min: int,
    dy_max: int,
    *,
    lado_ctr: str | None = None,
    passo: int = _PELE_PASSO,
    permitir_lateral: bool = True,
) -> tuple[tuple[int, int, int, int], int, float, float]:
    """Escolhe (box, dy, score_antes, score_depois) do card glass que menos
    cobre rostos. Cabelo é restrição categórica: se existe posição sem tocar
    célula de cabeça, ela vence qualquer alternativa que toque. Com `lado_ctr`
    o card já parte estreitado para o lado do negative space; sem ele, a
    largura cheia é preferida e o estreitamento lateral só entra quando
    necessário."""
    mapa, cabeca = mapas
    box_base = _box_lateral(box, lado_ctr) if (lado_ctr and permitir_lateral) else box
    sc_base = _score_rosto(mapa, box_base)
    base_toca = _box_toc_cabeca(cabeca, box_base)
    if not base_toca and sc_base <= _PELE_LIMITE:
        return box_base, 0, sc_base, sc_base

    if not permitir_lateral:
        # Largura já decidida: só o deslocamento vertical pode mudar (evita o
        # ciclo largura→altura→largura que fazia o texto vazar do card).
        laterais = [None]
    elif lado_ctr:
        outro = "direita" if lado_ctr == "esquerda" else "esquerda"
        laterais = [lado_ctr, outro]
    else:
        laterais = [None, "esquerda", "direita"]

    candidatos: list[tuple[int, int, int, int, int, tuple]] = []
    for lado in laterais:
        bx = _box_lateral(box, lado) if lado else box
        for dy in range(dy_min, dy_max + 1, passo):
            cand = (bx[0], bx[1] + dy, bx[2], bx[3] + dy)
            toca = int(_box_toc_cabeca(cabeca, cand))
            sc = _score_rosto(mapa, cand)
            # 1º não tocar cabelo; 2º score; empate técnico (±0.005): largura
            # cheia > lateral, deslocamento menor > maior
            candidatos.append((toca, round(sc * 200), 0 if lado is None else 1, abs(dy), dy, cand))
    candidatos.sort()
    toca_dep, sc, _, _, dy, cand = candidatos[0]
    sc_dep = sc / 200.0
    if toca_dep < int(base_toca):
        return cand, dy, sc_base, sc_dep
    # Só muda por score se a melhoria for grande (≥40% e ≥0.01 absoluto): em
    # foto lotada, braço/mão também pontuam e um ganho pequeno troca um
    # queixo coberto por uma mão coberta — não vale o risco.
    if sc_dep <= min(sc_base - _PELE_MELHORIA_MIN, sc_base * 0.6):
        return cand, dy, sc_base, sc_dep
    return box_base, 0, sc_base, sc_base


def render_slide_hd(
    slide_num: int,
    texto: str,
    *,
    eixo: str = "Didático",
    cta_keyword: str = "AULA",
    prompt_en: str = "",
    referencias: list[str] | None = None,
    destaques: list[str] | None = None,
    ctr: dict | None = None,
    total_slides: int = 8,
) -> tuple[bytes, dict]:
    """
    Renderiza um slide 1080×1350 no estilo Editorial / AutoFlow HD usando as fotos
    reais da unidade (refs/catalogo.json), paleta oficial e tipografia Montserrat-Bold.

    Composição v3: grade única (margem 96, largura útil 888), manchete alinhada à
    esquerda com kicker de sobrancelha, entrelinha tipográfica constante, cards
    dimensionados pelo conteúdo e rodapé de série (@ + índice). Mantém as fotos
    reais intocáveis, a busca de posição que não cobre rostos e o `ctr` da regra 17.
    """
    cena = _inferir_cena_padrao(slide_num, texto, prompt_en, referencias)
    is_last = slide_num >= total_slides

    ctr_ativo = isinstance(ctr, dict) and slide_num in (1, 2, 4, 5)
    lado_ctr = ""
    hl_ctr: str | None = None
    if ctr_ativo:
        hl_ctr = _ctr_cor_destaque(ctr, "")
        lado_ctr = (ctr.get("lado_negative_space") or "").strip().lower()
        if lado_ctr not in ("esquerda", "direita"):
            lado_ctr = ""
        if destaques is None:
            impacto = str(ctr.get("texto_de_impacto") or "").strip()
            if impacto:
                destaques = [impacto]
    hl_amarelo = hl_ctr or HEX_YELLOW
    card_rosto_info: dict | None = None
    info: dict = {}

    if slide_num == 1:
        base = _cover_crop(_selecionar_foto_cena(cena, 0), _W2, _H2)
        mapa = _mapa_pele(base)
        _desenhar_scrim(base, 0.26, (8, 18, 34), _scrim_alpha_adaptativo(_luminancia(base)), expo=1.2)
        _paste_logo(base, center_x=_MARGEM + 125, top_y=64, target_w=250, invert_white_box=True)
        info, card_rosto_info = _card_sobre_foto(
            base, mapa, texto,
            kicker=f"ENSINA MAIS · TATUAPÉ · {eixo.upper()}",
            destaques=destaques, hl_color=hl_amarelo, lado_ctr=lado_ctr or None,
            icone="triade", max_text_h=300,
        )
        if not is_last:
            _draw_nav_tag(base, style="pill_white")

    elif slide_num == 2:
        base = _gradiente_vertical("#0C90B4", HEX_BRAND_BLUE)
        draw = ImageDraw.Draw(base)
        f_ghost = _load_font(124 * _SCALE)
        draw.text(
            ((1080 - _MARGEM) * _SCALE, 250 * _SCALE), "02", font=f_ghost,
            fill=(255, 255, 255, 34), anchor="rs",
        )
        _draw_kicker(
            base, "POR QUE ACONTECE", _MARGEM, 250,
            color=HEX_WHITE, rule_color=HEX_YELLOW, rule_w=30,
        )
        info = _draw_text_block(
            base, texto, (_MARGEM, 300, 1080 - _MARGEM, 900),
            size=66, min_size=36, color=HEX_WHITE,
            highlight_color=hl_ctr or HEX_ORANGE, highlight_phrases=destaques,
            leading=1.1, vertical="center",
        )
        draw = ImageDraw.Draw(base)
        draw.line(
            [(_MARGEM * _SCALE, 972 * _SCALE), ((1080 - _MARGEM) * _SCALE, 972 * _SCALE)],
            fill=(255, 255, 255, 64), width=2 * _SCALE,
        )
        for cx_i, nome in ((160, "gamepad"), (540, "code"), (920, "brain")):
            draw.ellipse(
                [(cx_i - 52) * _SCALE, (1058 - 52) * _SCALE, (cx_i + 52) * _SCALE, (1058 + 52) * _SCALE],
                outline=(255, 255, 255, 150), width=3 * _SCALE,
            )
            _icone_linha(draw, nome, cx_i, 1058, 34, (255, 255, 255, 235))
        if not is_last:
            _draw_nav_tag(base, style="white_on_dark")

    elif slide_num == 3:
        base = _gradiente_vertical(HEX_WHITE, "#F1F6FD")
        _paste_logo(base, center_x=_MARGEM + 112, top_y=70, target_w=224)
        _draw_kicker(base, "MÉTODO ENSINA MAIS", _MARGEM, 312, color=HEX_BRAND_BLUE)
        info = _draw_text_block(
            base, texto, (_MARGEM, 340, 1080 - _MARGEM, 552),
            size=56, min_size=34, color=HEX_BRAND_BLUE,
            highlight_color=HEX_YELLOW, highlight_phrases=destaques, leading=1.14,
        )
        _draw_rounded_card_with_shadow(
            base, box=(_MARGEM, 574, 514, 1070), radius=24, fill=(255, 255, 255, 255),
            shadow_alpha=34, shadow_blur=26, shadow_offset_y=10,
            outline=_hex_rgba("#E2E8F0"), outline_width=2,
        )
        _draw_rounded_card_with_shadow(
            base, box=(566, 574, 1080 - _MARGEM, 1070), radius=24,
            fill=_hex_rgba(HEX_PASTEL_ORANGE),
            shadow_alpha=42, shadow_blur=26, shadow_offset_y=12,
            outline=_hex_rgba(HEX_BRAND_BLUE), outline_width=4,
        )
        draw = ImageDraw.Draw(base)
        draw.ellipse(
            [(305 - 74) * _SCALE, (754 - 74) * _SCALE, (305 + 74) * _SCALE, (754 + 74) * _SCALE],
            fill=_hex_rgba("#F1F5F9"),
        )
        _draw_icon_tablet_passive(draw, 305, 754, 42, _hex_rgba("#64748B"))
        draw.ellipse(
            [(775 - 74) * _SCALE, (754 - 74) * _SCALE, (775 + 74) * _SCALE, (754 + 74) * _SCALE],
            fill=_hex_rgba(HEX_BRAND_BLUE),
        )
        _draw_icon_code_window(draw, 775, 754, 42, (255, 255, 255, 255))
        _draw_text_block(
            base, "Rotina\nPassiva", (120, 870, 490, 1016),
            align="center", size=34, min_size=26, color="#475569",
            highlight_phrases=[], leading=1.12, vertical="center",
        )
        _draw_text_block(
            base, "Método Ativo\ne Prático", (590, 870, 960, 1016),
            align="center", size=34, min_size=26, color=HEX_DARK_NAVY,
            highlight_phrases=[], leading=1.12, vertical="center",
        )
        draw = ImageDraw.Draw(base)
        draw.ellipse(
            [(540 - 34) * _SCALE, (822 - 34) * _SCALE, (540 + 34) * _SCALE, (822 + 34) * _SCALE],
            fill=(255, 255, 255, 255), outline=_hex_rgba("#CBD5E1"), width=2 * _SCALE,
        )
        draw.text(
            (540 * _SCALE, 822 * _SCALE), "VS", font=_load_font(18 * _SCALE),
            fill=_hex_rgba(HEX_DARK_NAVY), anchor="mm",
        )
        if not is_last:
            _draw_nav_tag(base, style="dark_on_light")

    elif slide_num == 4:
        base = _cover_crop(_selecionar_foto_cena(cena, 1), _W2, _H2)
        mapa = _mapa_pele(base)
        _desenhar_scrim(base, 0.34, (8, 18, 34), _scrim_alpha_adaptativo(_luminancia(base)), expo=1.2)
        _paste_logo(base, center_x=_MARGEM + 110, top_y=64, target_w=220, invert_white_box=True)
        info, card_rosto_info = _card_sobre_foto(
            base, mapa, texto, kicker="MÉTODO ENSINA MAIS", destaques=destaques,
            hl_color=hl_amarelo, lado_ctr=lado_ctr or None, icone="brain_topo", max_text_h=260,
        )
        if not is_last:
            _draw_nav_tag(base, style="pill_white")

    elif slide_num == 5:
        base = _cover_crop(_selecionar_foto_cena(cena, 2), _W2, _H2)
        mapa = _mapa_pele(base)
        _desenhar_scrim(base, 0.40, (8, 18, 34), _scrim_alpha_adaptativo(_luminancia(base)), expo=1.2)
        _paste_logo(base, center_x=_MARGEM + 110, top_y=64, target_w=220, invert_white_box=True)
        info, card_rosto_info = _card_sobre_foto(
            base, mapa, texto, kicker="ENSINA MAIS · TATUAPÉ", destaques=destaques,
            hl_color=hl_amarelo, lado_ctr=lado_ctr or None, max_text_h=300,
        )
        if not is_last:
            _draw_nav_tag(base, style="white_on_dark")

    elif slide_num == 6:
        base = _gradiente_vertical(HEX_WHITE, "#EEF4FC")
        fotos_grid = [
            (_selecionar_foto_cena("aluno_programacao", 0), (96, 96, 520, 470)),
            (_selecionar_foto_cena("alunos_apoio", 0), (560, 96, 984, 470)),
            (_selecionar_foto_cena("laboratorio", 0), (96, 494, 520, 868)),
            (_selecionar_foto_cena("alunos_robotica", 0), (560, 494, 984, 868)),
        ]
        for f_path, (x0, y0, x1, y1) in fotos_grid:
            crop = _cover_crop(f_path, (x1 - x0) * _SCALE, (y1 - y0) * _SCALE)
            mask = Image.new("L", crop.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                [0, 0, crop.width - 1, crop.height - 1], radius=18 * _SCALE, fill=255
            )
            base.paste(crop, (x0 * _SCALE, y0 * _SCALE), mask)

        draw = ImageDraw.Draw(base)
        loc_txt = "Rua Coelho Lisboa, 783 • Tatuapé"
        f_loc = _load_font(22 * _SCALE)
        lw = draw.textlength(loc_txt, font=f_loc)
        px = _MARGEM * _SCALE
        chip_y = 902 * _SCALE
        chip_h = 54 * _SCALE
        draw.rounded_rectangle(
            [px, chip_y, px + 44 * _SCALE + lw + 30 * _SCALE, chip_y + chip_h],
            radius=chip_h // 2, fill=_hex_rgba(HEX_PASTEL_ORANGE),
        )
        pcx, pcy = int(px + 26 * _SCALE), int(chip_y + 27 * _SCALE)
        draw.ellipse(
            [pcx - 9 * _SCALE, pcy - 12 * _SCALE, pcx + 9 * _SCALE, pcy + 6 * _SCALE],
            fill=_hex_rgba(HEX_BRAND_BLUE),
        )
        draw.polygon(
            [(pcx - 7 * _SCALE, pcy + 2 * _SCALE), (pcx + 7 * _SCALE, pcy + 2 * _SCALE), (pcx, pcy + 14 * _SCALE)],
            fill=_hex_rgba(HEX_BRAND_BLUE),
        )
        draw.text(
            (px + 44 * _SCALE, chip_y + 17 * _SCALE), loc_txt, font=f_loc,
            fill=_hex_rgba(HEX_DARK_NAVY),
        )
        info = _draw_text_block(
            base, texto, (_MARGEM, 1000, 1080 - _MARGEM, 1195),
            size=44, min_size=28, color=HEX_DARK_NAVY,
            highlight_color=HEX_YELLOW, highlight_phrases=destaques, leading=1.14,
        )
        if not is_last:
            _draw_nav_tag(base, style="dark_on_light")

    elif slide_num == 7:
        base = _cover_crop(_selecionar_foto_cena("fachada", 0), _W2, _H2)
        mapa = _mapa_pele(base)
        _desenhar_scrim(base, 0.32, (8, 18, 34), _scrim_alpha_adaptativo(_luminancia(base)), expo=1.2)
        info, card_rosto_info = _card_sobre_foto(
            base, mapa, texto, kicker="CASO REAL · ENSINO FUNDAMENTAL",
            destaques=destaques, hl_color=HEX_PASTEL_BLUE, cor_texto=HEX_DARK_NAVY,
            max_text_h=340,
        )
        if not is_last:
            _draw_nav_tag(base, style="pill_white")

    else:
        # Slide 8 (ou último slide): CTA Final
        base = _gradiente_vertical(HEX_WHITE, "#F0F5FD")
        draw = ImageDraw.Draw(base)
        draw.ellipse(
            [(-320) * _SCALE, (-620) * _SCALE, 1400 * _SCALE, 340 * _SCALE],
            fill=_hex_rgba(HEX_BRAND_BLUE),
        )
        _paste_logo(base, center_x=_MARGEM + 120, top_y=66, target_w=240, invert_white_box=True)
        _draw_kicker(base, "PRÓXIMO PASSO", _MARGEM, 404, color=HEX_BRAND_BLUE)
        hl_cta = [cta_keyword] if cta_keyword else None
        info = _draw_text_block(
            base, texto, (_MARGEM, 432, 980, 742),
            size=54, min_size=32, color=HEX_DARK_NAVY,
            highlight_phrases=hl_cta, highlight_color=HEX_YELLOW, leading=1.14,
        )

        _draw_rounded_card_with_shadow(
            base, box=(_MARGEM, 800, 1080 - _MARGEM, 968), radius=84,
            fill=_hex_rgba(HEX_ACTION_GREEN), shadow_alpha=60, shadow_blur=28, shadow_offset_y=14,
        )
        draw = ImageDraw.Draw(base)
        f_cta = _load_font(28 * _SCALE)
        f_tel = _load_font(42 * _SCALE)
        t1, t2 = "AGENDAR NO WHATSAPP", "(11) 94475-0009"
        w1 = draw.textlength(t1, font=f_cta)
        w2 = draw.textlength(t2, font=f_tel)
        draw.text(
            (_W2 // 2 - w1 / 2, 826 * _SCALE), t1, font=f_cta, fill=(255, 255, 255, 255)
        )
        icon_w = 50 * _SCALE
        start_x2 = int(_W2 // 2 - (w2 + icon_w) / 2)
        icy = 912 * _SCALE
        icx = start_x2 + 16 * _SCALE
        draw.ellipse(
            [icx - 22 * _SCALE, icy - 22 * _SCALE, icx + 22 * _SCALE, icy + 22 * _SCALE],
            outline=(255, 255, 255, 255), width=4 * _SCALE,
        )
        draw.polygon(
            [(icx - 20 * _SCALE, icy + 14 * _SCALE), (icx - 26 * _SCALE, icy + 26 * _SCALE), (icx - 8 * _SCALE, icy + 20 * _SCALE)],
            fill=(255, 255, 255, 255),
        )
        draw.arc(
            [icx - 11 * _SCALE, icy - 11 * _SCALE, icx + 11 * _SCALE, icy + 11 * _SCALE],
            start=35, end=235, fill=(255, 255, 255, 255), width=5 * _SCALE,
        )
        draw.text(
            (start_x2 + icon_w, 888 * _SCALE), t2, font=f_tel, fill=(255, 255, 255, 255)
        )

        _draw_rounded_card_with_shadow(
            base, box=(_MARGEM, 1008, 1080 - _MARGEM, 1152), radius=22,
            fill=(255, 255, 255, 255), shadow_alpha=28, shadow_blur=18, shadow_offset_y=6,
            outline=_hex_rgba("#E2E8F0"), outline_width=2,
        )
        draw = ImageDraw.Draw(base)
        f_eng = _load_font(24 * _SCALE)
        # Envie para outros pais
        draw.ellipse(
            [(176 - 42) * _SCALE, (1080 - 42) * _SCALE, (176 + 42) * _SCALE, (1080 + 42) * _SCALE],
            fill=_hex_rgba(HEX_BRAND_BLUE),
        )
        px, py = 176 * _SCALE, 1080 * _SCALE
        draw.polygon(
            [
                (px - 19 * _SCALE, py - 4 * _SCALE), (px + 21 * _SCALE, py - 17 * _SCALE),
                (px + 4 * _SCALE, py + 21 * _SCALE), (px - 4 * _SCALE, py + 6 * _SCALE),
            ],
            outline=(255, 255, 255, 255), width=4 * _SCALE,
        )
        draw.text((238 * _SCALE, 1046 * _SCALE), "Envie para", font=f_eng, fill=_hex_rgba(HEX_DARK_NAVY))
        draw.text((238 * _SCALE, 1078 * _SCALE), "outros pais", font=f_eng, fill=_hex_rgba(HEX_BRAND_BLUE))
        draw.line(
            [(560 * _SCALE, 1032 * _SCALE), (560 * _SCALE, 1128 * _SCALE)],
            fill=_hex_rgba("#CBD5E1"), width=2 * _SCALE,
        )
        # Salve para consultar
        draw.ellipse(
            [(640 - 42) * _SCALE, (1080 - 42) * _SCALE, (640 + 42) * _SCALE, (1080 + 42) * _SCALE],
            fill=_hex_rgba(HEX_YELLOW),
        )
        bx, by = 640 * _SCALE, 1080 * _SCALE
        draw.polygon(
            [
                (bx - 15 * _SCALE, by - 21 * _SCALE), (bx + 15 * _SCALE, by - 21 * _SCALE),
                (bx + 15 * _SCALE, by + 21 * _SCALE), (bx, by + 10 * _SCALE),
                (bx - 15 * _SCALE, by + 21 * _SCALE),
            ],
            outline=_hex_rgba(HEX_DARK_NAVY), width=4 * _SCALE,
        )
        draw.text((702 * _SCALE, 1046 * _SCALE), "Salve para", font=f_eng, fill=_hex_rgba(HEX_DARK_NAVY))
        draw.text((702 * _SCALE, 1078 * _SCALE), "consultar", font=f_eng, fill=_hex_rgba(HEX_BRAND_BLUE))

    if not info:
        info = {"font_size": 0, "auto_shrunk": False, "truncated": False, "dropped": 0, "lines": 0}

    _draw_rodape(base, slide_num, total_slides)
    if ctr_ativo:
        info["ctr_aplicado"] = {
            "lado": lado_ctr or "centro",
            "destaque": hl_ctr or (HEX_ORANGE if slide_num == 2 else HEX_YELLOW),
        }
    if card_rosto_info:
        info["card_rosto"] = card_rosto_info

    img_final = base.resize((FORMATO["largura"], FORMATO["altura"]), Image.LANCZOS)
    # Photos já vêm com UnsharpMask interno (_cover_crop); aqui só um passe leve
    # para recuperar a definição do downscale, sem halos sobre o texto antialiasado.
    img_final = img_final.filter(ImageFilter.UnsharpMask(radius=0.6, percent=55, threshold=3))
    img_final = img_final.convert("RGB")
    output = BytesIO()
    img_final.save(output, format="PNG", optimize=True)
    return output.getvalue(), info


# ─── Geração de slide a partir de template (API Pública) ──────────────────────

@overload
def create_slide_from_template(
    template_key: str,
    slide_num: int,
    texto: str,
    return_info: Literal[False] = False,
) -> bytes: ...


@overload
def create_slide_from_template(
    template_key: str,
    slide_num: int,
    texto: str,
    return_info: Literal[True],
) -> tuple[bytes, dict]: ...


def create_slide_from_template(
    template_key: str,
    slide_num: int,
    texto: str,
    return_info: bool = False,
) -> bytes | tuple[bytes, dict]:
    """
    Gera um slide 1080×1350 px em alta definição (Motor Visual Editorial HD).

    Se existir um PNG customizado em templates_base/<template_key>.png, respeita
    a base customizada; caso contrário, renderiza no padrão Editorial / AutoFlow HD
    com as fotos reais da unidade (refs/catalogo.json), cards com sombra difusa,
    grifos #FFC20E e tipografia Montserrat-Bold.
    """
    w, h = FORMATO["largura"], FORMATO["altura"]
    template = TEMPLATES.get(template_key, TEMPLATES["desconstrucao_didatica"])
    estrutura: list[SlideEstrutura] = template["estrutura"]
    idx = min(max(0, slide_num - 1), len(estrutura) - 1)
    slide_info = estrutura[idx]

    template_path = PROJECT_DIR / "templates_base" / f"{template_key}.png"
    if not os.path.exists(template_path):
        refs = [slide_info.tipo_foto] if slide_info.tipo_foto else None
        png_bytes, info = render_slide_hd(
            slide_num=slide_num,
            texto=texto,
            eixo=template.get("eixo", "Didático"),
            cta_keyword=template.get("cta_padrao", "AULA"),
            referencias=refs,
            total_slides=len(estrutura),
        )
        if return_info:
            return png_bytes, info
        return png_bytes

    # Caso exista PNG customizado em templates_base/
    img = Image.open(template_path).convert("RGBA")
    if img.size != (w, h):
        img = img.resize((w, h), Image.LANCZOS)

    draw = ImageDraw.Draw(img)
    font_label = _load_font(36)
    font_small = _load_font(34)

    fundo_claro = _fundo_e_claro(img)
    if fundo_claro:
        cor_branco = (18, 30, 54, 255)
        cor_destaque = (180, 124, 20, 255)
        cor_muted = (71, 85, 105, 230)
    else:
        cor_branco = (255, 255, 255, 255)
        cor_destaque = (255, 209, 102, 255)
        cor_muted = (255, 255, 255, 180)

    draw.text((80, 80), f"Slide {slide_num}", font=font_label, fill=cor_muted)
    draw.text((80, 125), slide_info.tipo.upper(), font=font_label, fill=cor_destaque)

    fit = fit_slide_text(texto)
    font_main = fit["font"]
    lines = fit["lines"]

    y_text = _TEXTO_Y_INI
    for line in lines:
        try:
            bbox = draw.textbbox((0, 0), line, font=font_main)
            line_h = bbox[3] - bbox[1]
        except AttributeError:
            line_h = 70
        draw.text((80, y_text), line, font=font_main, fill=cor_branco)
        y_text += line_h + _ENTRELINHAS

    if slide_num >= len(estrutura):
        cta_text = f"Comente '{template['cta_padrao']}' ou WhatsApp: (11) 94475-0009"
    else:
        cta_text = f"Comente '{template['cta_padrao']}' no Direct"
    marca_text = "@ensinamais.tatuape"

    try:
        cta_bbox = draw.textbbox((80, h - 210), cta_text, font=font_small)
        draw.rounded_rectangle(
            [cta_bbox[0] - 16, cta_bbox[1] - 8, cta_bbox[2] + 16, cta_bbox[3] + 8],
            radius=10,
            fill=(0, 0, 0, 140),
        )
    except AttributeError:
        pass

    draw.text((80, h - 210), cta_text, font=font_small, fill=cor_destaque)
    draw.text((80, h - 110), marca_text, font=font_small, fill=cor_muted)

    is_last_slide = slide_num >= len(estrutura)
    if not is_last_slide:
        arraste_text = TAG_NAVEGACAO
        font_arraste = _load_font(28)
        try:
            arr_bbox = draw.textbbox((0, 0), arraste_text, font=font_arraste)
            arr_w = arr_bbox[2] - arr_bbox[0]
            arr_h = arr_bbox[3] - arr_bbox[1]
        except AttributeError:
            arr_w, arr_h = 240, 30
        arr_x = w - arr_w - 40
        arr_y = h - arr_h - 40
        draw.text((arr_x, arr_y), arraste_text, font=font_arraste, fill=(255, 255, 255, 140))

    output = BytesIO()
    img.convert("RGB").save(output, format="PNG", quality=95)

    info = {
        "font_size": fit["font_size"],
        "auto_shrunk": fit["auto_shrunk"],
        "truncated": fit["truncated"],
        "dropped": fit["dropped"],
        "lines": len(fit["lines"]),
    }
    if return_info:
        return output.getvalue(), info
    return output.getvalue()


def generate_all_slides(
    template_key: str,
    slides: list[dict],
    prompts_data: dict | None = None,
) -> list[tuple[int, bytes, dict]]:
    """
    Gera todos os slides de um carrossel a partir de uma lista de dicts
    com campos 'slide' (int) e 'texto' (str), ou enriquecidos com o JSON
    de `prompts_data` (text_overlay, referencias e prompt_en).
    """
    if prompts_data and isinstance(prompts_data.get("slides"), list) and prompts_data["slides"]:
        return render_carousel_from_prompts(prompts_data, template_key=template_key)

    result = []
    for slide in slides:
        num = slide.get("slide", 1)
        texto = slide.get("texto", "")
        img_bytes, info = create_slide_from_template(template_key, num, texto, return_info=True)
        result.append((num, img_bytes, info))
    return result


_RE_OVERLAY_PT = re.compile(
    r"in\s+Brazilian\s+Portuguese\s*:\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def extrair_overlay_de_prompt_en(prompt_en: str) -> str:
    """Extrai o texto em português da cláusula 'text overlay in Brazilian Portuguese: ...'."""
    m = _RE_OVERLAY_PT.search(prompt_en or "")
    return m.group(1).strip() if m else ""


def render_carousel_from_prompts(
    prompts_data: dict | str,
    *,
    template_key: str = "desconstrucao_didatica",
    eixo: str | None = None,
    cta_keyword: str | None = None,
) -> list[tuple[int, bytes, dict]]:
    """
    Renderiza as 8 lâminas diretamente a partir do JSON de prompts (ou do bloco .txt
    colado pelo usuário, separado por linhas em branco).
    """
    template = TEMPLATES.get(template_key, TEMPLATES["desconstrucao_didatica"])
    eixo_final = eixo or template.get("eixo", "Didático")
    cta_final = cta_keyword or template.get("cta_padrao", "AULA")

    slides_spec: list[dict] = []
    if isinstance(prompts_data, str):
        blocos = [b.strip() for b in re.split(r"\n\s*\n", prompts_data.strip()) if b.strip()]
        for i, bloco in enumerate(blocos, start=1):
            ov = extrair_overlay_de_prompt_en(bloco) or bloco[:80]
            slides_spec.append(
                {
                    "slide_num": i,
                    "prompt_en": bloco,
                    "text_overlay": ov,
                    "referencias": ["fachada"] if i == 7 else None,
                    "destaques": None,
                    "ctr": None,
                }
            )
    elif isinstance(prompts_data, dict):
        for i, s in enumerate(prompts_data.get("slides") or [], start=1):
            if not isinstance(s, dict):
                continue
            snum = int(s.get("slide_num") or s.get("slide") or i)
            pen = s.get("prompt_en", "")
            ov = s.get("text_overlay") or extrair_overlay_de_prompt_en(pen) or s.get("texto", "")
            refs = s.get("referencias") or ([s["tipo_foto"]] if s.get("tipo_foto") else None)
            dest = s.get("destaques") or s.get("highlight_phrases")
            ctr_raw = s.get("ctr")
            slides_spec.append(
                {
                    "slide_num": snum,
                    "prompt_en": pen,
                    "text_overlay": ov,
                    "referencias": refs,
                    "destaques": list(dest) if dest else None,
                    "ctr": ctr_raw if isinstance(ctr_raw, dict) else None,
                }
            )

    total = len(slides_spec) or 8
    resultado: list[tuple[int, bytes, dict]] = []
    for item in slides_spec:
        snum = item["slide_num"]
        png_bytes, info = render_slide_hd(
            slide_num=snum,
            texto=item["text_overlay"],
            eixo=eixo_final,
            cta_keyword=cta_final,
            prompt_en=item["prompt_en"],
            referencias=item["referencias"],
            destaques=item.get("destaques"),
            ctr=item.get("ctr"),
            total_slides=total,
        )
        resultado.append((snum, png_bytes, info))
    return resultado
