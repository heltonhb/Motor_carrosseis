"""Testes do V7 — acervo (nível 7: o motor aprende com o que foi aprovado).

O acervo é o único ponto do motor que aprende sozinho, e é também o único que
pode envenenar todas as gerações futuras. Os testes abaixo tratam as duas
faces: entra só o que é mérito, e entra DNA, não cópia.
"""

import json
import os

import pytest

import acervo
import batch_engine
import config
import persistence
from persistence import load_acervo, remover_acervo, save_acervo

IDEIA = {
    "id": "ideia_teste",
    "titulo": "Por que a leitura apressada perde pontos",
    "eixo": "Didático",
    "tipo_hook": "dado_chocante",
}

PROMPTS = {
    "slides": [
        {"slide": 1, "tipo": "Capa", "usa_foto_real": True, "referencias": ["fachada"],
         "prompt_en": "Brand Blue #007799 typography, Poppins, photo full-bleed"},
        {"slide": 3, "tipo": "Entrega", "usa_foto_real": False, "referencias": [],
         "prompt_en": "white card #F7F9FF with Action Green #58B947 pill"},
        {"slide": 8, "tipo": "CTA", "usa_foto_real": False, "referencias": ["logo"],
         "prompt_en": "green button #58B947, WhatsApp"},
    ]
}

ESTADO_PUBLICADO = {"ideia_teste": {"id": "ideia_teste", "status": "publicado"}}
METRICA_BOA = [{
    "data": "2026-10-14", "titulo": IDEIA["titulo"], "alcance": 5000,
    "taxa_salvamentos": 6.2, "taxa_envios": 3.0, "leads_whatsapp": 18,
}]
METRICA_RUIM = [{**METRICA_BOA[0], "taxa_salvamentos": 1.1}]


