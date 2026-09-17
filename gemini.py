"""
gemini.py — Cliente Gemini com SDK nativo, structured output e cache de sessão.

Migração v2 (SDK nativo):
- google-genai SDK (substitui requests.post manuais)
- Structured JSON output via response_mime_type — elimina regex de parsing
- Retry/backoff e fallback entre modelos mantidos
- Cache via st.session_state preservado
"""

import json
import re
import time
import hashlib
import os
import logging

from google import genai
from google.genai import types

import streamlit as st

from prompts import SYSTEM_INSTRUCTION_PERSONA
from parser_nlm import extract_json

logger = logging.getLogger(__name__)

# ─── Modelos disponíveis (em ordem de preferência) ───────────────────────────
GEMINI_MODELS = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
]


def _get_api_key() -> str:
    """
    Busca a chave API na seguinte ordem de prioridade:
    1. st.session_state (digitada pelo usuário na sidebar)
    2. st.secrets (Streamlit Cloud / .streamlit/secrets.toml)
    3. Variável de ambiente GEMINI_API_KEY
    Nunca usa valor hardcoded.
    """
    # 1. Digitada pelo usuário na UI
    key = st.session_state.get("gemini_key", "").strip()
    if key:
        return key

    # 2. Streamlit secrets (produção / desenvolvimento via secrets.toml)
    try:
        key = st.secrets.get("GEMINI_API_KEY", "").strip()
        if key:
            return key
    except Exception:
        pass

    # 3. Variável de ambiente (desenvolvimento local com .env)
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return key


def _get_client() -> genai.Client | None:
    """Retorna um client Gemini configurado ou None se não houver chave."""
    api_key = _get_api_key()
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


def _cache_key(prompt: str, context: str) -> str:
    """Gera uma chave de cache determinística para o par (prompt, context)."""
    raw = f"{prompt}||{context}"
    return "gemini_cache_" + hashlib.md5(raw.encode()).hexdigest()[:16]


def _is_rate_limit(exc: Exception) -> bool:
    """Verifica se a exceção é um erro de rate limit (429)."""
    msg = str(exc).lower()
    return "429" in msg or "resource_exhausted" in msg or "rate" in msg


def _is_server_error(exc: Exception) -> bool:
    """Verifica se a exceção é um erro de servidor (5xx)."""
    msg = str(exc)
    return any(code in msg for code in ("500", "502", "503", "504"))


def call_gemini(prompt: str, context: str = "", max_retries: int = 3, temperature: float = 0.7) -> str:
    """
    Chama a API Gemini via SDK nativo com:
    - Cache por sessão (evita chamadas duplicadas idênticas)
    - Fallback automático entre modelos disponíveis
    - Retry com backoff exponencial para 429 e erros 5xx
    - Exceções tipadas (sem bare except)

    Retorna o texto gerado ou string vazia em caso de falha total.
    """
    client = _get_client()
    if not client:
        st.error("🔑 Chave API Gemini não encontrada. Configure na barra lateral.")
        return ""

    # ── Cache de sessão ──────────────────────────────────────────────────────
    ck = _cache_key(prompt, context)
    if ck in st.session_state:
        return st.session_state[ck]

    full_prompt = f"{prompt}\n\n{context}" if context else prompt

    for model_name in GEMINI_MODELS:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION_PERSONA,
                        temperature=temperature,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )

                text = response.text or ""
                if text:
                    st.session_state[ck] = text
                    return text

            except Exception as exc:
                if _is_rate_limit(exc):
                    wait = 2 ** attempt * 2
                    st.warning(f"⏳ Rate limit ({model_name}). Aguardando {wait}s…")
                    time.sleep(wait)
                    continue

                elif _is_server_error(exc):
                    wait = 2 ** attempt
                    st.warning(
                        f"⚠️ Erro servidor em {model_name}. "
                        f"Retry {attempt + 1}/{max_retries} em {wait}s…"
                    )
                    time.sleep(wait)
                    continue

                else:
                    logger.warning(
                        "Modelo %s erro: %s", model_name, str(exc)[:200]
                    )
                    st.warning(
                        f"Modelo {model_name} indisponível. Tentando próximo…"
                    )
                    break  # próximo modelo

    st.error(
        "❌ Todos os modelos Gemini estão temporariamente indisponíveis. "
        "Tente novamente em alguns minutos."
    )
    return ""


