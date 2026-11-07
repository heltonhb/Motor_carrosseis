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


def test_sorteio_de_fotos_por_nonce():
    """Sorteio aleatório entre as fotos de uma cena, estável por nonce e sem
    repetir dentro de um carrossel (papéis 0/1/2 dos slides 1/4/5)."""
    from refs_catalog import arquivos, foto_para, fotos_embaralhadas

    chave = "alunos_robotica"
    arqs = arquivos(chave)
    assert len(arqs) >= 3, "cena precisa de >=3 fotos para o teste de variedade"

    # nonce=None preserva a ordem do catálogo (compat com chamadas antigas)
    assert fotos_embaralhadas(chave, None) == arqs
    assert foto_para(chave, 0, None) == arqs[0]

    # determinístico: mesmo nonce → mesma ordem, e é permutação do catálogo
    n = 123456789
    assert fotos_embaralhadas(chave, n) == fotos_embaralhadas(chave, n)
    assert sorted(fotos_embaralhadas(chave, n)) == sorted(arqs)

    # sem repetição entre os papéis 0/1/2 (slides 1/4/5 caindo na mesma cena)
    tres = [foto_para(chave, i, n) for i in (0, 1, 2)]
    assert len(set(tres)) == 3

    # cicla quando acaba (ocorrência % len)
    assert foto_para(chave, len(arqs), n) == foto_para(chave, 0, n)

    # nonces diferentes dão ordens diferentes (é sorteio de verdade, não rotação)
    ordens = {tuple(fotos_embaralhadas(chave, k)) for k in range(1, 6)}
    assert len(ordens) > 1
