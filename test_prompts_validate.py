"""Testes do validador de prompts de imagem (validate_prompts)."""

from prompts import validate_prompts


def _slide(n: int, overlay: str, prompt_en: str | None = None) -> dict:
    if prompt_en is None:
        prompt_en = (
            f"Modern educational slide {n} with floating white cards. "
            f"Text overlay in Brazilian Portuguese: '{overlay}'"
        )
    return {
        "slide_num": n,
        "prompt_en": prompt_en,
        "prompt_pt": f"Descrição do slide {n}",
        "text_overlay": overlay,
    }


def _payload_valido() -> dict:
    overlays = [
        "A hora da lição de casa virou batalha na sua casa?",
        "Tentar ser pai e professor ao mesmo tempo desgasta",
        "Dica 1: dê 30 minutos de descanso antes das tarefas",
        "Dica 2: monte um cantinho de estudos sem distrações",
        "Dica 3: pergunte qual foi o desafio mais legal de hoje",
        "Deixe a mediação pedagógica com nossos especialistas",
        "De volta à harmonia familiar com o apoio da Ensina Mais",
        "Comente HARMONIA ou chame no WhatsApp (11) 94475-0009",
    ]
    return {
        "slides": [_slide(i + 1, ov) for i, ov in enumerate(overlays)],
        "paleta_cores": {"azul_brand": "#007799"},
        "base_prompt": (
            "Shared style: off-white #F7F9FF background, Brand Blue #007799 headers, "
            "Action Green #58B947 pill buttons, yellow #FFC20E highlights, floating "
            "white cards, rounded corners, soft shadows."
        ),
        "dicas_gerais": "Texto claro por lâmina.",
    }


def _ideia_origem(payload: dict) -> dict:
    """Ideia de origem cujos textos batem com os overlays do payload válido."""
    return {
        "titulo": "Harmonia familiar",
        "slides_sugeridos": [
            {"slide": i + 1, "tipo": "Capa" if i == 0 else "Entrega",
             "texto": f"{s['text_overlay']} — contexto adicional do roteiro aprovado"}
            for i, s in enumerate(payload["slides"])
        ],
    }


# ─── Payload válido ──────────────────────────────────────────────────────────

def test_payload_valido_sem_avisos():
    assert validate_prompts(_payload_valido()) == []


def test_payload_valido_com_ideia_sem_avisos():
    p = _payload_valido()
    assert validate_prompts(p, _ideia_origem(p)) == []


# ─── Estrutura ───────────────────────────────────────────────────────────────

def test_resposta_vazia():
    assert len(validate_prompts({})) == 1
    assert "Nenhum slide" in validate_prompts({})[0]


def test_resposta_nao_dict():
    avisos = validate_prompts(None)  # type: ignore[arg-type]
    assert len(avisos) == 1


def test_quantidade_errada_de_slides():
    p = _payload_valido()
    p["slides"] = p["slides"][:6]
    avisos = validate_prompts(p)
    assert any("6 slides" in a for a in avisos)


def test_paleta_ausente():
    p = _payload_valido()
    del p["paleta_cores"]
    assert any("Paleta" in a for a in validate_prompts(p))


def test_prompt_en_vazio():
    p = _payload_valido()
    p["slides"][2]["prompt_en"] = ""
    assert any("prompt_en vazio" in a for a in validate_prompts(p))


# ─── Regras de texto ─────────────────────────────────────────────────────────

def test_prompt_en_sem_clausula_brazilian_portuguese():
    p = _payload_valido()
    p["slides"][0]["prompt_en"] = "Modern slide with blue header, no language clause."
    avisos = validate_prompts(p)
    assert any("brazilian portuguese" in a.lower() for a in avisos)


def test_overlay_com_mais_de_15_palavras():
    p = _payload_valido()
    p["slides"][1]["text_overlay"] = " ".join(["palavra"] * 16)
    avisos = validate_prompts(p)
    assert any("16 palavras" in a for a in avisos)


def test_arraste_para_o_lado_dentro_do_overlay():
    p = _payload_valido()
    p["slides"][0]["text_overlay"] = "Arraste para o lado ➔ veja as dicas"
    avisos = validate_prompts(p)
    assert any("camada separada" in a for a in avisos)


def test_swipe_english_no_overlay():
    p = _payload_valido()
    p["slides"][0]["text_overlay"] = "Swipe to see the next tip"
    avisos = validate_prompts(p)
    assert any("Swipe" in a for a in avisos)


def test_overlay_vazio():
    p = _payload_valido()
    p["slides"][3]["text_overlay"] = ""
    assert any("text_overlay vazio" in a for a in validate_prompts(p))


# ─── Personagens da Turma da Mônica ─────────────────────────────────────────

def test_personagem_proibido_detectado():
    p = _payload_valido()
    p["slides"][0]["prompt_en"] += " featuring Cebolinha cartoon character."
    avisos = validate_prompts(p)
    assert any("cebolinha" in a for a in avisos)


