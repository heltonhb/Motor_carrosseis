"""
test_metricas_feedback.py — Testes do pipeline de métricas (grupo 1:
feedback loop real) sobre persistence.py.

Cobre: validação (metrica_eh_valida), normalização (normalizar_metrica),
deduplicação e lote único (importar_metricas), gate do save_metrica e
limpeza (limpar_metricas_vazias). Sem rede, sem Streamlit.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import persistence
from persistence import (
    importar_metricas,
    limpar_metricas_vazias,
    load_metricas,
    metrica_eh_valida,
    normalizar_metrica,
    save_metrica,
)

# ─── metrica_eh_valida ───────────────────────────────────────────────────────

def test_valida_requer_titulo_e_alcance():
    assert metrica_eh_valida({"titulo": "Post A", "alcance": 100})
    assert not metrica_eh_valida({"titulo": "", "alcance": 100})
    assert not metrica_eh_valida({"titulo": "Post A", "alcance": 0})
    assert not metrica_eh_valida({"titulo": "Post A"})  # sem alcance
    assert not metrica_eh_valida({})  # caso real das 280 entradas de lixo
    assert not metrica_eh_valida(None)  # type: ignore[arg-type]


def test_valida_aceita_alcance_como_texto_do_csv():
    assert metrica_eh_valida({"titulo": "Post A", "alcance": "1500"})


# ─── normalizar_metrica ─────────────────────────────────────────────────────

def test_normalizar_converte_envios_em_envios_dm():
    m = normalizar_metrica({"titulo": "A", "data": "2026-09-01",
                            "alcance": "1000", "salvamentos": "40",
                            "envios": "25"})
    assert m["envios_dm"] == 25 and "envios" not in m
    assert m["alcance"] == 1000 and isinstance(m["alcance"], int)
    assert m["taxa_salvamentos"] == 4.0
    assert m["taxa_envios"] == 2.5


def test_normalizar_calcula_taxas_faltantes():
    m = normalizar_metrica({"titulo": "A", "alcance": 500, "salvamentos": 30,
                            "envios_dm": 10, "nao_seguidores": 200})
    assert m["taxa_salvamentos"] == 6.0
    assert m["taxa_envios"] == 2.0
    assert m["taxa_nao_seguidores"] == 40.0


def test_normalizar_nao_sobrescreve_taxas_da_api():
    m = normalizar_metrica({"titulo": "A", "alcance": 100, "salvamentos": 5,
                            "taxa_salvamentos": 5.5})
    assert m["taxa_salvamentos"] == 5.5


def test_normalizar_alcance_zero_zera_taxas():
    m = normalizar_metrica({"titulo": "A", "alcance": 0})
    assert m["taxa_salvamentos"] == 0.0
    assert m["taxa_envios"] == 0.0


# ─── save_metrica / importar_metricas (gate + dedup + lote único) ───────────

def _reset_metricas(monkeypatch_path, dados):
    persistence._write_json(monkeypatch_path, dados)


def test_save_metrica_rejeita_entrada_vazia(tmp_path, monkeypatch):
    arq = tmp_path / "metricas.json"
    monkeypatch.setattr(persistence, "METRICAS_FILE", str(arq))
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path))
    # O lixo real de 17/09 (reimportado 2x por causa do loop linha-a-linha)
    assert save_metrica({"data": "", "titulo": "", "alcance": 0}) is False
    assert load_metricas() == []


def test_save_metrica_rejeita_duplicada_e_aceita_distinta(tmp_path, monkeypatch):
    arq = tmp_path / "metricas.json"
    monkeypatch.setattr(persistence, "METRICAS_FILE", str(arq))
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path))
    assert save_metrica({"titulo": "Post A", "data": "2026-09-01", "alcance": 100})
    assert save_metrica({"titulo": "Post A", "data": "2026-09-01", "alcance": 100}) is False
    assert save_metrica({"titulo": "Post A", "data": "2026-09-02", "alcance": 100})
    assert len(load_metricas()) == 2


def test_importar_metricas_lote_unico_e_resumo(tmp_path, monkeypatch):
    arq = tmp_path / "metricas.json"
    monkeypatch.setattr(persistence, "METRICAS_FILE", str(arq))
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path))
    linhas = [
        {"data": "2026-09-01", "titulo": "A", "alcance": "1200",
         "salvamentos": "45", "envios": "28", "leads_whatsapp": "8"},
        {"data": "2026-09-02", "titulo": "B", "alcance": "1500",
         "salvamentos": "60", "envios": "35", "leads_whatsapp": "12"},
        # inválida: sem título (o caso real das 280)
        {"data": "2026-09-03", "titulo": "", "alcance": "999"},
        # inválida: alcance 0
        {"data": "2026-09-04", "titulo": "C", "alcance": "0"},
    ]
    resumo = importar_metricas(linhas)
    assert resumo == {"importadas": 2, "invalidas": 2, "duplicadas": 0}
    salvas = load_metricas()
    assert len(salvas) == 2
    assert salvas[0]["envios_dm"] == 28  # normalizado
    assert salvas[0]["taxa_salvamentos"] == 3.8  # 45/1200


def test_importar_metricas_reimport_nao_duplica(tmp_path, monkeypatch):
    arq = tmp_path / "metricas.json"
    monkeypatch.setattr(persistence, "METRICAS_FILE", str(arq))
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path))
    linhas = [{"data": "2026-09-01", "titulo": "A", "alcance": "1200",
               "salvamentos": "45", "envios": "28", "leads_whatsapp": "8"}]
    assert importar_metricas(linhas)["importadas"] == 1
    resumo2 = importar_metricas(linhas)  # 2º clique no mesmo CSV
    assert resumo2 == {"importadas": 0, "invalidas": 0, "duplicadas": 1}
    assert len(load_metricas()) == 1


def test_importar_metricas_dedup_dentro_do_lote(tmp_path, monkeypatch):
    arq = tmp_path / "metricas.json"
    monkeypatch.setattr(persistence, "METRICAS_FILE", str(arq))
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path))
    linhas = [
        {"data": "2026-09-01", "titulo": "A", "alcance": "100"},
        {"data": "2026-09-01", "titulo": "A", "alcance": "100"},  # igual no lote
        {"data": "2026-09-01", "titulo": "A", "alcance": "100", "comentarios": "9"},
    ]
    resumo = importar_metricas(linhas)
    assert resumo["importadas"] == 1
    assert resumo["duplicadas"] == 2


# ─── limpar_metricas_vazias ─────────────────────────────────────────────────

def test_limpar_metricas_vazias_remove_sozinhas_o_lixo(tmp_path, monkeypatch):
    arq = tmp_path / "metricas.json"
    monkeypatch.setattr(persistence, "METRICAS_FILE", str(arq))
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path))
    # Reproduz o data/metricas.json real: 280 vazias + 1 útil
    dados = [{"data": "", "titulo": "", "alcance": 0} for _ in range(280)]
    dados.append({"data": "2026-09-01", "titulo": "Post real", "alcance": 1200,
                  "salvamentos": 45, "envios_dm": 28, "leads_whatsapp": 8})
    persistence._write_json(str(arq), dados)
    removidas = limpar_metricas_vazias()
    assert removidas == 280
    restantes = load_metricas()
    assert len(restantes) == 1 and restantes[0]["titulo"] == "Post real"


def test_limpar_metricas_vazias_idempotente(tmp_path, monkeypatch):
    arq = tmp_path / "metricas.json"
    monkeypatch.setattr(persistence, "METRICAS_FILE", str(arq))
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path))
    persistence._write_json(str(arq), [{"titulo": "A", "alcance": 10}])
    assert limpar_metricas_vazias() == 0


# ─── feedback loop (prompts.py) ─────────────────────────────────────────────

def test_feedback_loop_ignora_metricas_sem_titulo(monkeypatch):
    """As 280 entradas reais (título vazio) não podem alimentar o aprendizado."""
    import persistence as pers
    import prompts as p

    lixo = [{"data": "", "titulo": "", "alcance": 0, "taxa_salvamentos": 0.0}] * 280
    monkeypatch.setattr(pers, "load_metricas", lambda: lixo)
    assert p.build_ideas_prompt_with_feedback() == p.PROMPT_IDEIAS_BASE


def test_feedback_loop_ativo_com_metricas_reais(monkeypatch):
    """Com métricas úteis, o bloco de aprendizado aparece no prompt."""
    import prompts as p

    boas = [
        {"titulo": "Dicas de Matemática", "alcance": 1200,
         "taxa_salvamentos": 4.5, "taxa_envios": 2.8, "leads_whatsapp": 8},
        {"titulo": "Rotina de Estudos", "alcance": 1500,
         "taxa_salvamentos": 3.9, "taxa_envios": 3.1, "leads_whatsapp": 12},
    ]
    monkeypatch.setattr(p, "PROMPT_IDEIAS_BASE", p.PROMPT_IDEIAS_BASE)
    import persistence as pers
    monkeypatch.setattr(pers, "load_metricas", lambda: boas)
    prompt = p.build_ideas_prompt_with_feedback()
    assert "FEEDBACK DE PERFORMANCE" in prompt
    assert "Dicas de Matemática" in prompt
    assert "Rotina de Estudos" in prompt


def test_feedback_loop_morto_sem_metricas(monkeypatch):
    import persistence as pers
    import prompts as p
    monkeypatch.setattr(pers, "load_metricas", lambda: [])
    assert p.build_ideas_prompt_with_feedback() == p.PROMPT_IDEIAS_BASE
