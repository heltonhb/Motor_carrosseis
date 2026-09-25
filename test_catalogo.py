"""Catálogo único de fotos (refs/catalogo.json) — prompts, validador e templates."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from refs_catalog import (
    CENAS_FOTO,
    anexos_gemini,
    cena_valida,
    chaves_cenas,
    rotulo,
    rotulos_referencias,
    texto_catalogo_para_prompt,
)
from templates import TEMPLATES


def test_catalogo_contem_cenas_e_logo():
    chaves = chaves_cenas()
    assert set(CENAS_FOTO) <= set(chaves)
    assert "logo" in chaves


def test_templates_usam_chaves_do_catalogo():
    """B5: nenhuma taxonomia divergente nas estruturas de template."""
    for tkey, tpl in TEMPLATES.items():
        for slide in tpl["estrutura"]:
            if slide.tipo_foto:
                assert cena_valida(slide.tipo_foto), (
                    f"template {tkey} slide {slide.slide}: "
                    f"tipo_foto {slide.tipo_foto!r} fora do catálogo"
                )
            if slide.usa_foto_real:
                assert slide.tipo_foto in CENAS_FOTO, (
                    f"template {tkey} slide {slide.slide}: usa_foto_real "
                    f"exige cena fotográfica (achou {slide.tipo_foto!r})"
                )


def test_prompt_de_imagem_lista_o_catalogo():
    from prompts import PROMPT_PROMPTS_IMAGEM
    assert texto_catalogo_para_prompt() in PROMPT_PROMPTS_IMAGEM
    assert "Nada fora desta lista existe" in PROMPT_PROMPTS_IMAGEM


def test_rotulos_para_ui():
    rotulos = rotulos_referencias()
    assert rotulos.get("fachada") == rotulo("fachada") != "fachada"
    assert set(rotulos) == set(chaves_cenas())


def test_anexos_gemini_opcional():
    """FLOW_FOTOS: uma foto por cena + logo, com mime type."""
    anexos = anexos_gemini()
    assert len(anexos) == len(CENAS_FOTO) + 1
    for nome, mime, dados in anexos:
        assert nome and mime.startswith("image/") and dados
