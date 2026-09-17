"""
test_batch_engine.py — Testes do orquestrador de lote (batch_engine.py).

Usa mocks: nunca chama a API do Gemini nem renderiza imagens de verdade.
Baseado no mesmo cenário validado durante o Bloco 4.
"""

import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))

import batch_engine

IDEIA_FAKE = {
    "titulo": "Matemática no dia a dia",
    "eixo": "Didático",
    "slides_sugeridos": [
        {"slide": 1, "tipo": "Capa", "texto": "Texto da capa"},
        {"slide": 2, "tipo": "Problema", "texto": "Conteúdo"},
    ],
}


def _mock_tudo():
    return (
        patch.object(batch_engine, "call_gemini_json", return_value={"slides": []}),
        patch.object(batch_engine, "generate_all_slides", return_value=[(1, b"png", {})]),
    )


def test_processar_lote_completo():
    m1, m2 = _mock_tudo()
    with m1, m2:
        results = batch_engine.processar_lote([IDEIA_FAKE])
    assert "prompts_0" in results
    assert "slides_0" in results
    assert "cronograma" in results
    assert results["prompts_0"]["titulo"] == "Matemática no dia a dia"
    assert results["slides_0"]["images"] == [(1, b"png", {})]


def test_processar_lote_sem_cronograma():
    m1, m2 = _mock_tudo()
    with m1, m2:
        results = batch_engine.processar_lote([IDEIA_FAKE], fazer_cronograma=False)
    assert "prompts_0" in results
    assert "slides_0" in results
    assert "cronograma" not in results


def test_processar_lote_multiplas_ideias():
    ideias = [
        {**IDEIA_FAKE, "titulo": f"Ideia {i}", "eixo": eixo}
        for i, eixo in enumerate(["Didático", "Comportamental", "Diagnóstico"])
    ]
    m1, m2 = _mock_tudo()
    with m1, m2:
        results = batch_engine.processar_lote(ideias, fazer_cronograma=False)
    assert sorted(k for k in results if k.startswith("prompts_")) == [
        "prompts_0", "prompts_1", "prompts_2",
    ]
    assert sorted(k for k in results if k.startswith("slides_")) == [
        "slides_0", "slides_1", "slides_2",
    ]


def test_processar_lote_progresso_callback():
    m1, m2 = _mock_tudo()
    eventos = []
    with m1, m2:
        batch_engine.processar_lote(
            [IDEIA_FAKE],
            fazer_cronograma=True,
            on_progress=lambda s, t, m: eventos.append((s, t, m)),
        )
    # 2 ideias + 1 cronograma = total 2; evento final deve ser (2, 2)
    assert eventos[-1][0] == eventos[-1][1], "progresso deve terminar em step == total"


def test_gerar_prompts_ideia_retorna_dict():
    m1, _ = _mock_tudo()
    with m1:
        dados = batch_engine.gerar_prompts_ideia(IDEIA_FAKE)
    assert dados == {"slides": []}


def test_api_falhou_prompts_none_nao_quebra_lote():
    # se a API falha (retorna None), o lote continua sem a chave
    with patch.object(batch_engine, "call_gemini_json", return_value=None), \
         patch.object(batch_engine, "generate_all_slides", return_value=[]):
        results = batch_engine.processar_lote([IDEIA_FAKE], fazer_cronograma=False)
    assert "prompts_0" not in results  # falhou silenciosamente, sem crash
    assert "slides_0" in results
