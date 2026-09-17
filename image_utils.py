"""
image_utils.py — Geração e composição de imagens para os slides do carrossel.

Correções vs. versão original:
- word_wrap usa draw.textlength() para medir pixels reais, não caracteres
- add_text_overlay quebra o texto em múltiplas linhas via _wrap_text_pixels
  (antes media tudo como uma linha só e sangrava da imagem)
- create_slide_from_template auto-reduz a fonte principal (60→30px) até o
  texto caber na área útil; se nem no menor tamanho couber, trunca com
  reticências e sinaliza no retorno (return_info=True) — nunca some em
  silêncio
- Exceções tipadas (sem bare except:)
- Fontes carregadas via _load_font() com fallback robusto
"""

import logging
import os
from io import BytesIO
from typing import Literal, overload

from PIL import Image, ImageDraw, ImageFont

from config import FONTES, FORMATO
from templates import TEMPLATES, SlideEstrutura

logger = logging.getLogger(__name__)

# ─── Layout do slide 1080×1350 (px) ───────────────────────────────────────────
_TEXTO_Y_INI = 260                     # início da área do texto principal
_TEXTO_Y_FIM = 1070                    # fim (deixa folga antes do CTA em h-210)
_TEXTO_LARGURA = 920                   # 1080 - 2×80 de margem
_ENTRELINHAS = 14                      # espaçamento extra entre linhas

# Escada de auto-redução da fonte principal (P1)
_LADDER_FONT_MAIN = (60, 54, 48, 42, 36, 30)


# ─── Carregamento de Fonte ────────────────────────────────────────────────────

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
            # Fallback para versões antigas do Pillow
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

    Args:
        image_bytes: Bytes da imagem original (JPG ou PNG).
        text:        Texto a sobrepor (PT-BR).
        font_size:   Tamanho da fonte em pontos.
        position:    "center" | "bottom" | "top"

    Returns:
        Bytes PNG da imagem processada.
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size

    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)
    font = _load_font(font_size)

    padding = 40
    max_text_width = width - padding * 2 - 40  # folga extra além do padding
    lines = _wrap_text_pixels(draw, text, font, max_text_width)
    joined = "\n".join(lines)

    # Medir o bloco inteiro (todas as linhas)
    try:
        bbox = draw.multiline_textbbox((0, 0), joined, font=font, spacing=10)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        # Fallback: soma manual das linhas
        heights, total = _measure_lines(draw, lines, font, 10)
        text_height = total
        text_width = max(
            (draw.textlength(ln, font=font) for ln in lines), default=0
        )

    if position == "center":
        y = (height - text_height) // 2
    elif position == "bottom":
        y = height - text_height - padding * 2
    else:  # top
        y = padding
    x = (width - text_width) // 2

    # Fundo semi-transparente atrás do bloco inteiro
    bg_pad = 20
    bg_box = [
        x - bg_pad,
        y - bg_pad,
        x + text_width + bg_pad,
        y + text_height + bg_pad,
    ]
    draw.rounded_rectangle(bg_box, radius=12, fill=(27, 42, 74, 200))

    # Texto branco, centralizado por linha
    draw.multiline_text((x, y), joined, font=font, fill=(255, 255, 255, 255),
                        spacing=10, align="center")

    result = Image.alpha_composite(img, txt_layer)

    output = BytesIO()
    result.convert("RGB").save(output, format="PNG", quality=95)
    return output.getvalue()


# ─── Geração de slide a partir de template ────────────────────────────────────

