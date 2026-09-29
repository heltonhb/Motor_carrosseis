"""
test_parser_nlm.py — Testes do parser JSON unificado (parser_nlm.py).

Cobertura baseada em saídas REAIS do NotebookLM e Gemini:
- JSON limpo direto
- JSON em bloco de código markdown (```json ... ```)
- JSON com ruído antes/depois
- JSON com vírgula extra (trailing comma)
- JSON truncado (retorna {} — não pode crashar)
- texto sem JSON nenhum (retorna {})
- lista JSON (extract_json_list)
- entrada vazia
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from parser_nlm import extract_ideas_from_text, extract_json, extract_json_list, is_guideline_noise

# ─── extract_json ────────────────────────────────────────────────────────────

def test_json_direto():
    assert extract_json('{"ideias": [{"titulo": "x"}]}') == {"ideias": [{"titulo": "x"}]}


def test_json_em_bloco_markdown():
    texto = "Aqui está a análise:\n```json\n{\"ideias\": [1, 2]}\n```\nFim."
    assert extract_json(texto) == {"ideias": [1, 2]}


def test_json_em_bloco_sem_tag():
    texto = "Resultado:\n```\n{\"tendencias\": []}\n```\n"
    assert extract_json(texto) == {"tendencias": []}


def test_json_com_ruido_antes_e_depois():
    texto = 'Introdução longa do NLM...\n{"kpi": "salvamentos"}\nConclusão do texto.'
    assert extract_json(texto) == {"kpi": "salvamentos"}


def test_json_com_virgula_extra():
    # LLMs adoram deixar vírgula no final antes de }
    texto = '{"a": 1, "b": 2,}'
    assert extract_json(texto) == {"a": 1, "b": 2}


def test_json_truncado_nao_crasha():
    # JSON cortado no meio deve retornar {} e não levantar exceção
    texto = '{"ideias": [{"titulo": "Matemática divertida", "eixo": "Did'
    assert extract_json(texto) == {}


def test_sem_json_retorna_vazio():
    assert extract_json("Texto corrido sem nenhuma estrutura JSON aqui.") == {}


def test_vazio_retorna_vazio():
    assert extract_json("") == {}
    assert extract_json(None) == {}


def test_multiplas_chaves_aninhadas():
    texto = '```json\n{"semana_1": [{"dia": "seg"}], "semana_2": [{"dia": "qui"}], "obs": "x"}\n```'
    data = extract_json(texto)
    assert data["semana_1"][0]["dia"] == "seg"
    assert data["semana_2"][0]["dia"] == "qui"


def test_output_real_nlm_com_prefixo():
    # Formato real observado: NLM às vezes prefixa "Answer:"
    texto = "Answer:\n```json\n{\"ideias\": [{\"titulo\": \"Robótica nas férias\"}]}\n```"
    data = extract_json(texto)
    assert data["ideias"][0]["titulo"] == "Robótica nas férias"


# ─── extract_json_list ───────────────────────────────────────────────────────

def test_lista_direta():
    assert extract_json_list('[{"a": 1}, {"a": 2}]') == [{"a": 1}, {"a": 2}]


def test_lista_em_bloco_markdown():
    texto = "```json\n[{\"x\": true}]\n```"
    assert extract_json_list(texto) == [{"x": True}]


def test_lista_com_ruido():
    texto = 'Antes\n[{"item": 1}]\nDepois'
    assert extract_json_list(texto) == [{"item": 1}]


def test_lista_sem_json():
    assert extract_json_list("sem lista") == []
    assert extract_json_list("") == []


def test_objeto_nao_e_lista():
    # se o texto tem objeto (não array), extract_json_list deve devolver []
    assert extract_json_list('{"a": 1}') == []


# ─── is_guideline_noise ──────────────────────────────────────────────────────

def test_is_guideline_noise_detecta_diretrizes():
    assert is_guideline_noise("Portfolio Estrito") is True
    assert is_guideline_noise("Zero Menção a Personagens") is True
    assert is_guideline_noise("Ineditismo Total") is True
    assert is_guideline_noise("Ancoragem Local") is True
    assert is_guideline_noise("Call to Action Direto") is True
    assert is_guideline_noise("Capa") is False
    assert is_guideline_noise("A Cultura do Rascunho em Matemática") is False


def test_extract_json_envelope_cli_answer():
    envelope = '{"answer": "{\\"ideias\\": [{\\"titulo\\": \\"Robótica\\"}]}", "conversation_id": "abc"}'
    data = extract_json(envelope)
    assert "ideias" in data
    assert data["ideias"][0]["titulo"] == "Robótica"


# ─── extract_ideas_from_text ─────────────────────────────────────────────────

def test_extract_ideas_filtra_preambulo_e_diretrizes():
    texto_com_ruido = """
    Oi! Aqui é a Carol.
    Diretrizes seguidas:
    1. **Portfolio Estrito**: focar em exatas.
    2. **Zero Menção a Personagens**: nenhuma menção.
    3. **Ineditismo Total**: sem repetições.

    ### 💡 IDEIA 1: A "Cultura do Rascunho" em Matemática
    * **Eixo Temático**: Desconstrução Didática Prática
    * **Curso Oficial**: Apoio Escolar — Matemática (Ensino Fundamental)
    * **Palavra-chave (CTA)**: `RASCUNHO`
    * **Justificativa Estratégica**: Reduz perda de notas por falta de organização.

    #### Estrutura dos Slides:
    1. **Capa**: Seu filho perde pontos por erros bobos no rascunho?
    2. **Segunda Capa**: O problema não é falta de estudo, é organização visual.
    3. **Problema**: Provas exigentes demandam rascunho estruturado.
    4. **CTA**: Comente RASCUNHO no WhatsApp.

    ### 💡 IDEIA 2: Vocabulário Passivo vs Ativo na Redação
    * **Eixo Temático**: Diagnóstico Pedagógico
    * **Curso Oficial**: Apoio Escolar — Português (Ensino Fundamental)
    * **Palavra-chave (CTA)**: `REDACAO`
    * **Justificativa Estratégica**: Destrava escrita e argumentação.
    """
    ideias = extract_ideas_from_text(texto_com_ruido)
    assert len(ideias) == 2
    titulos = [i["titulo"] for i in ideias]
    assert "Portfolio Estrito" not in titulos
    assert "Zero Menção a Personagens" not in titulos
    assert 'A "Cultura do Rascunho" em Matemática' in titulos
    assert "Vocabulário Passivo vs Ativo na Redação" in titulos
    # Verifica que completou os 8 slides
    for i in ideias:
        assert len(i["slides_sugeridos"]) == 8
        assert i["cta"] in ("RASCUNHO", "REDACAO")

