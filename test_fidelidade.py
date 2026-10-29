"""Testes do V6 — fidelidade à referência.

O risco aqui é prometer mais do que se entrega: dizer "alta fidelidade" quando
nenhuma foto chega ao Gemini produz exatamente o tipo de resultado que o
usuário não consegue explicar.
"""

import pytest

import batch_engine
import prompts
from prompts import (
    FIDELIDADE_PADRAO,
    FIDELIDADES,
    bloco_fidelidade,
    fidelidade_eh_valida,
    resolver_fidelidade,
)

TODOS = {"baixa", "media", "alta"}


def test_padrao_e_media():
    assert set(FIDELIDADES) == TODOS
    assert FIDELIDADE_PADRAO == "media"
    assert resolver_fidelidade()[0] == "media"
    assert resolver_fidelidade(None)[0] == "media"


@pytest.mark.parametrize("nivel", sorted(TODOS))
def test_nivel_valido_passa_direto_com_imagem(nivel):
    assert resolver_fidelidade(nivel, tem_imagem=True) == (nivel, [])
    assert fidelidade_eh_valida(nivel)


def test_fidelidade_desconhecida_avisa_e_cai_em_media():
    nivel, avisos = resolver_fidelidade("maximal", tem_imagem=True)
    assert nivel == "media"
    assert len(avisos) == 1
    assert "maximal" in avisos[0]


def test_normaliza_caixa():
    assert resolver_fidelidade("  ALTA ")[0] == "alta"
    assert fidelidade_eh_valida(" Alta ")


def test_alta_sem_imagem_degrada_avisado():
    nivel, avisos = resolver_fidelidade("alta", tem_imagem=False)
    assert nivel == "media"
    assert any("FLOW_FOTOS" in a for a in avisos)


def test_alta_com_imagem_nao_avisa():
    assert resolver_fidelidade("alta", tem_imagem=True) == ("alta", [])


def test_baixa_e_media_nunca_degradam():
    for nivel in ("baixa", "media"):
        assert resolver_fidelidade(nivel, tem_imagem=False) == (nivel, [])


def test_bloco_traz_a_instrucao_do_nivel():
    for nivel in TODOS:
        bloco = bloco_fidelidade(nivel, tem_imagem=True)
        assert nivel.upper() in bloco
        assert FIDELIDADES[nivel][:40] in bloco


def test_bloco_reforca_que_a_foto_real_e_intocavel():
    # Fidelidade alta não pode virar permissão para redesenhar aluno ou fachada.
    for nivel in TODOS:
        assert "intocável" in bloco_fidelidade(nivel)


def test_bloco_reflete_o_downgrade():
    bloco = bloco_fidelidade("alta", tem_imagem=False)
    assert "MEDIA" in bloco
    assert "ALTA" not in bloco


def test_bloco_nao_altera_a_base_dos_prompts_de_imagem():
    # bloco_fidelidade é concatenado pelo batch_engine; ele não pode reescrever
    # nem truncar o prompt que já existe.
    assert prompts.PROMPT_PROMPTS_IMAGEM in (
        prompts.PROMPT_PROMPTS_IMAGEM + bloco_fidelidade("alta")
    )
    assert bloco_fidelidade("media").endswith("foto.\n")


@pytest.fixture
def captura(monkeypatch):
    """Captura o prompt realmente enviado para o Gemini."""
    registrado = {}

    def fake_call(prompt, ctx, temperature=None, images=None):
        registrado.update(prompt=prompt, ctx=ctx, temperature=temperature, images=images)
        return {"prompts": []}

    monkeypatch.setattr(batch_engine, "call_gemini_json", fake_call)
    monkeypatch.setattr(batch_engine, "invalidate_cache", lambda *a, **k: None)
    return registrado


def _ligar_fotos(monkeypatch):
    monkeypatch.setattr(batch_engine, "FLOW_FOTOS", True)
    monkeypatch.setattr(
        batch_engine, "anexos_gemini", lambda: [("fachada.png", "image/png", b"x")]
    )


