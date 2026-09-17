"""Testes do backup V4 — export, preview e import (merge/replace)."""

from __future__ import annotations

import json

import pytest

import backup
import persistence
from persistence import _write_json


@pytest.fixture(autouse=True)
def _isolate_data(tmp_path, monkeypatch):
    """Redireciona METRICAS_FILE/HISTORICO_FILE para arquivos temporários por teste."""
    mfile = str(tmp_path / "metricas.json")
    hfile = str(tmp_path / "historico_geracoes.json")
    monkeypatch.setattr(persistence, "METRICAS_FILE", mfile)
    monkeypatch.setattr(persistence, "HISTORICO_FILE", hfile)
    # também dentro de backup.py que importa os mesmos caminhos
    monkeypatch.setattr(backup, "METRICAS_FILE", mfile)
    monkeypatch.setattr(backup, "HISTORICO_FILE", hfile)
    # _FILES mapa interno
    monkeypatch.setattr(backup, "_FILES", {
        "metricas.json": mfile,
        "historico_geracoes.json": hfile,
    })
    yield


def _setup(tmp_data: list[dict] | None = None, tmp_hist: list[dict] | None = None) -> None:
    _write_json(persistence.METRICAS_FILE, tmp_data or [])
    _write_json(persistence.HISTORICO_FILE, tmp_hist or [])


def _metrica(titulo: str, alcance: int = 1000, data: str = "2026-09-15") -> dict:
    return {
        "titulo": titulo,
        "data": data,
        "alcance": alcance,
        "taxa_salvamentos": 5.0,
        "taxa_envios": 2.0,
        "leads_whatsapp": 10,
    }


def _geracao(tipo: str, quando: str, payload: dict | None = None) -> dict:
    return {"tipo": tipo, "gerado_em": quando, "dados": payload or {"foo": 1}}


def test_backup_zip_contem_arquivos_e_manifest():
    _setup([_metrica("Post A")], [_geracao("ideias", "2026-09-15T10:00:00")])
    zb = backup.build_backup_zip()

    info = backup.preview_backup(zb)
    assert info["contagens"]["metricas.json"] == 1
    assert info["contagens"]["historico_geracoes.json"] == 1
    assert info["total_itens"] == 2
    assert info["manifest"]["schema_version"] == 1


def test_backup_zip_vazio_funciona():
    _setup([], [])
    zb = backup.build_backup_zip()
    info = backup.preview_backup(zb)
    assert info["contagens"] == {"metricas.json": 0, "historico_geracoes.json": 0}


def test_import_replace_substitui_tudo():
    _setup([_metrica("Antigo")], [_geracao("ideias", "2026-01-01T00:00:00")])
    # cria um backup com outros dados
    backup_metricas = [_metrica("Novo A"), _metrica("Novo B")]
    backup_hist = [_geracao("prompts", "2026-09-16T10:00:00", {"slides": []})]
    _write_json(persistence.METRICAS_FILE, backup_metricas)
    _write_json(persistence.HISTORICO_FILE, backup_hist)
    zb = backup.build_backup_zip()

    # agora reativa os originais e aplica replace
    _setup([_metrica("Antigo")], [])
    ok, msg = backup.apply_backup_zip(zb, mode="replace")
    assert ok, msg
    from persistence import load_historico_geracoes, load_metricas
    assert len(load_metricas()) == 2
    assert all(m["titulo"].startswith("Novo") for m in load_metricas())
    assert len(load_historico_geracoes()) == 1
    assert load_historico_geracoes()[0]["tipo"] == "prompts"


def test_import_merge_dedupe():
    existente = _metrica("Post A", alcance=1000)
    _setup([existente], [])
    # backup contém a MESMA métrica + uma nova
    _write_json(persistence.METRICAS_FILE, [_metrica("Post A", alcance=1000), _metrica("Post B", alcance=2000)])
    zb = backup.build_backup_zip()

    _setup([existente], [])
    ok, msg = backup.apply_backup_zip(zb, mode="merge")
    assert ok, msg
    from persistence import load_metricas
    metricas = load_metricas()
    assert len(metricas) == 2  # 1 antiga + 1 nova (não duplicou a existente)
    titulos = sorted(m["titulo"] for m in metricas)
    assert titulos == ["Post A", "Post B"]


def test_import_merge_respeita_limite_50_historico():
    _setup([], [_geracao("ideias", f"2026-09-{d:02d}T10:00:00") for d in range(1, 30)])  # 29 locais
    # backup com mais 30 → total 59 → deve ficar 50
    backup_hist = [_geracao("ideias", f"2026-08-{d:02d}T10:00:00") for d in range(1, 31)]
    _write_json(persistence.HISTORICO_FILE, backup_hist)
    zb = backup.build_backup_zip()

    _setup([], [_geracao("ideias", f"2026-09-{d:02d}T10:00:00") for d in range(1, 30)])
    ok, _ = backup.apply_backup_zip(zb, mode="merge")
    assert ok
    from persistence import load_historico_geracoes
    assert len(load_historico_geracoes()) == 50


def test_import_zip_invalido_retorna_erro():
    ok, msg = backup.apply_backup_zip(b"isso-nao-e-um-zip", mode="merge")
    assert not ok
    assert "invalid" in msg.lower() or "inválido" in msg.lower()


def test_import_zip_sem_lista_json_da_erro():
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("metricas.json", json.dumps({"nao": "lista"}))
    ok, msg = backup.apply_backup_zip(buf.getvalue(), mode="merge")
    assert not ok
    assert "lista" in msg.lower()
