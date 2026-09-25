"""Pós-processamento _enforce_foto_real (batch_engine)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from batch_engine import _FRASE_TAG, _enforce_foto_real
from config import TAG_NAVEGACAO
from refs_catalog import CENAS_FOTO, cena_valida


def _dados() -> dict:
    return {
        "slides": [
            {
                "slide_num": "1",
                "prompt_en": (
                    "Professional Instagram carousel slide 1, 1080x1350, vertical. "
                    "Minimalist design, off-white background #F7F9FF."
                ),
                "text_overlay": "A diferença entre usar tecnologia e saber programá-la",
            },
            {
                "slide_num": 4,
                "prompt_en": "Instagram carousel slide 4, 1080x1350. Floating white card...",
                "text_overlay": "Conexões neurais",
                "referencias": ["foto_anexada", "fachada"],
            },
            {
                "slide_num": 8,
                "prompt_en": "Final CTA slide with green pill button.",
                "text_overlay": "Comente AULA ou chame no WhatsApp (11) 94475-0009",
            },
        ]
    }


def test_reescreve_slides_thumbnail_com_foto_real():
    res = _enforce_foto_real(_dados())
    for slide in res["slides"]:
        if slide["slide_num"] in {1, 4, "1", "4"}:
            assert slide["prompt_en"].lower().startswith("authentic school photo")
            assert slide["usa_foto_real"] is True
            assert slide["tipo_foto"] in CENAS_FOTO
            # regra 6: tag no prompt_en, regra 7: cláusula anti-personagem
            assert _FRASE_TAG in slide["prompt_en"]
            assert "no cartoon characters" in slide["prompt_en"].lower()
            # padrões genéricos removidos
            assert "off-white background" not in slide["prompt_en"].lower()
            assert "floating white card" not in slide["prompt_en"].lower()


def test_preserva_overlay_e_slide_nao_thumbnail():
    res = _enforce_foto_real(_dados())
    s1 = res["slides"][0]
    assert "A diferença entre usar tecnologia e saber programá-la" in s1["prompt_en"]
    s8 = res["slides"][2]
    assert s8["prompt_en"] == "Final CTA slide with green pill button."
    assert _FRASE_TAG not in s8["prompt_en"]


def test_referencias_limpas_e_validas():
    res = _enforce_foto_real(_dados())
    refs = res["slides"][1]["referencias"]
    assert all(cena_valida(r) for r in refs)
    assert "foto_anexada" not in refs
    assert any(r in CENAS_FOTO for r in refs)


def test_snum_string_ainda_processado():
    """slide_num pode chegar como string do JSON — não pode ser pulado."""
    res = _enforce_foto_real(_dados())
    assert res["slides"][0]["tipo_foto"] in CENAS_FOTO


def test_corrigidos_registra_acoes():
    dados = _dados()
    corrigidos: list = []
    _enforce_foto_real(dados, corrigidos=corrigidos)
    assert any("slide 4" in c for c in corrigidos)


def test_payload_invalido_passa_adiano():
    assert _enforce_foto_real(None) is None  # type: ignore[arg-type]
    assert _enforce_foto_real({"slides": []}) == {"slides": []}


def test_tag_constante():
    assert TAG_NAVEGACAO == "Mova para o próximo ➔"
