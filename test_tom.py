"""Testes do V5 — tons de voz (ghostwriter).

O tom é a única personalização que entra no prompt sem passar pelo Gemini, então
o risco aqui é duplo: quebrar o prompt base (regressão silenciosa) ou deixar o
tom passar por cima das regras do motor.
"""

import pytest

import config
import prompts
from prompts import (
    TONES,
    bloco_tom,
    get_prompt_ideias,
    get_prompt_legendas,
    resolver_tom,
    tom_eh_valido,
)

TODOS_OS_TONS = {"natural", "didatico", "storyteller", "especialista", "viral"}


def test_config_e_prompts_conhecem_os_mesmos_tons():
    assert set(TONES) - {"automatico"} == TODOS_OS_TONS
    assert set(TONES) <= set(config.TONES)
    assert config.TONES_PADRAO == "automatico"


def test_tom_padrao_da_config_esta_no_prompts():
    # prompts.py importa de config, então se alguém renomear a constante aqui
    # o ImportError aparece na importação. Este teste documenta a intenção.
    assert config.TONES_PADRAO == "automatico"
    assert tom_eh_valido(config.TONES_PADRAO)


@pytest.mark.parametrize("eixo,tom_esperado", [
    ("Didático", "didatico"),
    ("Comportamental", "storyteller"),
    ("Diagnóstico", "especialista"),
])
def test_automatico_segue_o_eixo(eixo, tom_esperado):
    assert resolver_tom("automatico", eixo) == tom_esperado


def test_automatico_sem_eixo_cai_em_natural():
    # Geração de ideias acontece antes de qualquer triagem: sem eixo, o registro
    # de menor risco é conversa, não campanha.
    assert resolver_tom("automatico") == "natural"
    assert resolver_tom("automatico", "Eixo Inventado") == "natural"
    assert resolver_tom(None) == "natural"
    # omitting o tom equivale a "automatico", então o eixo ainda manda
    assert resolver_tom(None, "Didático") == "didatico"


def test_tom_desconhecido_nao_quebra_a_geracao():
    # Payload vindo do NotebookLM ou JSON antigo pode não ter o campo, ou ter
    # um valor de uma versão anterior. Gerar com "natural" é melhor que erro.
    assert resolver_tom("sirene") == "natural"
    assert resolver_tom("") == "natural"
    assert resolver_tom("sirene", "Diagnóstico") == "natural"


def test_tom_explicito_e_respeitado():
    for tom in TODOS_OS_TONS:
        assert resolver_tom(tom, "Didático") == tom


def test_resolver_tom_normaliza_caixa_e_espaco():
    assert resolver_tom("  Viral  ") == "viral"
    assert resolver_tom("DIDATICO") == "didatico"


def test_tom_eh_valido():
    assert tom_eh_valido("viral")
    assert tom_eh_valido("automatico")
    assert not tom_eh_valido("sirene")


def test_bloco_tom_traz_a_instrucao_do_tom():
    bloco = bloco_tom("viral")
    assert TONES["viral"]["rotulo"] in bloco
    assert TONES["viral"]["instrucao"][:40] in bloco


def test_bloco_automatico_nao_fixa_um_registro():
    # "Automático" precisa mandar variar entre as ideias — foi exatamente por
    # isso que o tom virou parâmetro. Se um dia o bloco voltar a fixar um
    # registro, este teste avisa.
    bloco = bloco_tom("automatico")
    assert "Varie o registro" in bloco
    for tom in TODOS_OS_TONS:
        assert tom not in bloco.lower().replace("registro didático", "").replace(
            "registro de cena", ""
        ).replace("registro de especialista", "")


def test_bloco_tom_de_peca_unica_resolve_automatico_pelo_eixo():
    bloco = bloco_tom("automatico", "Diagnóstico", variacao=False)
    assert TONES["especialista"]["rotulo"] in bloco
    assert "Varie o registro" not in bloco