@pytest.fixture(autouse=True)
def acervo_isolado(monkeypatch, tmp_path):  # noqa: ARG001
    """Isola o acervo em diretório temporário — teste nenhum toca data/acervo."""
    dir_acervo = tmp_path / "acervo"
    # acervo.py não guarda caminho próprio: ele lê de persistence, que é quem
    # sabe do backend. Patching lá cobre as duas camadas.
    monkeypatch.setattr(persistence, "ACERVO_DIR", str(dir_acervo))
    monkeypatch.setattr(persistence, "DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    return str(dir_acervo)


# ─── Persistência ────────────────────────────────────────────────────────────

def test_acervo_comeca_vazio():
    assert load_acervo() == []


def test_salva_e_lê_um_registro():
    assert save_acervo({"slug": "post-a", "titulo": "A", "aprovado_em": "2026-10-01"})
    assert save_acervo({"slug": "post-b", "titulo": "B", "aprovado_em": "2026-10-14"})
    registros = load_acervo()
    assert {r["slug"] for r in registros} == {"post-a", "post-b"}
    # mais recente primeiro: é assim que o bloco_dna escolhe o que entra
    assert registros[0]["slug"] == "post-b"


def test_primeira_promocao_cria_o_diretorio():
    # data/acervo/ nasce vazio; sem criar a pasta a escrita falha em silêncio.
    destino = persistence.ACERVO_DIR
    assert not os.path.isdir(destino)
    assert save_acervo({"slug": "post-a", "aprovado_em": "2026-10-01"}) is True
    assert os.path.isdir(destino)


def test_registro_sem_slug_nao_e_salvo():
    assert save_acervo({"titulo": "sem slug"}) is False
    assert load_acervo() == []


def test_salvar_mesmo_slug_sobrescreve():
    save_acervo({"slug": "post-a", "titulo": "A", "aprovado_em": "2026-10-01"})
    save_acervo({"slug": "post-a", "titulo": "A revisado", "aprovado_em": "2026-10-02"})
    registros = load_acervo()
    assert len(registros) == 1
    assert registros[0]["titulo"] == "A revisado"


def test_arquivo_corrompido_nao_derruba_o_acervo():
    save_acervo({"slug": "bom", "titulo": "Bom", "aprovado_em": "2026-10-14"})
    caminho = os.path.join(persistence.ACERVO_DIR, "ruim.json")
    with open(caminho, "w", encoding="utf-8") as f:
        f.write("{isso nao é json")
    assert [r["slug"] for r in load_acervo()] == ["bom"]


def test_remover_acervo():
    save_acervo({"slug": "post-a", "aprovado_em": "2026-10-14"})
    assert remover_acervo("post-a") is True
    assert remover_acervo("post-a") is False
    assert load_acervo() == []


# ─── Alvo do eixo ────────────────────────────────────────────────────────────

def test_alvo_do_eixo_vem_da_config():
    # Se o alvo do prompt e o alvo do acervo divergirem, o motor aprende contra
    # a própria régua. Aqui ambos leem a mesma string de config.EIXOS.
    assert acervo.alvo_do_eixo("Didático") == 4.0
    assert acervo.alvo_do_eixo("Comportamental") == 2.5
    # Diagnóstico tem KPI de leads, não porcentagem: vale o alvo global de
    # salvamento — que é o portão único do acervo.
    assert acervo.alvo_do_eixo("Diagnóstico") == config.KPIS["salvamentos_pct"]
    assert acervo.alvo_do_eixo("Eixo Inventado") == config.KPIS["salvamentos_pct"]


# ─── Avaliação de promoção ───────────────────────────────────────────────────

def test_ideia_rascunho_nao_entra():
    pode, motivo = acervo.avaliar_promocao(
        IDEIA, metricas=METRICA_BOA, estados={"ideia_teste": {"status": "rascunho"}}
    )
    assert not pode
    assert "publicado" in motivo


def test_sem_metrica_nao_entra():
    pode, motivo = acervo.avaliar_promocao(IDEIA, metricas=[], estados=ESTADO_PUBLICADO)
    assert not pode
    assert "métrica" in motivo.lower()


def test_metrica_abaixo_do_alvo_nao_entra():
    pode, motivo = acervo.avaliar_promocao(
        IDEIA, metricas=METRICA_RUIM, estados=ESTADO_PUBLICADO
    )
    assert not pode
    assert "abaixo do alvo" in motivo


def test_publicada_e_no_alvo_entra():
    pode, motivo = acervo.avaliar_promocao(
        IDEIA, metricas=METRICA_BOA, estados=ESTADO_PUBLICADO
    )
    assert pode
    assert "6.2%" in motivo


def test_metrica_de_outro_post_nao_serve():
    outra = [{**METRICA_BOA[0], "titulo": "Outro post"}]
    pode, _ = acervo.avaliar_promocao(IDEIA, metricas=outra, estados=ESTADO_PUBLICADO)
    assert not pode


# ─── DNA ─────────────────────────────────────────────────────────────────────

def test_dna_extrai_estrutura_recursos_e_paleta():
    dna = acervo.extrair_dna(IDEIA, PROMPTS)
    assert dna["estrutura"] == ["Capa", "Entrega", "CTA"]
    assert "foto_real_slide_1" in dna["recursos"]
    assert "referencia:fachada" in dna["recursos"]
    assert "#007799" in dna["paleta"]
    assert "#58B947" in dna["paleta"]
    assert dna["tipografia"] == ["geometric sans"]
    assert dna["hook"] == "dado_chocante"


def test_dna_ignora_hex_fora_da_marca():
    # Um roxu no prompt é bug de paleta, não padrão a aprender.
    payload = {"slides": [{"slide": 1, "tipo": "Capa", "prompt_en": "background #A855F7"}]}
    assert acervo.extrair_dna(IDEIA, payload)["paleta"] == []


def test_dna_nao_guarda_texto_de_slide():
    # Guardar o conteúdo envelhece o acervo e vira ruído nas gerações futuras.
    payload = {"slides": [{"slide": 1, "tipo": "Capa", "texto": "SÓ PARA COPIAR NAO"}]}
    dna = acervo.extrair_dna(IDEIA, payload)
    assert "SÓ PARA COPIAR NAO" not in json.dumps(dna, ensure_ascii=False)


def test_dna_sem_prompts_nao_quebra():
    dna = acervo.extrair_dna(IDEIA, None)
    assert dna["estrutura"] == []
    assert dna["paleta"] == []


# ─── Promoção ────────────────────────────────────────────────────────────────

def test_promocao_grava_registro_com_metricas():
    registro, motivo = acervo.promover_para_acervo(
        IDEIA, prompts=PROMPTS, metricas=METRICA_BOA, estados=ESTADO_PUBLICADO
    )
    assert registro is not None
    assert registro["slug"].startswith("por-que-a-leitura-apressada")
    assert registro["metricas"]["taxa_salvamentos"] == 6.2
    assert registro["dna"]["estrutura"] == ["Capa", "Entrega", "CTA"]
    assert [r["slug"] for r in load_acervo()] == [registro["slug"]]
    assert "6.2%" in motivo


def test_promocao_recusada_nao_escreve_nada():
    registro, motivo = acervo.promover_para_acervo(
        IDEIA, prompts=PROMPTS, metricas=METRICA_RUIM, estados=ESTADO_PUBLICADO
    )
    assert registro is None
    assert load_acervo() == []
    assert "abaixo do alvo" in motivo


def test_forcar_promove_mesmo_sem_merito():
    registro, motivo = acervo.promover_para_acervo(
        IDEIA, prompts=PROMPTS, metricas=[], estados={}, forcar=True
    )
    assert registro is not None
    assert "manualmente" in motivo
    assert registro["metricas"]["alcance"] == 0


# ─── Bloco de prompt ─────────────────────────────────────────────────────────

def test_bloco_dna_vazio_sem_acervo():
    assert acervo.bloco_dna() == ""


def test_bloco_dna_lista_o_que_ja_funcionou():
    acervo.promover_para_acervo(
        IDEIA, prompts=PROMPTS, metricas=METRICA_BOA, estados=ESTADO_PUBLICADO
    )
    bloco = acervo.bloco_dna()
    assert "O QUE JÁ FUNCIONOU" in bloco
    assert IDEIA["titulo"] in bloco
    assert "Capa/Entrega/CTA" in bloco


def test_bloco_dna_respeita_o_limite():
    for n in range(6):
        save_acervo(
            {
                "slug": f"post-{n}",
                "titulo": f"Post {n}",
                "eixo": "Didático",
                "aprovado_em": f"2026-10-{10 + n:02d}",
                "dna": {"estrutura": ["Capa"], "recursos": [], "paleta": [], "hook": ""},
            }
        )
    bloco = acervo.bloco_dna(limite=3)
    assert bloco.count("Post ") == 3
    assert "Post 0" not in bloco  # o mais antigo fica de fora


def test_bloco_dna_entra_no_prompt_de_imagem(monkeypatch):
    acervo.promover_para_acervo(
        IDEIA, prompts=PROMPTS, metricas=METRICA_BOA, estados=ESTADO_PUBLICADO
    )
    capturado = {}
    monkeypatch.setattr(batch_engine, "FLOW_FOTOS", False)
    monkeypatch.setattr(
        batch_engine,
        "call_gemini_json",
        lambda prompt, *a, **k: capturado.setdefault("prompt", prompt) and None,
    )
    monkeypatch.setattr(batch_engine, "invalidate_cache", lambda *a, **k: None)
    batch_engine.gerar_prompts_ideia(IDEIA, fidelidade="media")
    assert "O QUE JÁ FUNCIONOU" in capturado["prompt"]


def test_resumo_acervo_conta():
    acervo.promover_para_acervo(
        IDEIA, prompts=PROMPTS, metricas=METRICA_BOA, estados=ESTADO_PUBLICADO
    )
    resumo = acervo.resumo_acervo()
    assert resumo["total"] == 1
    assert resumo["com_metrica"] == 1
    assert resumo["taxa_media"] == 6.2
