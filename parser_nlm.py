"""
parser_nlm.py — Unificado de parsing JSON para NotebookLM e Gemini.
Centraliza todas as estratégias de extração de JSON.
"""

import json
import re


def _clean_json_string(text: str) -> str:
    """Remove ruídos comuns de strings JSON (vírgulas extras, etc.)."""
    # Remove vírgulas antes de chaves/colchetes fechantes
    text = re.sub(r",\s*([\]}])", r"\1", text)
    # Remove vírgulas no final de arrays/objects
    text = re.sub(r",\s*([\]}])", r"\1", text)
    # Remove múltiplos espaços
    text = re.sub(r"\s+", " ", text)
    return text


def extract_json(text: str) -> dict:
    """
    Extrai um objeto JSON de uma resposta de texto (Gemini ou NotebookLM).
    Tenta múltiplas estratégias com tolerância a ruídos de formatação.
    """
    if not text:
        return {}

    # Estratégia 1: bloco de código markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return json.loads(_clean_json_string(content))
            except json.JSONDecodeError:
                pass

    # Estratégia 2: do primeiro '{' ao último '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        content = text[start : end + 1].strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            try:
                return json.loads(_clean_json_string(content))
            except json.JSONDecodeError:
                pass

    # Estratégia 3: parse direto do texto inteiro
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        try:
            return json.loads(_clean_json_string(text.strip()))
        except json.JSONDecodeError:
            return {}


def extract_json_list(text: str) -> list:
    """
    Extrai uma lista JSON (array) de uma resposta de texto.
    """
    if not text:
        return []

    # Estratégia 1: bloco de código markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            try:
                data = json.loads(_clean_json_string(content))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

    # Estratégia 2: do primeiro '[' ao último ']'
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        content = text[start : end + 1].strip()
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            try:
                data = json.loads(_clean_json_string(content))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

    return []