@overload
def create_slide_from_template(
    template_key: str,
    slide_num: int,
    texto: str,
    return_info: Literal[True] = True,
) -> tuple[bytes, dict]: ...
@overload
def create_slide_from_template(
    template_key: str,
    slide_num: int,
    texto: str,
    return_info: Literal[False],
) -> bytes: ...
def create_slide_from_template(
    template_key: str,
    slide_num: int,
    texto: str,
    return_info: bool = False,
) -> bytes | tuple[bytes, dict]:
    """
    Gera um slide 1080×1350 px a partir de um template pré-definido.

    Fluxo:
    1. Tenta carregar PNG de base em templates_base/<template_key>.png
    2. Senão, cria fundo sólido com barra de acento no topo
    3. Ajusta a fonte principal automaticamente até o texto caber
       (nunca trunca em silêncio — ver return_info)
    4. Renderiza metadados (número/tipo do slide), texto principal,
       CTA e marca no rodapé
    5. Adiciona "Arraste para o lado ➔" discreto no canto inferior direito
       (exceto no último slide)

    Args:
        return_info: se True, retorna (bytes, info) onde info contém
            font_size, auto_shrunk, truncated e dropped para a UI exibir
            avisos de ajuste.
    """
    w, h = FORMATO["largura"], FORMATO["altura"]
    template = TEMPLATES.get(template_key, TEMPLATES["desconstrucao_didatica"])

    # ── 1. Imagem de base ────────────────────────────────────────────────────
    template_path = f"templates_base/{template_key}.png"
    if os.path.exists(template_path):
        img = Image.open(template_path).convert("RGBA")
        if img.size != (w, h):
            img = img.resize((w, h), Image.LANCZOS)
    else:
        # Fallback: fundo sólido com barra de acento no topo
        eixo_cores: dict[str, tuple[tuple[int, int, int], tuple[int, int, int]]] = {
            "Didático":      ((27, 42, 74),  (78, 205, 196)),
            "Comportamental": ((27, 42, 74), (255, 209, 102)),
            "Diagnóstico":   ((27, 42, 74),  (230, 57, 70)),
        }
        bg_rgb, accent_rgb = eixo_cores.get(template["eixo"], ((27, 42, 74), (78, 205, 196)))
        img = Image.new("RGBA", (w, h), bg_rgb)
        draw_bg = ImageDraw.Draw(img)
        draw_bg.rectangle([0, 0, w, 10], fill=accent_rgb)

    draw = ImageDraw.Draw(img)

    # ── 2. Fontes ────────────────────────────────────────────────────────────
    font_label = _load_font(36)   # metadados (slide N / tipo)
    font_small = _load_font(34)   # CTA, marca, arraste

    # ── 3. Metadados do slide ────────────────────────────────────────────────
    estrutura: list[SlideEstrutura] = template["estrutura"]
    idx = min(slide_num - 1, len(estrutura) - 1)
    slide_info = estrutura[idx]

    cor_branco    = (255, 255, 255, 255)
    cor_destaque  = (255, 209, 102, 255)   # amarelo
    cor_muted     = (255, 255, 255, 180)

    draw.text((80, 80),  f"Slide {slide_num}", font=font_label, fill=cor_muted)
    draw.text((80, 125), slide_info.tipo.upper(), font=font_label, fill=cor_destaque)

    # ── 4. Texto principal com ajuste automático (P1) ────────────────────────
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

    # ── 5. CTA e marca no rodapé ─────────────────────────────────────────────
    if slide_num >= len(estrutura):
        cta_text = f"Comente '{template['cta_padrao']}' ou WhatsApp: (11) 94475-0009"
    else:
        cta_text = f"Comente '{template['cta_padrao']}' no Direct"
    marca_text = "@ensinamais.tatuape"

    # Fundo sutil atrás do CTA
    try:
        cta_bbox = draw.textbbox((80, h - 210), cta_text, font=font_small)
        draw.rounded_rectangle(
            [cta_bbox[0] - 16, cta_bbox[1] - 8, cta_bbox[2] + 16, cta_bbox[3] + 8],
            radius=10,
            fill=(0, 0, 0, 140),
        )
    except AttributeError:
        pass

    draw.text((80, h - 210), cta_text,   font=font_small, fill=cor_destaque)
    draw.text((80, h - 110), marca_text, font=font_small, fill=cor_muted)

    # ── 6. "Arraste para o lado ➔" — canto inferior direito ─────────────────
    # Omitido no slide de CTA (último slide) pois ele não pede deslizamento
    is_last_slide = slide_num >= len(estrutura)
    if not is_last_slide:
        arraste_text = "Arraste para o lado ➔"
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

    # ── 7. Exportar ──────────────────────────────────────────────────────────
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
) -> list[tuple[int, bytes, dict]]:
    """
    Gera todos os slides de um carrossel a partir de uma lista de dicts
    com campos 'slide' (int) e 'texto' (str).

    Returns:
        Lista de tuplas (numero_slide, bytes_png, info_ajuste), onde
        info_ajuste contém font_size, auto_shrunk, truncated, dropped e
        lines (ver create_slide_from_template).
    """
    result = []
    for slide in slides:
        num   = slide.get("slide", 1)
        texto = slide.get("texto", "")
        img_bytes, info = create_slide_from_template(template_key, num, texto, return_info=True)
        result.append((num, img_bytes, info))
    return result
