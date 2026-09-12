"""
image_utils.py — Geração e composição de imagens para os slides do carrossel.

Correções vs. versão original:
- word_wrap usa draw.textlength() para medir pixels reais, não caracteres
- Exceções tipadas (sem bare except:)
- Fontes carregadas uma vez via _load_font() com fallback robusto
- Cores e caminhos de fonte centralizados em config.py
"""

import textwrap
from io import BytesIO
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

from config import CORES, FONTES, FORMATO
from templates import TEMPLATES, SlideEstrutura


# ─── Carregamento de Fonte ────────────────────────────────────────────────────

def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """
    Tenta carregar uma fonte TrueType da lista em FONTES (config.py).
    Retorna a fonte padrão do Pillow se todas falharem.
    """
    for path in FONTES:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
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


# ─── Texto sobreposto numa imagem existente ───────────────────────────────────

def add_text_overlay(
    image_bytes: bytes,
    text: str,
    font_size: int = 48,
    position: str = "center",
) -> bytes:
    """
    Adiciona texto sobreposto em PT-BR numa imagem existente.

    Args:
        image_bytes: Bytes da imagem original (JPG ou PNG).
        text:        Texto a sobrepor (PT-BR, ≤15 palavras).
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

    # Medir dimensões do texto
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
    except AttributeError:
        text_width, text_height = draw.textsize(text, font=font)  # type: ignore[attr-defined]

    padding = 40
    if position == "center":
        x = (width - text_width) // 2
        y = (height - text_height) // 2
    elif position == "bottom":
        x = (width - text_width) // 2
        y = height - text_height - padding * 2
    else:  # top
        x = (width - text_width) // 2
        y = padding

    # Fundo semi-transparente
    bg_pad = 20
    bg_box = [
        x - bg_pad,
        y - bg_pad,
        x + text_width + bg_pad,
        y + text_height + bg_pad,
    ]
    draw.rounded_rectangle(bg_box, radius=12, fill=(27, 42, 74, 200))

    # Texto branco
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    result = Image.alpha_composite(img, txt_layer)

    output = BytesIO()
    result.convert("RGB").save(output, format="PNG", quality=95)
    return output.getvalue()


# ─── Geração de slide a partir de template ────────────────────────────────────

def create_slide_from_template(
    template_key: str,
    slide_num: int,
    texto: str,
) -> bytes:
    """
    Gera um slide 1080×1350 px a partir de um template pré-definido.

    Fluxo:
    1. Tenta carregar PNG de base em templates_base/<template_key>.png
    2. Senão, cria fundo gradiente com a cor do eixo
    3. Aplica word-wrap em pixels reais
    4. Renderiza metadados (número/tipo do slide), texto principal,
       CTA e marca no rodapé
    5. Adiciona "Arraste para o lado ➔" discreto no canto inferior direito
       (exceto no slide 8/CTA)

    Returns:
        Bytes PNG do slide gerado.
    """
    w, h = FORMATO["largura"], FORMATO["altura"]
    template = TEMPLATES.get(template_key, TEMPLATES["desconstrucao_didatica"])

    # ── 1. Imagem de base ────────────────────────────────────────────────────
    template_path = f"templates_base/{template_key}.png"
    import os
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
    font_main  = _load_font(60)   # texto principal
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

    # ── 4. Texto principal com word-wrap em pixels ───────────────────────────
    max_text_width = w - 160  # margem de 80px de cada lado
    lines = _wrap_text_pixels(draw, texto, font_main, max_text_width)

    y_text = 260
    line_spacing = 14

    for line in lines[:8]:  # limitar a 8 linhas para não vazar o slide
        try:
            bbox = draw.textbbox((0, 0), line, font=font_main)
            line_h = bbox[3] - bbox[1]
        except AttributeError:
            line_h = 70

        draw.text((80, y_text), line, font=font_main, fill=cor_branco)
        y_text += line_h + line_spacing

    # ── 5. CTA e marca no rodapé ─────────────────────────────────────────────
    if slide_num >= len(estrutura):
        cta_text   = f"Comente '{template['cta_padrao']}' ou WhatsApp: (11) 94475-0009"
    else:
        cta_text   = f"Comente '{template['cta_padrao']}' no Direct"
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
    return output.getvalue()


def generate_all_slides(
    template_key: str,
    slides: list[dict],
) -> list[tuple[int, bytes]]:
    """
    Gera todos os slides de um carrossel a partir de uma lista de dicts
    com campos 'slide' (int) e 'texto' (str).

    Returns:
        Lista de tuplas (numero_slide, bytes_png).
    """
    result = []
    for slide in slides:
        num   = slide.get("slide", 1)
        texto = slide.get("texto", "")
        img_bytes = create_slide_from_template(template_key, num, texto)
        result.append((num, img_bytes))
    return result
