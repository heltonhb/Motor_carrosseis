"""
refs_catalog.py — Catálogo único dos ativos fotográficos reais da unidade.

Fonte: refs/catalogo.json. Este módulo é a única porta de acesso às fotos:
o prompt de imagem lista as cenas, o validador checa `referencias`, a aba
Prompts rotula e o export do Flow aponta os arquivos que o usuário deve
anexar como referência no Google Flow.

Nenhuma foto é gerada ou editada aqui — o app só produz prompts.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

REFS_DIR = Path(__file__).resolve().parent / "refs"
CATALOGO_PATH = REFS_DIR / "catalogo.json"

# Chaves de cena que são fotografias reais da unidade (elegíveis como
# "foto real" nos slides thumbnail 1, 4 e 5). O logo não entra.
CENAS_FOTO = (
    "fachada",
    "recepcao_unidade",
    "equipe",
    "alunos_robotica",
    "aluno_programacao",
    "alunos_apoio",
    "laboratorio",
)


@lru_cache(maxsize=1)
def carregar_catalogo() -> dict:
    """Lê refs/catalogo.json. Sem arquivo válido → catálogo vazio (fallback textual)."""
    try:
        dados = json.loads(CATALOGO_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("catalogo.json ilegível (%s); seguindo sem ativos", exc)
        return {"cenas": {}, "excluidas": {}}
    if not isinstance(dados, dict) or not isinstance(dados.get("cenas"), dict):
        return {"cenas": {}, "excluidas": {}}
    return dados


def cenas() -> dict:
    """Mapa chave → metadados do catálogo."""
    return carregar_catalogo().get("cenas", {})


def chaves_cenas() -> tuple[str, ...]:
    return tuple(cenas().keys())


def cena_valida(chave: str) -> bool:
    return isinstance(chave, str) and chave in cenas()


def rotulo(chave: str) -> str:
    cena = cenas().get(chave)
    return cena.get("rotulo", chave) if isinstance(cena, dict) else chave


def desc_en(chave: str) -> str:
    cena = cenas().get(chave)
    return cena.get("desc_en", "") if isinstance(cena, dict) else ""


def rotulos_referencias() -> dict[str, str]:
    """Mapa chave → rótulo para a UI da aba Prompts."""
    return {chave: rotulo(chave) for chave in cenas()}


def arquivos(chave: str) -> list[Path]:
    """Arquivos existentes de uma cena (relativos a refs/)."""
    cena = cenas().get(chave)
    if not isinstance(cena, dict):
        return []
    return [REFS_DIR / nome for nome in cena.get("arquivos", []) if (REFS_DIR / nome).is_file()]


def arquivo_principal(chave: str) -> str | None:
    """Caminho relativo do primeiro arquivo da cena (para exibir/exportar)."""
    lista = arquivos(chave)
    if not lista:
        return None
    try:
        return str(lista[0].relative_to(Path(__file__).resolve().parent))
    except ValueError:
        return str(lista[0])


def texto_catalogo_para_prompt() -> str:
    """Catálogo em texto para o prompt de imagem (rótulo + descrição EN + uso)."""
    linhas = []
    for chave, cena in cenas().items():
        if not isinstance(cena, dict):
            continue
        uso = cena.get("uso", "")
        linha = f'• "{chave}" — {cena.get("rotulo", chave)}: {cena.get("desc_en", "")}'
        if uso:
            linha += f" (uso típico: {uso})"
        linhas.append(linha)
    return "\n".join(linhas) or "• (catálogo de fotos indisponível — descreva a cena ideal)"


_MIME_POR_EXT = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def anexos_gemini(max_bytes: int = 4 * 1024 * 1024) -> list[tuple[str, str, bytes]]:
    """Arquivo principal de cada cena + logo, para anexar ao Gemini.

    Retorna tuplas (nome, mime_type, bytes). Só é usada quando a flag
    FLOW_FOTOS=true — o padrão é gerar prompts apenas com texto.
    """
    anexos: list[tuple[str, str, bytes]] = []
    for chave in (*CENAS_FOTO, "logo"):
        arqs = arquivos(chave)
        if not arqs:
            continue
        caminho = arqs[0]
        try:
            dados = caminho.read_bytes()
        except OSError:
            continue
        if len(dados) > max_bytes:
            continue
        mime = _MIME_POR_EXT.get(caminho.suffix.lower(), "image/jpeg")
        anexos.append((caminho.name, mime, dados))
    return anexos


def listar_referencias_disponiveis() -> list[dict]:
    """Lista para a UI: chave, rótulo, caminho e nº de arquivos."""
    saida = []
    for chave in cenas():
        arqs = arquivos(chave)
        saida.append(
            {
                "chave": chave,
                "rotulo": rotulo(chave),
                "arquivo": arquivo_principal(chave),
                "n_arquivos": len(arqs),
            }
        )
    return saida
