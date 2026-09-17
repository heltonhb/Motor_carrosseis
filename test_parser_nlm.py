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

from parser_nlm import extract_json, extract_json_list

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