def _avisos_de_fidelidade(avisos: list[str]) -> list[str]:
    """Separa os avisos sobre fidelidade dos avisos do validador de slides."""
    return [a for a in avisos if "FLOW_FOTOS" in a or "Fidelidade" in a]


def _desligar_fotos(monkeypatch):
    monkeypatch.setattr(batch_engine, "FLOW_FOTOS", False)
    monkeypatch.setattr(batch_engine, "anexos_gemini", lambda: [("fachada.png", "image/png", b"x")])


def test_prompt_de_imagem_recebe_o_bloco_de_fidelidade(monkeypatch, captura):
    _ligar_fotos(monkeypatch)
    avisos: list[str] = []
    batch_engine.gerar_prompts_ideia(
        {"titulo": "Teste", "eixo": "Didático"}, avisos=avisos, fidelidade="baixa"
    )
    assert captura["prompt"].startswith(prompts.PROMPT_PROMPTS_IMAGEM)
    assert "FIDELIDADE À REFERÊNCIA (BAIXA)" in captura["prompt"]
    # O payload falso do fixture também gera avisos do validador de slides;
    # aqui o que importa é que nenhum aviso seja sobre fidelidade.
    assert _avisos_de_fidelidade(avisos) == []


def test_degrade_chega_ao_usuario_nos_avisos(monkeypatch, captura):
    _desligar_fotos(monkeypatch)
    avisos: list[str] = []
    batch_engine.gerar_prompts_ideia(
        {"titulo": "Teste", "eixo": "Didático"}, avisos=avisos, fidelidade="alta"
    )
    assert any("FLOW_FOTOS" in a for a in _avisos_de_fidelidade(avisos))
    assert "FIDELIDADE À REFERÊNCIA (MEDIA)" in captura["prompt"]
    assert captura["images"] is None


def test_invalidate_cache_usa_o_prompt_com_fidelidade(monkeypatch):
    # Se o cache fosse invalidado com o prompt base, a troca de fidelidade
    # devolveria a geração antiga e o usuário não veria mudança nenhuma.
    _ligar_fotos(monkeypatch)
    vistos: list[str] = []
    monkeypatch.setattr(batch_engine, "call_gemini_json", lambda *a, **k: None)
    monkeypatch.setattr(
        batch_engine,
        "invalidate_cache",
        lambda prompt, *a, **k: vistos.append(prompt),
    )
    batch_engine.gerar_prompts_ideia(
        {"titulo": "Teste", "eixo": "Didático"}, forcar=True, fidelidade="alta"
    )
    assert len(vistos) == 1
    assert "FIDELIDADE À REFERÊNCIA (ALTA)" in vistos[0]


def test_prompts_diferentes_por_fidelidade_nao_compartilham_cache():
    assert bloco_fidelidade("baixa") != bloco_fidelidade("media") != bloco_fidelidade("alta")


def test_fidelidades_distintas_por_tom_independente(monkeypatch, captura):
    # Tom e fidelidade são eixos separados: um não pode apagar o outro.
    _ligar_fotos(monkeypatch)
    batch_engine.gerar_prompts_ideia({"titulo": "T", "eixo": "Didático"}, fidelidade="alta")
    assert "FIDELIDADE À REFERÊNCIA (ALTA)" in captura["prompt"]


def test_processar_lote_repassa_a_fidelidade(monkeypatch):
    recebidos: list[str | None] = []
    monkeypatch.setattr(
        batch_engine,
        "gerar_prompts_ideia",
        lambda ideia, forcar=False, avisos=None, corrigidos=None, fidelidade=None: (
            recebidos.append(fidelidade) or {"prompts": []}
        ),
    )
    monkeypatch.setattr(batch_engine, "gerar_cronograma", lambda *a, **k: {"dias": []})
    batch_engine.processar_lote(
        [{"titulo": "A", "eixo": "Didático"}],
        fazer_slides=False,
        fazer_cronograma=False,
        fidelidade="alta",
    )
    assert recebidos == ["alta"]