def call_gemini_json(
    prompt: str,
    context: str = "",
    max_retries: int = 3,
    temperature: float = 0.7,
) -> dict:
    """
    Chama a API Gemini com JSON estruturado garantido.

    Usa response_mime_type="application/json" do SDK — o modelo retorna
    JSON válido diretamente, eliminando a necessidade de regex/parsing.
    Em caso de falha no structured output, faz fallback para call_gemini
    + extract_json.

    Retorna dict com os dados ou dict vazio em caso de falha.
    """
    client = _get_client()
    if not client:
        st.error("🔑 Chave API Gemini não encontrada. Configure na barra lateral.")
        return {}

    # ── Cache de sessão (prefixo diferente para JSON) ────────────────────────
    ck = _cache_key(prompt, context) + "_json"
    if ck in st.session_state:
        return st.session_state[ck]

    full_prompt = f"{prompt}\n\n{context}" if context else prompt

    for model_name in GEMINI_MODELS:
        for attempt in range(max_retries):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_INSTRUCTION_PERSONA,
                        response_mime_type="application/json",
                        temperature=temperature,
                        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    ),
                )

                text = response.text or ""
                if text:
                    data = json.loads(text)
                    st.session_state[ck] = data
                    return data

            except json.JSONDecodeError:
                # Modelo retornou texto inválido mesmo com mime_type JSON
                logger.warning(
                    "Modelo %s retornou JSON inválido, tentando extract_json",
                    model_name,
                )
                data = extract_json(response.text if response else "")
                if data:
                    st.session_state[ck] = data
                    return data
                break  # próximo modelo

            except Exception as exc:
                if _is_rate_limit(exc):
                    wait = 2 ** attempt * 2
                    st.warning(f"⏳ Rate limit ({model_name}). Aguardando {wait}s…")
                    time.sleep(wait)
                    continue

                elif _is_server_error(exc):
                    wait = 2 ** attempt
                    st.warning(
                        f"⚠️ Erro servidor em {model_name}. "
                        f"Retry {attempt + 1}/{max_retries} em {wait}s…"
                    )
                    time.sleep(wait)
                    continue

                else:
                    logger.warning(
                        "Modelo %s erro: %s", model_name, str(exc)[:200]
                    )
                    st.warning(
                        f"Modelo {model_name} indisponível. Tentando próximo…"
                    )
                    break

    # ── Fallback: call_gemini + extract_json ──────────────────────────────────
    st.warning("⚠️ JSON estruturado falhou. Tentando modo texto + parsing…")
    raw = call_gemini(prompt, context, max_retries, temperature)
    if raw:
        data = extract_json(raw)
        if data:
            ck_base = _cache_key(prompt, context) + "_json"
            st.session_state[ck_base] = data
            return data

    return {}


def invalidate_cache(prompt: str, context: str = "") -> None:
    """Remove entradas do cache de sessão (texto e JSON)."""
    ck = _cache_key(prompt, context)
    st.session_state.pop(ck, None)
    st.session_state.pop(ck + "_json", None)


def _clean_json_string(s: str) -> str:
    """Limpa ruídos comuns do NotebookLM que quebram json.loads."""
    # Remove citações como [1], [2], [1, 2] que o NotebookLM insere dentro ou fora do JSON
    s = re.sub(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]", "", s)
    # Remove vírgulas extras antes de fechamento de chaves ou colchetes (ex: { "a": 1, })
    s = re.sub(r",\s*([\]}])", r"\1", s)
    # Remove quebras de linha dentro de strings JSON (substitui por espaço)
    # Pega strings entre aspas e substitui quebras de linha por espaço
    def fix_newlines_in_strings(match):
        content = match.group(0)
        # Substitui quebras de linha por espaço dentro da string
        return content.replace("\n", " ").replace("\r", " ")
    
    # Padrão para strings JSON: "texto com possíveis quebras"
    s = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_newlines_in_strings, s)
    
    # Remove caracteres de controle restantes que possam quebrar o JSON
    s = re.sub(r"[\x00-\x1f\x7f]", " ", s)
    
    return s