def test_bloco_tom_desconhecido_nao_vaza_texto_de_prompt():
    bloco = bloco_tom("sirene", "Didático")
    assert bloco == bloco_tom("natural", "Didático")


def test_bloco_tom_nao_afrouxa_as_regras_do_motor():
    for tom in list(TODOS_OS_TONS) + ["automatico"]:
        bloco = bloco_tom(tom)
        assert "Mônica" in bloco, f"o tom {tom} precisa repetir a regra da marca"


def test_prompt_de_ideias_preserva_a_base_e_acrescenta_o_tom():
    base = get_prompt_ideias()
    com_tom = get_prompt_ideias("viral")
    assert prompts.PROMPT_IDEIAS_BASE in base
    assert prompts.PROMPT_IDEIAS_BASE in com_tom
    assert com_tom != base
    assert com_tom.endswith(bloco_tom("viral"))


def test_prompt_de_ideias_default_continua_valendo():
    # app.py e tab_notebooklm chamam sem argumento; nada pode quebrar ali.
    assert get_prompt_ideias() == get_prompt_ideias(config.TONES_PADRAO)


def test_feedback_de_metricas_sobrevive_ao_tom(monkeypatch):
    # O feedback loop monta o prompt em dois retornos antecipados (sem métricas
    # e sem posts válidos). O tom tem que entrar nos dois, senão o tom some
    # silenciosamente justamente no dia que não há histórico — que é o dia que
    # mais importa.
    import persistence

    monkeypatch.setattr(persistence, "load_metricas", lambda: [])
    monkeypatch.setenv("STORAGE_BACKEND", "json")
    assert get_prompt_ideias("didatico").endswith(bloco_tom("didatico"))

    monkeypatch.setattr(
        persistence,
        "load_metricas",
        lambda: [{"data": "2026-10-14", "titulo": "", "alcance": 0}],
    )
    assert get_prompt_ideias("didatico").endswith(bloco_tom("didatico"))


def test_prompt_de_legendas_mantem_a_base_e_acrescenta_o_tom():
    base = get_prompt_legendas()
    assert base.startswith(prompts.PROMPT_LEGENDAS)
    assert get_prompt_legendas("natural", "Comportamental").startswith(
        prompts.PROMPT_LEGENDAS
    )
    # Numa peça única não existe mistura: "automatico" resolve pelo eixo.
    assert TONES["storyteller"]["rotulo"] in get_prompt_legendas(
        "automatico", "Comportamental"
    )


def test_prompt_de_legendas_resolve_automático_pelo_eixo():
    # Numa peça única, automático e explícito são o mesmo prompt: o eixo já
    # decide. A diferença só existe no lote de ideias.
    automatico = get_prompt_legendas("automatico", "Diagnóstico")
    explicit = get_prompt_legendas("especialista", "Diagnóstico")
    assert automatico == explicit
    assert TONES["especialista"]["rotulo"] in explicit
    assert automatico != get_prompt_legendas("automatico", "Didático")


def test_gerar_legendas_repassa_o_tom_ao_prompt(monkeypatch):
    """batch_engine tem de enviar o prompt com tom, não o PROMPT_LEGENDAS cru."""
    import batch_engine

    capturado = {}

    def fake_call(prompt, ctx, temperature=None, images=None):
        capturado["prompt"] = prompt
        capturado["temperature"] = temperature
        return {"legendas": []}

    monkeypatch.setattr(batch_engine, "call_gemini_json", fake_call)
    monkeypatch.setattr(batch_engine, "invalidate_cache", lambda *a, **k: None)

    ideia = {"titulo": "Prova de matemática", "eixo": "Comportamental", "tema": "raiva"}
    batch_engine.gerar_legendas_ideia(ideia, tom="storyteller")

    assert capturado["prompt"].startswith(prompts.PROMPT_LEGENDAS)
    assert capturado["prompt"].endswith(bloco_tom("storyteller", "Comportamental"))
    assert capturado["temperature"] == prompts.TEMPERATURAS["legendas"]
