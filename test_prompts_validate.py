"""Testes do validador de prompts de imagem (validate_prompts)."""

from config import TAG_NAVEGACAO
from prompts import FRASE_FACHADA, validate_prompts

_TIPOS_THUMB = {1: "recepcao_unidade", 4: "alunos_robotica", 5: "aluno_programacao"}


def _tag_frase(n: int) -> str:
    if n == 8:
        return ""
    return (
        "In the bottom right corner, a small discreet text in Brazilian "
        f"Portuguese says '{TAG_NAVEGACAO}'."
    )


def _slide(n: int, overlay: str, prompt_en: str | None = None) -> dict:
    if prompt_en is None:
        corpo = (
            f"Authentic school photo of students at Ensina Mais Tatuapé, slide {n}"
            if n in _TIPOS_THUMB
            else f"Modern educational slide {n} with cards and line icons"
        )
        fachada = f"{FRASE_FACHADA} " if n == 7 else ""
        prompt_en = (
            f"{corpo}. {fachada}text overlay in Brazilian Portuguese: '{overlay}'. "
            f"No cartoon characters. {_tag_frase(n)}"
        ).strip()
    if n in _TIPOS_THUMB:
        refs = [_TIPOS_THUMB[n]]
    elif n == 7:
        refs = ["fachada"]
    else:
        refs = ["logo"]
    return {
        "slide_num": n,
        "prompt_en": prompt_en,
        "prompt_pt": f"Descrição do slide {n}",
        "text_overlay": overlay,
        "estilo": "Capa" if n == 1 else "Conteúdo",
        "usa_foto_real": n in _TIPOS_THUMB,
        "tipo_foto": _TIPOS_THUMB.get(n, "logo"),
        "referencias": refs,
        "tag_navegacao": "" if n == 8 else TAG_NAVEGACAO,
    }


