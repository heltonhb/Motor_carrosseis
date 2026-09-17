"""
backup.py — Export/Import dos dados locais do Motor de Carrosséis (V4).

Empacota metricas.json e historico_geracoes.json em um único .zip com
manifest.json (versão/schema + timestamps) para portabilidade entre máquinas
e segurança contra perda de dados.

Uso:
    from backup import build_backup_zip, apply_backup_zip
    zip_bytes = build_backup_zip()                     # → bytes do .zip
    info = preview_backup(zip_bytes)                   # dict p/ UI
    ok, msg = apply_backup_zip(zip_bytes, mode="merge"|"replace")
"""

from __future__ import annotations

import json
import zipfile
from datetime import datetime
from io import BytesIO

from config import HISTORICO_FILE, METRICAS_FILE
from persistence import load_historico_geracoes, load_metricas

SCHEMA_VERSION = 1

# Mapa: nome dentro do zip → caminho em disco
_FILES = {
    "metricas.json": METRICAS_FILE,
    "historico_geracoes.json": HISTORICO_FILE,
}


def _load_sources() -> dict[str, list]:
    """Carrega todos os arquivos de dados. Sempre retorna listas (vazias se não houver)."""
    return {
        "metricas.json": load_metricas(),
        "historico_geracoes.json": load_historico_geracoes(),
    }


def build_backup_zip() -> bytes:
    """Gera o .zip completo com todos os dados + manifest.json. Retorna bytes."""
    buf = BytesIO()
    fontes = _load_sources()
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "arquivos": {nome: len(lista) for nome, lista in fontes.items()},
    }
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for nome, lista in fontes.items():
            zf.writestr(nome, json.dumps(lista, ensure_ascii=False, indent=2))
    return buf.getvalue()


def _read_zip(zip_bytes: bytes) -> dict[str, list]:
    """Lê um backup .zip. Retorna dict {nome_arquivo: lista}. Valida estrutura mínima."""
    out: dict[str, list] = {}
    with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
        names = set(zf.namelist())
        for nome in _FILES:
            if nome not in names:
                continue
            raw = zf.read(nome).decode("utf-8")
            data = json.loads(raw)
            if not isinstance(data, list):
                raise ValueError(f"{nome}: conteúdo não é lista JSON")
            out[nome] = data
    return out


def preview_backup(zip_bytes: bytes) -> dict:
    """Lê um backup e devolve metadados + contagens para a UI exibir antes de aplicar."""
    dados = _read_zip(zip_bytes)
    # manifest é opcional (backups antigos podem não ter)
    manifest = {}
    try:
        with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
            if "manifest.json" in zf.namelist():
                manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
    except (json.JSONDecodeError, KeyError):
        manifest = {}
    return {
        "manifest": manifest,
        "contagens": {nome: len(lista) for nome, lista in dados.items()},
        "total_itens": sum(len(v) for v in dados.values()),
    }


def _dedupe_key_metrica(m: dict) -> tuple:
    return (m.get("data", ""), m.get("titulo", ""), m.get("alcance", 0))


def _dedupe_key_geracao(g: dict) -> tuple:
    return (g.get("tipo", ""), g.get("gerado_em", ""))


def apply_backup_zip(zip_bytes: bytes, mode: str = "merge") -> tuple[bool, str]:
    """
    Aplica um backup nos arquivos locais.

    mode="merge":   mescla (sem duplicar) com os dados atuais.
    mode="replace": substitui tudo pelo conteúdo do backup.

    Retorna (sucesso, mensagem_amigável).
    """
    from persistence import _write_json  # escrita atômica já existente

    try:
        novos = _read_zip(zip_bytes)
    except (zipfile.BadZipFile, UnicodeDecodeError, ValueError, json.JSONDecodeError) as e:
        return False, f"Backup inválido: {e}"

    if mode not in ("merge", "replace"):
        return False, f"Modo desconhecido: {mode}"

    aplicados: list[str] = []

    # Métricas
    if "metricas.json" in novos:
        atuais = load_metricas()
        if mode == "replace":
            final = novos["metricas.json"]
        else:
            existentes = {_dedupe_key_metrica(m) for m in atuais}
            so_novas = [m for m in novos["metricas.json"] if _dedupe_key_metrica(m) not in existentes]
            final = atuais + so_novas
        if _write_json(METRICAS_FILE, final):
            aplicados.append(f"métricas ({len(final)} registros)")

    # Histórico de gerações
    if "historico_geracoes.json" in novos:
        atuais = load_historico_geracoes()
        if mode == "replace":
            final = novos["historico_geracoes.json"]
        else:
            existentes = {_dedupe_key_geracao(g) for g in atuais}
            so_novas = [g for g in novos["historico_geracoes.json"] if _dedupe_key_geracao(g) not in existentes]
            final = atuais + so_novas
            # mantém limite de 50 como save_geracao
            if len(final) > 50:
                final = final[-50:]
        if _write_json(HISTORICO_FILE, final):
            aplicados.append(f"histórico ({len(final)} gerações)")

    if not aplicados:
        return False, "Backup não continha dados aplicáveis."
    return True, "Backup aplicado: " + ", ".join(aplicados)
