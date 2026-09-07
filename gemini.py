"""
gemini.py — Cliente Gemini com modelos reais, retry/backoff e cache de sessão.

Correções vs. versão original:
- Lista de modelos corrigida para nomes reais da API Google
- Cache via st.session_state para evitar chamadas duplicadas
- Exceções tipadas (sem bare `except:`)
- extract_json() robusto com múltiplas estratégias de parse
"""

import json
import re
import time
import hashlib
import os

import requests
import streamlit as st


# ─── Modelos disponíveis (em ordem de preferência) ───────────────────────────
# Verificados em: https://ai.google.dev/gemini-api/docs/models
GEMINI_MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
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


def _cache_key(prompt: str, context: str) -> str:
    """Gera uma chave de cache determinística para o par (prompt, context)."""
    raw = f"{prompt}||{context}"
    return "gemini_cache_" + hashlib.md5(raw.encode()).hexdigest()[:16]


def call_gemini(prompt: str, context: str = "", max_retries: int = 3) -> str:
    """
    Chama a API Gemini com:
    - Cache por sessão (evita chamadas duplicadas idênticas)
    - Fallback automático entre modelos disponíveis
    - Retry com backoff exponencial para 429 e erros 5xx
    - Exceções tipadas (sem bare except)

    Retorna o texto gerado ou string vazia em caso de falha total.
    """
    api_key = _get_api_key()
    if not api_key:
        st.error("🔑 Chave API Gemini não encontrada. Configure na barra lateral.")
        return ""

    # ── Cache de sessão ──────────────────────────────────────────────────────
    ck = _cache_key(prompt, context)
    if ck in st.session_state:
        return st.session_state[ck]

    full_prompt = f"{prompt}\n\n{context}" if context else prompt
    payload = {"contents": [{"parts": [{"text": full_prompt}]}]}

    for model_name in GEMINI_MODELS:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{model_name}:generateContent?key={api_key}"
        )
        for attempt in range(max_retries):
            try:
                response = requests.post(url, json=payload, timeout=90)

                if response.status_code == 200:
                    data = response.json()
                    text = (
                        data.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [{}])[0]
                        .get("text", "")
                    )
                    if text:
                        # Armazena no cache de sessão
                        st.session_state[ck] = text
                        return text

                elif response.status_code == 429:
                    wait = 2 ** attempt * 2
                    st.warning(f"⏳ Rate limit ({model_name}). Aguardando {wait}s…")
                    time.sleep(wait)
                    continue  # retry no mesmo modelo

                elif response.status_code >= 500:
                    wait = 2 ** attempt
                    st.warning(
                        f"⚠️ Erro {response.status_code} em {model_name}. "
                        f"Retry {attempt + 1}/{max_retries} em {wait}s…"
                    )
                    time.sleep(wait)
                    continue  # retry no mesmo modelo

                else:
                    # 4xx não recuperáveis — tentar próximo modelo
                    st.warning(
                        f"Modelo {model_name} retornou {response.status_code}. "
                        "Tentando próximo modelo…"
                    )
                    break

            except requests.exceptions.ConnectionError:
                wait = 2 ** attempt
                if attempt < max_retries - 1:
                    st.warning(f"🔌 Erro de conexão. Retry em {wait}s…")
                    time.sleep(wait)
                else:
                    st.warning(f"Modelo {model_name} falhou por conexão.")
                    break

            except requests.exceptions.Timeout:
                wait = 2 ** attempt
                if attempt < max_retries - 1:
                    st.warning(f"⏱️ Timeout. Retry em {wait}s…")
                    time.sleep(wait)
                else:
                    st.warning(f"Modelo {model_name} timeout após {max_retries} tentativas.")
                    break

            except Exception as exc:
                st.warning(f"Modelo {model_name} erro inesperado: {str(exc)[:120]}")
                break  # não vale retry em erro desconhecido

    st.error(
        "❌ Todos os modelos Gemini estão temporariamente indisponíveis. "
        "Tente novamente em alguns minutos."
    )
    return ""


def invalidate_cache(prompt: str, context: str = "") -> None:
    """Remove uma entrada específica do cache de sessão."""
    ck = _cache_key(prompt, context)
    st.session_state.pop(ck, None)


def extract_json(text: str) -> dict:
    """
    Extrai um objeto JSON de uma resposta de texto do Gemini.
    Tenta três estratégias em ordem:
    1. Bloco de código ```json ... ```
    2. Parse direto do texto inteiro
    3. Primeiro '{' ao último '}' do texto
    Retorna dict vazio se todas falharem.
    """
    if not text:
        return {}

    # Estratégia 1: bloco de código markdown
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Estratégia 2: parse do texto inteiro
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Estratégia 3: primeiro { ao último }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            pass

    return {}
