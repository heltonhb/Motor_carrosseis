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

from config import FONTES, FORMATO, PROJECT_DIR, TAG_NAVEGACAO
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
        fill = (*fill[:3], 245)
        if outline is None:
            outline = (255, 255, 255, 190)
            outline_width = 3

    if glass:
        _glass_fill_radial(base, (x0, y0, x1, y1), r, fill[:3], fill[3])

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
    "ser", "são", "está", "estão", "foi", "será", "tem", "não", "sim", "ou", "a",
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
    """
    Desenha texto centralizado com auto-ajuste de fonte, word-wrap em pixels
    e suporte a grifo marca-texto (#FFC20E). Retorna metadados de ajuste.
    """
    draw = ImageDraw.Draw(base)
    text_clean = (text or "").strip()
    if not text_clean:
        return {"font_size": initial_font_size, "auto_shrunk": False, "truncated": False, "dropped": 0, "lines": 0}

    ladder = [s for s in (initial_font_size, 54, 48, 44, 40, 36, 32, 28) if s <= initial_font_size]
    if not ladder:
        ladder = [initial_font_size]

    chosen_size = ladder[-1]
    chosen_font = _load_font(chosen_size * _SCALE)
    chosen_lines: list[str] = []
    auto_shrunk = False
    truncated = False
    dropped = 0

    for sz in ladder:
        f_test = _load_font(sz * _SCALE)
        lines = _wrap_text_pixels(draw, text_clean, f_test, max_w * _SCALE)
        _, total_h = _measure_lines(draw, lines, f_test, line_spacing * _SCALE)
        if total_h <= max_h * _SCALE:
            chosen_size = sz
            chosen_font = f_test
            chosen_lines = lines
            auto_shrunk = (sz != initial_font_size)
            break
    else:
        # Trunca se nem na menor fonte couber
        f_test = _load_font(ladder[-1] * _SCALE)
        lines = _wrap_text_pixels(draw, text_clean, f_test, max_w * _SCALE)
        heights, _ = _measure_lines(draw, lines, f_test, line_spacing * _SCALE)
        kept: list[str] = []
        used = 0
        for ln, h_ln in zip(lines, heights, strict=True):
            if kept and used + h_ln > max_h * _SCALE:
                break
            kept.append(ln)
            used += h_ln + line_spacing * _SCALE
        dropped = len(lines) - len(kept)
        if dropped and kept:
            kept[-1] = kept[-1].rstrip(" .,;:") + "…"
        chosen_size = ladder[-1]
        chosen_font = f_test
        chosen_lines = kept
        auto_shrunk = True
        truncated = bool(dropped)

    _, total_block_h = _measure_lines(draw, chosen_lines, chosen_font, line_spacing * _SCALE)
    if vertical_center:
        y = start_y * _SCALE + max(0, (max_h * _SCALE - total_block_h) // 2)
    else:
        y = start_y * _SCALE

    cx = center_x * _SCALE
    hl_phrases = [p.lower() for p in (highlight_phrases if highlight_phrases is not None else _auto_highlight_phrases(text_clean)) if p]

    for line in chosen_lines:
        lw = draw.textlength(line, font=chosen_font)
        bbox = draw.textbbox((0, 0), line, font=chosen_font)
        lh = bbox[3] - bbox[1]
        x = cx - lw / 2

        for s0, s1 in _highlight_spans(line, hl_phrases):
            prefix = line[:s0]
            match_str = line[s0:s1]
            pw = draw.textlength(prefix, font=chosen_font)
            mw = draw.textlength(match_str, font=chosen_font)
            pad_x = 12 * _SCALE
            pad_y = 6 * _SCALE
            hx0 = x + pw - pad_x
            hy0 = y + bbox[1] - pad_y
            hx1 = x + pw + mw + pad_x
            hy1 = y + bbox[3] + pad_y
            draw.rounded_rectangle(
                [hx0, hy0, hx1, hy1],
                radius=10 * _SCALE,
                fill=_hex_rgba(highlight_color, 255),
            )

        draw.text((x, y), line, font=chosen_font, fill=_hex_rgba(color))
        y += lh + line_spacing * _SCALE

    return {
        "font_size": chosen_size,
        "auto_shrunk": auto_shrunk,
        "truncated": truncated,
        "dropped": dropped,
        "lines": len(chosen_lines),
    }


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

def render_slide_hd(
    slide_num: int,
    texto: str,
    *,
    eixo: str = "Didático",
    cta_keyword: str = "AULA",
    prompt_en: str = "",
    referencias: list[str] | None = None,
    destaques: list[str] | None = None,
    total_slides: int = 8,
) -> tuple[bytes, dict]:
    """
    Renderiza um slide 1080×1350 no estilo Editorial / AutoFlow HD usando as fotos
    reais da unidade (refs/catalogo.json), paleta oficial e tipografia Montserrat-Bold.
    """
    cena = _inferir_cena_padrao(slide_num, texto, prompt_en, referencias)
    is_last = (slide_num >= total_slides)

    if slide_num == 1:
        foto_path = _selecionar_foto_cena(cena, indice_variacao=0)
        base = _cover_crop(foto_path, _W2, _H2)
        _desenhar_scrim(base, 0.35, (10, 22, 40), _scrim_alpha_adaptativo(_luminancia(base)), expo=1.3)

        _draw_rounded_card_with_shadow(
            base, box=(115, 420, 965, 945), radius=28, fill=(255, 255, 255, 230),
            shadow_alpha=65, shadow_blur=32, shadow_offset_y=16, glass=True, glass_blur=24,
        )
        draw = ImageDraw.Draw(base)
        pill_font = _load_font(22 * _SCALE)
        pill_txt = f"ENSINA MAIS • TATUAPÉ ({eixo.upper()})"
        pw = draw.textlength(pill_txt, font=pill_font)
        px0, px1 = _W2 // 2 - pw // 2 - 26 * _SCALE, _W2 // 2 + pw // 2 + 26 * _SCALE
        draw.rounded_rectangle([px0, 465 * _SCALE, px1, 515 * _SCALE], radius=24 * _SCALE, fill=_hex_rgba(HEX_PASTEL_BLUE))
        draw.text((_W2 // 2 - pw // 2, 476 * _SCALE), pill_txt, font=pill_font, fill=_hex_rgba(HEX_BRAND_BLUE))

        info = _draw_centered_multiline(
            base, texto, center_x=540, start_y=545, max_w=740, max_h=230,
            initial_font_size=58, color=HEX_BRAND_BLUE, highlight_color=HEX_YELLOW,
            highlight_phrases=destaques, vertical_center=True,
        )
        col_ic = _hex_rgba(HEX_BRAND_BLUE)
        _draw_icon_gamepad(draw, 370, 840, 44, col_ic)
        _draw_icon_brain_logic(draw, 540, 840, 44, col_ic)
        _draw_icon_code_window(draw, 710, 840, 44, col_ic)
        _paste_logo(base, center_x=540, top_y=70, target_w=320, invert_white_box=True)
        if not is_last:
            _draw_nav_tag(base, style="pill_white")

    elif slide_num == 2:
        base = Image.new("RGBA", (_W2, _H2), _hex_rgba(HEX_BRAND_BLUE))
        draw = ImageDraw.Draw(base)
        draw.ellipse([-220 * _SCALE, 1080 * _SCALE, 1350 * _SCALE, 1650 * _SCALE], fill=_hex_rgba(HEX_BG_SOFT))

        _draw_rounded_card_with_shadow(
            base, box=(110, 190, 970, 1060), radius=36, fill=(255, 255, 255, 255),
            shadow_alpha=55, shadow_blur=36, shadow_offset_y=20,
        )
        _draw_rounded_card_with_shadow(
            base, box=(142, 265, 938, 1025), radius=28, fill=_hex_rgba(HEX_BRAND_BLUE), shadow_alpha=0,
        )
        draw = ImageDraw.Draw(base)
        draw.rounded_rectangle([300 * _SCALE, 230 * _SCALE, 780 * _SCALE, 300 * _SCALE], radius=34 * _SCALE, fill=_hex_rgba(HEX_PASTEL_ORANGE))
        f_badge = _load_font(26 * _SCALE)
        b_txt = f"Eixo {eixo} • Tatuapé"
        bw = draw.textlength(b_txt, font=f_badge)
        draw.text((_W2 // 2 - bw // 2, 248 * _SCALE), b_txt, font=f_badge, fill=_hex_rgba(HEX_BRAND_BLUE))

        info = _draw_centered_multiline(
            base, texto, center_x=540, start_y=350, max_w=710, max_h=380,
            initial_font_size=50, color=HEX_WHITE, highlight_color=HEX_ORANGE,
            highlight_phrases=destaques, vertical_center=True,
        )
        for cx_i in (350, 540, 730):
            draw.ellipse(
                [(cx_i - 64) * _SCALE, (845 - 64) * _SCALE, (cx_i + 64) * _SCALE, (845 + 64) * _SCALE],
                outline=(255, 255, 255, 230), width=4 * _SCALE,
            )
        _draw_icon_gamepad(draw, 350, 845, 36, (255, 255, 255, 255))
        _draw_icon_code_window(draw, 540, 845, 36, (255, 255, 255, 255))
        _draw_icon_brain_logic(draw, 730, 845, 36, (255, 255, 255, 255))
        if not is_last:
            _draw_nav_tag(base, style="yellow_on_blue")

    elif slide_num == 3:
        base = Image.new("RGBA", (_W2, _H2), _hex_rgba(HEX_BG_SOFT))
        _paste_logo(base, center_x=540, top_y=80, target_w=300, invert_white_box=False)

        info = _draw_centered_multiline(
            base, texto, center_x=540, start_y=265, max_w=860, max_h=260,
            initial_font_size=48, color=HEX_BRAND_BLUE, highlight_color=HEX_YELLOW,
            highlight_phrases=destaques, vertical_center=True,
        )
        _draw_rounded_card_with_shadow(
            base, box=(95, 575, 515, 1030), radius=24, fill=_hex_rgba(HEX_WHITE),
            shadow_alpha=35, shadow_blur=24, outline=_hex_rgba("#CBD5E1"), outline_width=3,
        )
        _draw_rounded_card_with_shadow(
            base, box=(565, 575, 985, 1030), radius=24, fill=_hex_rgba(HEX_PASTEL_ORANGE),
            shadow_alpha=40, shadow_blur=24, outline=_hex_rgba(HEX_BRAND_BLUE), outline_width=5,
        )
        draw = ImageDraw.Draw(base)
        draw.ellipse([(305 - 76) * _SCALE, (730 - 76) * _SCALE, (305 + 76) * _SCALE, (730 + 76) * _SCALE], fill=_hex_rgba("#F1F5F9"))
        _draw_icon_tablet_passive(draw, 305, 730, 44, _hex_rgba("#64748B"))
        _draw_centered_multiline(
            base, "Rotina\nPassiva", center_x=305, start_y=850, max_w=340, max_h=130,
            initial_font_size=34, color="#475569", highlight_phrases=[], line_spacing=10,
        )
        draw.ellipse([(775 - 76) * _SCALE, (730 - 76) * _SCALE, (775 + 76) * _SCALE, (730 + 76) * _SCALE], fill=_hex_rgba(HEX_BRAND_BLUE))
        _draw_icon_code_window(draw, 775, 730, 44, (255, 255, 255, 255))
        _draw_centered_multiline(
            base, "Método Ativo\ne Prático", center_x=775, start_y=850, max_w=340, max_h=130,
            initial_font_size=34, color=HEX_DARK_NAVY, highlight_phrases=[], line_spacing=10,
        )
        if not is_last:
            _draw_nav_tag(base, style="dark_on_light")

    elif slide_num == 4:
        foto_path = _selecionar_foto_cena(cena, indice_variacao=1)
        base = _cover_crop(foto_path, _W2, _H2)
        _draw_rounded_card_with_shadow(
            base, box=(115, 380, 965, 955), radius=28, fill=(255, 255, 255, 230),
            shadow_alpha=60, shadow_blur=30, shadow_offset_y=14, glass=True, glass_blur=24,
        )
        draw = ImageDraw.Draw(base)
        draw.ellipse([(540 - 62) * _SCALE, (485 - 62) * _SCALE, (540 + 62) * _SCALE, (485 + 62) * _SCALE], fill=_hex_rgba(HEX_PASTEL_BLUE))
        _draw_icon_brain_logic(draw, 540, 485, 38, _hex_rgba(HEX_BRAND_BLUE))
        info = _draw_centered_multiline(
            base, texto, center_x=540, start_y=575, max_w=750, max_h=330,
            initial_font_size=50, color=HEX_BRAND_BLUE, highlight_color=HEX_YELLOW,
            highlight_phrases=destaques, vertical_center=True,
        )
        if not is_last:
            _draw_nav_tag(base, style="pill_white")

    elif slide_num == 5:
        foto_path = _selecionar_foto_cena(cena, indice_variacao=2)
        base = _cover_crop(foto_path, _W2, _H2)
        _desenhar_scrim(base, 0.45, (8, 20, 38), _scrim_alpha_adaptativo(_luminancia(base)), expo=1.2)

        _draw_rounded_card_with_shadow(
            base, box=(95, 795, 985, 1190), radius=28, fill=(255, 255, 255, 230),
            shadow_alpha=70, shadow_blur=28, shadow_offset_y=12, glass=True, glass_blur=24,
        )
        info = _draw_centered_multiline(
            base, texto, center_x=540, start_y=835, max_w=800, max_h=315,
            initial_font_size=48, color=HEX_BRAND_BLUE, highlight_color=HEX_YELLOW,
            highlight_phrases=destaques, vertical_center=True,
        )
        _paste_logo(base, center_x=540, top_y=70, target_w=300, invert_white_box=True)
        if not is_last:
            _draw_nav_tag(base, style="white_on_dark")

    elif slide_num == 6:
        base = Image.new("RGBA", (_W2, _H2), _hex_rgba(HEX_BG_SOFT))
        fotos_grid = [
            (_selecionar_foto_cena("aluno_programacao", 0), (85, 85, 520, 465)),
            (_selecionar_foto_cena("alunos_apoio", 0), (560, 85, 995, 465)),
            (_selecionar_foto_cena("laboratorio", 0), (85, 495, 520, 875)),
            (_selecionar_foto_cena("alunos_robotica", 0), (560, 495, 995, 875)),
        ]
        for f_path, (x0, y0, x1, y1) in fotos_grid:
            _draw_rounded_card_with_shadow(
                base, box=(x0 - 8, y0 - 8, x1 + 8, y1 + 8), radius=22,
                fill=(255, 255, 255, 255), shadow_alpha=38, shadow_blur=18, shadow_offset_y=8,
            )
            crop = _cover_crop(f_path, (x1 - x0) * _SCALE, (y1 - y0) * _SCALE)
            mask = Image.new("L", crop.size, 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, crop.width, crop.height], radius=16 * _SCALE, fill=255)
            base.paste(crop, (x0 * _SCALE, y0 * _SCALE), mask)

        _draw_rounded_card_with_shadow(
            base, box=(95, 910, 985, 1235), radius=26, fill=(255, 255, 255, 255),
            shadow_alpha=45, shadow_blur=24, shadow_offset_y=10,
        )
        draw = ImageDraw.Draw(base)
        loc_txt = "Rua Coelho Lisboa, 783 • Tatuapé"
        f_loc = _load_font(23 * _SCALE)
        lw = draw.textlength(loc_txt, font=f_loc)
        pin_space = 34 * _SCALE
        total_lw = lw + pin_space
        lx0, lx1 = _W2 // 2 - total_lw // 2 - 28 * _SCALE, _W2 // 2 + total_lw // 2 + 28 * _SCALE
        draw.rounded_rectangle([lx0, 932 * _SCALE, lx1, 986 * _SCALE], radius=26 * _SCALE, fill=_hex_rgba(HEX_PASTEL_ORANGE))
        pcx = int(_W2 // 2 - total_lw // 2 + 12 * _SCALE)
        pcy = 956 * _SCALE
        draw.ellipse([pcx - 10 * _SCALE, pcy - 12 * _SCALE, pcx + 10 * _SCALE, pcy + 8 * _SCALE], fill=_hex_rgba(HEX_BRAND_BLUE))
        draw.polygon([(pcx - 8 * _SCALE, pcy + 2 * _SCALE), (pcx + 8 * _SCALE, pcy + 2 * _SCALE), (pcx, pcy + 16 * _SCALE)], fill=_hex_rgba(HEX_BRAND_BLUE))
        draw.ellipse([pcx - 4 * _SCALE, pcy - 6 * _SCALE, pcx + 4 * _SCALE, pcy + 2 * _SCALE], fill=_hex_rgba(HEX_PASTEL_ORANGE))
        draw.text((pcx + 22 * _SCALE, 944 * _SCALE), loc_txt, font=f_loc, fill=_hex_rgba(HEX_DARK_NAVY))

        info = _draw_centered_multiline(
            base, texto, center_x=540, start_y=1002, max_w=820, max_h=210,
            initial_font_size=38, color=HEX_BRAND_BLUE, highlight_color=HEX_YELLOW,
            highlight_phrases=destaques, line_spacing=12, vertical_center=True,
        )
        if not is_last:
            _draw_nav_tag(base, style="dark_on_light")

    elif slide_num == 7:
        foto_path = _selecionar_foto_cena("fachada", indice_variacao=0)
        base = _cover_crop(foto_path, _W2, _H2)
        _draw_rounded_card_with_shadow(
            base, box=(110, 410, 970, 970), radius=28, fill=(255, 255, 255, 230),
            shadow_alpha=68, shadow_blur=32, shadow_offset_y=16, glass=True, glass_blur=24,
        )
        draw = ImageDraw.Draw(base)
        badge_txt = "Caso Real • Unidade Tatuapé"
        f_b = _load_font(24 * _SCALE)
        bw = draw.textlength(badge_txt, font=f_b)
        bx0, bx1 = _W2 // 2 - bw // 2 - 28 * _SCALE, _W2 // 2 + bw // 2 + 28 * _SCALE
        draw.rounded_rectangle([bx0, 455 * _SCALE, bx1, 512 * _SCALE], radius=26 * _SCALE, fill=_hex_rgba(HEX_YELLOW))
        draw.text((_W2 // 2 - bw // 2, 469 * _SCALE), badge_txt, font=f_b, fill=_hex_rgba(HEX_DARK_NAVY))

        f_quote = _load_font(92 * _SCALE)
        draw.text((160 * _SCALE, 505 * _SCALE), "“", font=f_quote, fill=_hex_rgba(HEX_BRAND_BLUE))
        info = _draw_centered_multiline(
            base, texto, center_x=540, start_y=575, max_w=750, max_h=345,
            initial_font_size=46, color=HEX_DARK_NAVY, highlight_color=HEX_PASTEL_BLUE,
            highlight_phrases=destaques, vertical_center=True,
        )
        if not is_last:
            _draw_nav_tag(base, style="pill_white")

    else:
        # Slide 8 (ou último slide): CTA Final
        base = Image.new("RGBA", (_W2, _H2), _hex_rgba(HEX_BG_SOFT))
        draw = ImageDraw.Draw(base)
        draw.ellipse([-220 * _SCALE, -420 * _SCALE, 1300 * _SCALE, 380 * _SCALE], fill=_hex_rgba(HEX_BRAND_BLUE))
        _paste_logo(base, center_x=540, top_y=70, target_w=390, invert_white_box=True)

        hl_cta = [cta_keyword] if cta_keyword else None
        info = _draw_centered_multiline(
            base, texto, center_x=540, start_y=420, max_w=840, max_h=350,
            initial_font_size=48, color=HEX_DARK_NAVY, highlight_phrases=hl_cta,
            highlight_color=HEX_YELLOW, vertical_center=True,
        )
        _draw_rounded_card_with_shadow(
            base, box=(115, 815, 965, 985), radius=85, fill=_hex_rgba(HEX_ACTION_GREEN),
            shadow_alpha=55, shadow_blur=26, shadow_offset_y=12,
        )
        draw = ImageDraw.Draw(base)
        f_cta = _load_font(32 * _SCALE)
        f_tel = _load_font(44 * _SCALE)
        t1 = "AGENDAR NO WHATSAPP"
        t2 = "(11) 94475-0009"
        w1 = draw.textlength(t1, font=f_cta)
        w2 = draw.textlength(t2, font=f_tel)
        draw.text((_W2 // 2 - w1 // 2, 842 * _SCALE), t1, font=f_cta, fill=(255, 255, 255, 255))
        icon_w = 52 * _SCALE
        total_w2 = w2 + icon_w
        start_x2 = int(_W2 // 2 - total_w2 // 2)
        icy = 925 * _SCALE
        icx = start_x2 + 18 * _SCALE
        draw.ellipse([icx - 22 * _SCALE, icy - 22 * _SCALE, icx + 22 * _SCALE, icy + 22 * _SCALE], outline=(255, 255, 255, 255), width=4 * _SCALE)
        draw.polygon([(icx - 20 * _SCALE, icy + 14 * _SCALE), (icx - 26 * _SCALE, icy + 26 * _SCALE), (icx - 8 * _SCALE, icy + 20 * _SCALE)], fill=(255, 255, 255, 255))
        draw.arc([icx - 11 * _SCALE, icy - 11 * _SCALE, icx + 11 * _SCALE, icy + 11 * _SCALE], start=35, end=235, fill=(255, 255, 255, 255), width=5 * _SCALE)
        draw.text((start_x2 + icon_w, 898 * _SCALE), t2, font=f_tel, fill=(255, 255, 255, 255))

        _draw_rounded_card_with_shadow(
            base, box=(140, 1065, 940, 1210), radius=24, fill=(255, 255, 255, 255),
            shadow_alpha=30, shadow_blur=18, shadow_offset_y=6,
        )
        draw = ImageDraw.Draw(base)
        draw.ellipse([(240 - 44) * _SCALE, (1137 - 44) * _SCALE, (240 + 44) * _SCALE, (1137 + 44) * _SCALE], fill=_hex_rgba(HEX_BRAND_BLUE))
        px, py = 240 * _SCALE, 1137 * _SCALE
        draw.polygon([(px - 20 * _SCALE, py - 4 * _SCALE), (px + 22 * _SCALE, py - 18 * _SCALE), (px + 4 * _SCALE, py + 22 * _SCALE), (px - 4 * _SCALE, py + 6 * _SCALE)], outline=(255, 255, 255, 255), width=4 * _SCALE)
        f_eng = _load_font(25 * _SCALE)
        draw.text((305 * _SCALE, 1108 * _SCALE), "Envie para", font=f_eng, fill=_hex_rgba(HEX_DARK_NAVY))
        draw.text((305 * _SCALE, 1142 * _SCALE), "outros pais", font=f_eng, fill=_hex_rgba(HEX_BRAND_BLUE))
        draw.line([(555 * _SCALE, 1095 * _SCALE), (555 * _SCALE, 1180 * _SCALE)], fill=_hex_rgba("#CBD5E1"), width=3 * _SCALE)
        draw.ellipse([(635 - 44) * _SCALE, (1137 - 44) * _SCALE, (635 + 44) * _SCALE, (1137 + 44) * _SCALE], fill=_hex_rgba(HEX_YELLOW))
        bx, by = 635 * _SCALE, 1137 * _SCALE
        draw.polygon(
            [(bx - 16 * _SCALE, by - 22 * _SCALE), (bx + 16 * _SCALE, by - 22 * _SCALE), (bx + 16 * _SCALE, by + 22 * _SCALE), (bx, by + 10 * _SCALE), (bx - 16 * _SCALE, by + 22 * _SCALE)],
            outline=_hex_rgba(HEX_DARK_NAVY), width=4 * _SCALE,
        )
        draw.text((700 * _SCALE, 1108 * _SCALE), "Salve para", font=f_eng, fill=_hex_rgba(HEX_DARK_NAVY))
        draw.text((700 * _SCALE, 1142 * _SCALE), "consultar", font=f_eng, fill=_hex_rgba(HEX_BRAND_BLUE))

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
            slides_spec.append(
                {
                    "slide_num": snum,
                    "prompt_en": pen,
                    "text_overlay": ov,
                    "referencias": refs,
                    "destaques": list(dest) if dest else None,
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
            total_slides=total,
        )
        resultado.append((snum, png_bytes, info))
    return resultado