def _payload_valido() -> dict:
    overlays = [
        "A hora da lição de casa virou batalha?",
        "Tentar ser pai e professor ao mesmo tempo desgasta",
        "Dica 1: dê 30 minutos de descanso antes das tarefas",
        "Monte um cantinho de estudos sem distrações",
        "Qual foi o desafio mais legal de hoje?",
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


def test_clausula_de_overlay_repetida():
    p = _payload_valido()
    p["slides"][0]["prompt_en"] += (
        " Extra text overlay in Brazilian Portuguese: 'Outra frase aqui.'"
    )
    avisos = validate_prompts(p)
    assert any("repete a instrução de texto sobreposto" in a for a in avisos)


def test_clausula_de_overlay_variante_e_aceita():
    """Paráfrase do Gemini ("highlight in Brazilian Portuguese") vale como regra 5."""
    p = _payload_valido()
    p["slides"][0]["prompt_en"] = p["slides"][0]["prompt_en"].replace(
        "text overlay in Brazilian Portuguese", "highlight in Brazilian Portuguese"
    )
    avisos = validate_prompts(p)
    assert not any("regra 5" in a for a in avisos)


def test_overlay_com_mais_de_15_palavras():
    p = _payload_valido()
    p["slides"][1]["text_overlay"] = " ".join(["palavra"] * 16)
    avisos = validate_prompts(p)
    assert any("16 palavras" in a for a in avisos)


def test_arraste_para_o_lado_dentro_do_overlay():
    p = _payload_valido()
    p["slides"][0]["text_overlay"] = "Arraste para o lado ➔ veja as dicas"
    avisos = validate_prompts(p)
    assert any("tag_navegacao" in a or "regra 6" in a for a in avisos)


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


def test_personagem_detectado_em_estilo():
    p = _payload_valido()
    p["slides"][0]["estilo"] = "Estilo cartoon de Mônica para capa"
    avisos = validate_prompts(p)
    assert any('"estilo"' in a and "mônica" in a for a in avisos)


def test_personagem_detectado_em_base_prompt_e_dicas():
    p = _payload_valido()
    p["base_prompt"] += " With Chico Bento illustration style."
    p["dicas_gerais"] += " Evite citar Cebolinha."
    avisos = validate_prompts(p)
    assert any(a.startswith("⚠️ base_prompt") and "chico bento" in a for a in avisos)
    assert any(a.startswith("⚠️ dicas_gerais") and "cebolinha" in a for a in avisos)


# ─── Regra 12 — fachada intocável ───────────────────────────────────────────

def test_fachada_intocavel_sem_clausula_avisada():
    p = _payload_valido()
    p["slides"][6]["prompt_en"] = p["slides"][6]["prompt_en"].replace(
        FRASE_FACHADA, ""
    ).replace("  ", " ").strip()
    avisos = validate_prompts(p)
    assert any("fachada intocável" in a for a in avisos)


def test_fachada_intocavel_com_clausula_ok():
    p = _payload_valido()
    assert FRASE_FACHADA in p["slides"][6]["prompt_en"]
    assert validate_prompts(p) == []


def test_slide7_sem_referencia_fachada_avisado():
    p = _payload_valido()
    p["slides"][6]["referencias"] = ["equipe"]
    avisos = validate_prompts(p)
    assert any('deve incluir "fachada"' in a for a in avisos)


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


def test_regras_9_e_10_e_11_de_consistencia():
    from prompts import PROMPT_PROMPTS_IMAGEM
    assert "9. BASE_PROMPT PARA CONSISTÊNCIA" in PROMPT_PROMPTS_IMAGEM
    assert "10. \"dicas_gerais\" — ESPECÍFICO DESTE CARROSSEL" in PROMPT_PROMPTS_IMAGEM
    assert "11. REFERÊNCIA DE IMAGEM POR SLIDE" in PROMPT_PROMPTS_IMAGEM


# ─── Regra 6 — tag de navegação no prompt_en ────────────────────────────────

def test_tag_ausente_no_prompt_en_avisado():
    p = _payload_valido()
    p["slides"][0]["prompt_en"] = p["slides"][0]["prompt_en"].replace(TAG_NAVEGACAO, "…")
    avisos = validate_prompts(p)
    assert any("regra 6" in a for a in avisos)


def test_tag_no_prompt_do_slide_8_avisado():
    p = _payload_valido()
    p["slides"][7]["prompt_en"] += f" discreet tag {TAG_NAVEGACAO} bottom right."
    p["slides"][7]["tag_navegacao"] = TAG_NAVEGACAO
    avisos = validate_prompts(p)
    assert any("slide 8" in a.lower() for a in avisos)


def test_tag_campo_json_incoerente():
    p = _payload_valido()
    p["slides"][2]["tag_navegacao"] = ""
    avisos = validate_prompts(p)
    assert any("tag_navegacao" in a for a in avisos)


# ─── Regra 7 — cláusula anti-personagem ─────────────────────────────────────

def test_clausula_no_cartoon_characters_obrigatoria():
    p = _payload_valido()
    p["slides"][1]["prompt_en"] = p["slides"][1]["prompt_en"].replace(
        "No cartoon characters.", ""
    )
    avisos = validate_prompts(p)
    assert any("no cartoon characters" in a for a in avisos)


# ─── Regra 11 — referências de imagem por slide ─────────────────────────────

def test_referencia_fora_do_catalogo():
    p = _payload_valido()
    p["slides"][0]["referencias"] = ["foto_anexada", "banco_de_imagens"]
    avisos = validate_prompts(p)
    assert any("fora do catálogo" in a for a in avisos)


def test_referencia_vazia():
    p = _payload_valido()
    p["slides"][3]["referencias"] = []
    avisos = validate_prompts(p)
    assert any("referencias" in a for a in avisos)


def test_slide_thumbnail_sem_cena_fotografica():
    p = _payload_valido()
    p["slides"][4]["referencias"] = ["logo"]
    avisos = validate_prompts(p)
    assert any("foto real da unidade" in a for a in avisos)


def test_prompt_pt_vazio():
    p = _payload_valido()
    p["slides"][2]["prompt_pt"] = ""
    assert any("prompt_pt vazio" in a for a in validate_prompts(p))


# ─── Export .txt da série (extensão de automação) ────────────────────────────

def test_formatar_txt_prompts_so_os_8_prompts():
    from prompts import formatar_txt_prompts

    payload = _payload_valido()
    txt = formatar_txt_prompts(payload)
    # só os prompt_en, um bloco por lâmina, separados por linha em branco
    blocos = [b.strip() for b in txt.split("\n\n") if b.strip()]
    assert blocos == [s["prompt_en"] for s in payload["slides"]]
    for proibido in (
        "CARROSSEL",
        "## ",
        "BASE PROMPT",
        "COMO GERAR",
        "Referências:",
        "Text overlay (PT-BR):",
        payload["base_prompt"][:40],
        payload["dicas_gerais"],
    ):
        assert proibido not in txt


def test_formatar_txt_prompts_payload_invalido():
    from prompts import formatar_txt_prompts
    assert formatar_txt_prompts({}) == ""
    assert formatar_txt_prompts(None) == ""  # type: ignore[arg-type]