def test_marca_do_logo_permitida():
    """A marca 'Ensina Mais Turma da Mônica' no logo NÃO pode gerar aviso."""
    p = _payload_valido()
    p["slides"][0]["prompt_en"] += " Official logo 'Ensina Mais Turma da Mônica' in corner."
    assert validate_prompts(p) == []


# ─── CTA / WhatsApp ─────────────────────────────────────────────────────────

def test_ultimo_slide_sem_whatsapp():
    p = _payload_valido()
    p["slides"][-1]["text_overlay"] = "Comente HARMONIA para receber o material"
    p["slides"][-1]["prompt_en"] = (
        "Final CTA slide with green pill button. "
        "Text overlay in Brazilian Portuguese: 'Comente HARMONIA para receber o material'"
    )
    avisos = validate_prompts(p)
    assert any("94475" in a for a in avisos)


# ─── Fidelidade ao roteiro ──────────────────────────────────────────────────

def test_overlay_inventado_detectado():
    p = _payload_valido()
    ideia = _ideia_origem(p)
    # Overlay do slide 2 totalmente alinhado ao roteiro (fidelidade ok)…
    assert not any("não deriva" in a for a in validate_prompts(p, ideia))
    # …agora troca por um texto inventado sem palavras do original:
    ideia["slides_sugeridos"][1]["texto"] = (
        "Segunda capa: por que a leitura apressada induz ao raciocínio errado na prova"
    )
    p["slides"][1]["text_overlay"] = "Robôs alienígenas invadem a biblioteca municipal hoje"
    avisos = validate_prompts(p, ideia)
    assert any("não deriva" in a for a in avisos)


def test_sem_ideia_nao_checa_fidelidade():
    p = _payload_valido()
    p["slides"][1]["text_overlay"] = "Robôs alienígenas invadem a biblioteca municipal hoje"
    assert validate_prompts(p) == []


# ─── Base prompt / consistência entre lâminas (Bloco 6) ─────────────────────

def test_base_prompt_ausente():
    p = _payload_valido()
    del p["base_prompt"]
    assert any("base_prompt" in a for a in validate_prompts(p))


def test_base_prompt_sem_hexes_da_marca():
    p = _payload_valido()
    p["base_prompt"] = "Shared modern style with blue and green."
    assert any("hexes" in a for a in validate_prompts(p))


# ─── Paleta em formato hex (swatch do app) ──────────────────────────────────

def test_paleta_com_valor_fora_de_hex():
    p = _payload_valido()
    p["paleta_cores"]["azul_brand"] = "azul escuro"
    assert any("hex" in a.lower() for a in validate_prompts(p))


def test_cor_eh_valida():
    from prompts import cor_eh_valida
    assert cor_eh_valida("#007799")
    assert cor_eh_valida("#FFF")
    assert not cor_eh_valida("url(javascript:alert(1))")
    assert not cor_eh_valida("#GGHHII")
    assert not cor_eh_valida(None)
    assert not cor_eh_valida(123)


# ─── Identidade visual em fonte única (Bloco 4) ─────────────────────────────

def test_identidade_injetada_do_arquivo():
    """O prompt de imagem carrega o .txt inteiro — não uma cópia própria."""
    from prompts import PADRAO_VISUAL, PROMPT_PROMPTS_IMAGEM
    assert "padroesVisuais.txt" in PROMPT_PROMPTS_IMAGEM
    assert PADRAO_VISUAL in PROMPT_PROMPTS_IMAGEM


def test_sem_ingles_fora_do_portfolio():
    """'Inglês' não está no portfólio de4 cursos — não pode aparecer na paleta."""
    from pathlib import Path

    from prompts import PROMPT_PROMPTS_IMAGEM, SYSTEM_INSTRUCTION_PERSONA
    txt = (Path(__file__).parent / "padroesVisuais.txt").read_text(encoding="utf-8")
    for nome, fonte in (
        ("persona", SYSTEM_INSTRUCTION_PERSONA),
        ("prompt de imagem", PROMPT_PROMPTS_IMAGEM),
        ("padroesVisuais.txt", txt),
    ):
        assert "Inglês" not in fonte, f"'Inglês' ainda presente em {nome}"
    assert "pastel_ingles" not in PROMPT_PROMPTS_IMAGEM


def test_regra_dupla_monica_em_todos_os_prompts():
    from prompts import (
        PROMPT_PROMPTS_IMAGEM,
        PROMPT_VIDEO_CURTO,
        SYSTEM_INSTRUCTION_PERSONA,
    )
    assert "REGRA DUPLA" in SYSTEM_INSTRUCTION_PERSONA
    assert "REGRA DUPLA" in PROMPT_PROMPTS_IMAGEM
    assert "no cartoon characters" in PROMPT_PROMPTS_IMAGEM
    assert "regra dupla" in PROMPT_VIDEO_CURTO


def test_regras_9_e_10_de_consistencia():
    from prompts import PROMPT_PROMPTS_IMAGEM
    assert "9. BASE_PROMPT PARA CONSISTÊNCIA" in PROMPT_PROMPTS_IMAGEM
    assert "10. GERAÇÃO EM SÉRIE" in PROMPT_PROMPTS_IMAGEM
