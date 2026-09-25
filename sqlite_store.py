"""Armazenamento SQLite simples para documentos JSON do aplicativo."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _connect(db_path: str) -> sqlite3.Connection:
    """Abre o banco, garantindo o schema e o modo WAL."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(path), timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            document_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.commit()
    return connection


def read_document(db_path: str, document_key: str, fallback: Any = None) -> Any:
    """Lê um documento e migra ``fallback`` quando a chave ainda não existe."""
    connection = None
    try:
        connection = _connect(db_path)
        with connection:
            row = connection.execute(
                "SELECT payload FROM documents WHERE document_key = ?",
                (document_key,),
            ).fetchone()
            if row:
                return json.loads(row[0])

            if fallback is not None:
                _write_document(connection, document_key, fallback)
            return fallback
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return fallback
    finally:
        if connection is not None:
            connection.close()


def write_document(db_path: str, document_key: str, payload: Any) -> bool:
    """Grava ou substitui um documento em uma transação SQLite."""
    connection = None
    try:
        connection = _connect(db_path)
        with connection:
            _write_document(connection, document_key, payload)
        return True
    except (OSError, sqlite3.Error, TypeError, ValueError):
        return False
    finally:
        if connection is not None:
            connection.close()


def _write_document(connection: sqlite3.Connection, document_key: str, payload: Any) -> None:
    serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    updated_at = datetime.now(UTC).isoformat(timespec="seconds")
    connection.execute(
        """
        INSERT INTO documents (document_key, payload, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(document_key) DO UPDATE SET
            payload = excluded.payload,
            updated_at = excluded.updated_at
        """,
        (document_key, serialized, updated_at),
    )
