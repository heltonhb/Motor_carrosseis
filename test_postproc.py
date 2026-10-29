"""Pós-processamento _enforce_foto_real (batch_engine)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from batch_engine import (
    _CLAUSULAS_DO_MOTOR,
    _FRASE_TAG,
    _dedup_frases,
    _enforce_foto_real,
    _garantir_regras,
    _limite_overlay,
)
from config import TAG_NAVEGACAO
from prompts import FRASE_FACHADA, FRASE_FOTO_REAL
from refs_catalog import CENAS_FOTO, cena_valida


def _dados() -> dict:
    return {
        "slides": [
            {
                "slide_num": "1",
                "prompt_en": (
                    "Professional Instagram carousel slide 1, 1080x1350, vertical. "
                    "Minimalist design, off-white background #F7F9FF."
                ),
                "text_overlay": "A diferença entre usar tecnologia e saber programá-la",
            },
            {
                "slide_num": 4,
                "prompt_en": "Instagram carousel slide 4, 1080x1350. Floating white card...",
                "text_overlay": "Conexões neurais",
                "referencias": ["foto_anexada", "fachada"],
            },
            {
                "slide_num": 8,
                "prompt_en": "Final CTA slide with green pill button.",
                "text_overlay": "Comente AULA ou chame no WhatsApp (11) 94475-0009",
            },
        ]
    }


def test_reescreve_slides_thumbnail_com_foto_real():
    res = _enforce_foto_real(_dados())
    for slide in res["slides"]:
        if slide["slide_num"] in {1, 4, "1", "4"}:
            assert FRASE_FOTO_REAL.lower() in slide["prompt_en"].lower()
            assert slide["usa_foto_real"] is True
            assert slide["tipo_foto"] in CENAS_FOTO
            # regra 6: tag no prompt_en, regra 7: cláusula anti-personagem
            assert _FRASE_TAG in slide["prompt_en"]
            assert "no cartoon characters" in slide["prompt_en"].lower()
            # padrões genéricos removidos
            assert "off-white background" not in slide["prompt_en"].lower()
            assert "floating white card" not in slide["prompt_en"].lower()


def test_preserva_overlay_e_slide_nao_thumbnail():
    res = _enforce_foto_real(_dados())
    s1 = res["slides"][0]
    assert "A diferença entre usar tecnologia e saber programá-la" in s1["prompt_en"]
    s8 = res["slides"][2]
    # texto original preservado, com as cláusulas das regras 5 e 7 acrescentadas
    assert s8["prompt_en"].startswith("Final CTA slide with green pill button.")
    assert "text overlay in Brazilian Portuguese" in s8["prompt_en"]
    assert "no cartoon characters" in s8["prompt_en"].lower()
    # regra 6: slide 8 sem tag, campo em string vazia
    assert _FRASE_TAG not in s8["prompt_en"]
    assert s8["tag_navegacao"] == ""


def test_referencias_limpas_e_validas():
    res = _enforce_foto_real(_dados())
    refs = res["slides"][1]["referencias"]
    assert all(cena_valida(r) for r in refs)
    assert "foto_anexada" not in refs
    assert any(r in CENAS_FOTO for r in refs)


def test_snum_string_ainda_processado():
    """slide_num pode chegar como string do JSON — não pode ser pulado."""
    res = _enforce_foto_real(_dados())
    assert res["slides"][0]["tipo_foto"] in CENAS_FOTO


def test_corrigidos_registra_acoes():
    dados = _dados()
    corrigidos: list = []
    _enforce_foto_real(dados, corrigidos=corrigidos)
    assert any("slide 4" in c for c in corrigidos)


def test_payload_invalido_passa_adiano():
    assert _enforce_foto_real(None) is None  # type: ignore[arg-type]
    assert _enforce_foto_real({"slides": []}) == {"slides": []}


def test_tag_constante():
    assert TAG_NAVEGACAO == "Mova para o próximo ➔"


# ─── Regressão: payload legado sem foto real no slide 1 ─────────────────────

_PAYLOAD_LEGADO = {
    "slides": [
        {
            "slide_num": 1,
            "prompt_en": (
                "Modern friendly geometric sans-serif typography on a soft "
                "off-white #F7F9FF background. Centered elements respecting a "
                "1:1 square safe zone for Instagram grid preview. A floating "
                "white card with 24px rounded corners and subtle diffuse "
                "shadows. On the card, a bold title in Brand Blue #007799 with "
                "key words highlighted with a vibrant yellow #FFC20E marker "
                "line. Minimalist line-art icon of a glowing brain and laptop, "
                "no cartoon characters. Clean, professional look. "
                "Text overlay in Brazilian Portuguese: 'Usar tecnologia vs. "
                "Programar tecnologia: Qual o futuro do seu filho?'"
            ),
            "prompt_pt": "",
            "text_overlay": "Usar tecnologia vs. Programar tecnologia: Qual o futuro do seu filho?",
        }
    ]
}


def test_payload_legado_slide_1_vira_foto_real():
    from copy import deepcopy

    from batch_engine import normalizar_prompts

    res = normalizar_prompts(deepcopy(_PAYLOAD_LEGADO))
    s1 = res["slides"][0]
    assert FRASE_FOTO_REAL.lower() in s1["prompt_en"].lower()
    assert "off-white" not in s1["prompt_en"].lower()
    assert "floating white card" not in s1["prompt_en"].lower()
    assert _FRASE_TAG in s1["prompt_en"]
    assert "no cartoon characters" in s1["prompt_en"].lower()
    assert s1["tag_navegacao"] == TAG_NAVEGACAO
    assert s1["prompt_pt"]
    assert s1["referencias"] and s1["tipo_foto"] in CENAS_FOTO
    # overlay original preservado dentro do prompt
    assert "Usar tecnologia vs." in s1["prompt_en"]


def test_normalizar_prompts_e_idempotente():
    from copy import deepcopy

    from batch_engine import normalizar_prompts

    res = normalizar_prompts(deepcopy(_PAYLOAD_LEGADO))
    snapshot = [dict(s) for s in res["slides"]]
    normalizar_prompts(res)
    assert res["slides"] == snapshot


# ─── Regressão: cláusula de overlay duplicada (slide 5 real) ────────────────
# O Gemini parafraseou a cláusula ("highlight in Brazilian Portuguese") e o
# enforce anexou uma segunda, com texto diferente e depois da tag: duas
# instruções conflitantes para o modelo. O enforce agora reescreve o slide
# inteiro com FRASE_FOTO_REAL (composição sobre foto), unificando o overlay.

def _slide5_duplicado() -> dict:
    return {
        "slides": [
            {
                "slide_num": 5,
                "prompt_en": (
                    "Authentic school photo of a student focused on programming "
                    "at a modern desktop station at Ensina Mais Tatuapé. Bold "
                    "Brand Blue #007799 text overlay with yellow marker #FFC20E "
                    "highlight in Brazilian Portuguese: 'Mentes estruturadas e "
                    "inovadoras desde o Ensino Fundamental.' No cartoon "
                    f"characters. {_FRASE_TAG} text overlay in Brazilian "
                    "Portuguese: 'Mentes estruturadas e inovadoras desde cedo.'"
                ),
                "prompt_pt": "",
                "text_overlay": "Mentes estruturadas e inovadoras desde cedo.",
                "referencias": ["aluno_programacao"],
                "tipo_foto": "aluno_programacao",
                "usa_foto_real": True,
            }
        ]
    }


def test_slide5_clausula_duplicada_unificada():
    import re

    res = _enforce_foto_real(_slide5_duplicado())
    s5 = res["slides"][0]
    pen = s5["prompt_en"]
    # Slide 5 (thumbnail) é reescrito com FRASE_FOTO_REAL — composição sobre foto
    assert FRASE_FOTO_REAL.lower() in pen.lower()
    # Uma única cláusula de overlay, com o texto canônico do text_overlay
    assert re.findall(r"in Brazilian Portuguese: '[^']+'", pen) == [
        "in Brazilian Portuguese: 'Mentes estruturadas e inovadoras desde cedo.'"
    ]
    assert "Fundamental" not in pen
    # A cláusula continua antes da tag; a tag fecha o prompt
    assert "text overlay in brazilian portuguese" in pen.lower()
    tag_pos = pen.lower().find(_FRASE_TAG.lower())
    overlay_pos = pen.lower().find("text overlay in brazilian portuguese")
    assert overlay_pos < tag_pos
    assert pen.rstrip().endswith("'.")
    assert s5["prompt_pt"] == "Mentes estruturadas e inovadoras desde cedo."


def test_slide5_clausula_duplicada_e_idempotente():
    res = _enforce_foto_real(_slide5_duplicado())
    snap = res["slides"][0]["prompt_en"]
    corrigidos: list = []
    _enforce_foto_real(res, corrigidos=corrigidos)
    assert res["slides"][0]["prompt_en"] == snap
    assert not any("duplicada" in c for c in corrigidos)


def test_clausula_ausente_entra_antes_da_tag():
    dados = {
        "slides": [
            {
                "slide_num": 3,
                "prompt_en": f"Modern educational slide 3. No cartoon characters. {_FRASE_TAG}",
                "text_overlay": "Dica de estudo em casa",
            }
        ]
    }
    pen = _enforce_foto_real(dados)["slides"][0]["prompt_en"]
    assert "text overlay in Brazilian Portuguese: 'Dica de estudo em casa'" in pen
    assert pen.index("text overlay in Brazilian") < pen.index(_FRASE_TAG)
    # tag é sempre a última frase
    assert pen.rstrip().endswith("'.")
    assert pen.index("No cartoon characters") < pen.index(_FRASE_TAG)


def test_clausula_depois_da_tag_e_reposicionada():
    dados = {
        "slides": [
            {
                "slide_num": 3,
                "prompt_en": (
                    f"Modern educational slide 3. {_FRASE_TAG} "
                    "text overlay in Brazilian Portuguese: 'Texto certo aqui'."
                ),
                "text_overlay": "Texto certo aqui",
            }
        ]
    }
    pen = _enforce_foto_real(dados)["slides"][0]["prompt_en"]
    assert pen.index("text overlay in Brazilian") < pen.index(_FRASE_TAG)
    assert "Texto certo aqui" in pen
    assert pen.count("Brazilian Portuguese:") == 1


def test_slide8_remove_frase_de_tag_variante():
    from config import TAG_NAVEGACAO

    dados = {
        "slides": [
            {
                "slide_num": 8,
                "prompt_en": (
                    "Final CTA slide. Some corner text says '"
                    f"{TAG_NAVEGACAO}' in PT-BR. "
                    "text overlay in Brazilian Portuguese: 'Comente AULA'."
                ),
                "text_overlay": "Comente AULA",
            }
        ]
    }
    pen = _enforce_foto_real(dados)["slides"][0]["prompt_en"]
    assert TAG_NAVEGACAO not in pen
    assert "text overlay in Brazilian Portuguese" in pen


# ─── Regra 12 — fachada intocável ───────────────────────────────────────────

def _slide7() -> dict:
    return {
        "slides": [
            {
                "slide_num": 7,
                "prompt_en": (
                    "Realistic photo of the school facade on Rua Coelho Lisboa, 783. "
                    "No cartoon characters. "
                    f"{_FRASE_TAG}"
                ),
                "text_overlay": "De volta à harmonia familiar",
                "referencias": ["fachada"],
            }
        ]
    }


def test_fachada_intocavel_clausula_adicionada():
    from prompts import FRASE_FACHADA

    res = _enforce_foto_real(_slide7())
    pen = res["slides"][0]["prompt_en"]
    assert FRASE_FACHADA in pen
    assert pen.count(FRASE_FACHADA) == 1
    # antes da tag; a tag fecha o prompt
    assert pen.index(FRASE_FACHADA) < pen.index(_FRASE_TAG)
    assert pen.rstrip().endswith("'.")


def test_fachada_intocavel_idempotente():
    res = _enforce_foto_real(_slide7())
    snap = res["slides"][0]["prompt_en"]
    corrigidos: list = []
    _enforce_foto_real(res, corrigidos=corrigidos)
    assert res["slides"][0]["prompt_en"] == snap
    assert not any("fachada" in c for c in corrigidos)


def test_clausula_fachada_so_quando_referencia_fachada():
    from prompts import FRASE_FACHADA

    dados = {
        "slides": [
            {
                "slide_num": 3,
                "prompt_en": f"Modern slide 3. No cartoon characters. {_FRASE_TAG}",
                "text_overlay": "Dica de estudo",
                "referencias": ["logo"],
            }
        ]
    }
    pen = _enforce_foto_real(dados)["slides"][0]["prompt_en"]
    assert FRASE_FACHADA not in pen


def test_slide7_sempre_referencia_fachada():
    dados = {
        "slides": [
            {
                "slide_num": 7,
                "prompt_en": f"Facade photo. No cartoon characters. {_FRASE_TAG}",
                "text_overlay": "Prova social real",
                "referencias": ["equipe"],
            }
        ]
    }
    res = _enforce_foto_real(dados)
    assert "fachada" in res["slides"][0]["referencias"]
    from prompts import FRASE_FACHADA

    assert FRASE_FACHADA in res["slides"][0]["prompt_en"]


# ─── Personagens da Turma da Mônica — remoção automática ────────────────────

def test_personagem_removido_de_prompt_en_por_frase():
    dados = {
        "slides": [
            {
                "slide_num": 3,
                "prompt_en": (
                    "Step-by-step study cards with clock icons. "
                    "Featuring Cebolinha cartoon character in the corner. "
                    "No cartoon characters. "
                    f"{_FRASE_TAG}"
                ),
                "text_overlay": "Dica de estudo em casa",
            }
        ]
    }
    corrigidos: list = []
    res = _enforce_foto_real(dados, corrigidos=corrigidos)
    pen = res["slides"][0]["prompt_en"]
    assert "cebolinha" not in pen.lower()
    assert "Step-by-step study cards" in pen
    assert "No cartoon characters" in pen
    assert pen.rstrip().endswith("'.")


def test_personagem_removido_de_text_overlay_e_estilo():
    dados = {
        "slides": [
            {
                "slide_num": 2,
                "prompt_en": f"Blue cover slide. {_FRASE_TAG}",
                "text_overlay": "Aprenda com a Mônica lógica de verdade",
                "estilo": "Estilo Mônica para a capa",
            }
        ]
    }
    res = _enforce_foto_real(dados)
    s2 = res["slides"][0]
    assert "mônica" not in s2["text_overlay"].lower()
    assert "lógica de verdade" in s2["text_overlay"]
    assert "mônica" not in s2["estilo"].lower()
    assert "Estilo" in s2["estilo"]


def test_personagem_removido_de_base_prompt_e_dicas():
    dados = {
        "slides": [
            {
                "slide_num": 3,
                "prompt_en": f"Modern slide 3. No cartoon characters. {_FRASE_TAG}",
                "text_overlay": "Dica de estudo",
            }
        ],
        "base_prompt": (
            "Shared style: off-white #F7F9FF background, Brand Blue #007799. "
            "Mônica character illustrations are forbidden."
        ),
        "dicas_gerais": "Usar o logo 'Ensina Mais Turma da Mônica' e nunca citar Cascão.",
    }
    corrigidos: list = []
    res = _enforce_foto_real(dados, corrigidos=corrigidos)
    # frase com personagem removida; o resto do base_prompt continua intacto
    assert "Shared style" in res["base_prompt"]
    assert "mônica" not in res["base_prompt"].lower()
    # em texto curto (dicas), remove só o nome — a marca do logo fica
    assert "cascão" not in res["dicas_gerais"].lower()
    assert "Ensina Mais Turma da Mônica" in res["dicas_gerais"]
    assert any("base_prompt" in c for c in corrigidos)
    assert any("dicas_gerais" in c for c in corrigidos)


def test_personagem_marca_do_logo_permitida():
    dados = {
        "slides": [
            {
                "slide_num": 3,
                "prompt_en": (
                    "Modern slide 3 with official logo 'Ensina Mais Turma da Mônica'. "
                    f"No cartoon characters. {_FRASE_TAG}"
                ),
                "text_overlay": "Conheça a unidade",
            }
        ]
    }
    corrigidos: list = []
    pen = _enforce_foto_real(dados, corrigidos=corrigidos)["slides"][0]["prompt_en"]
    assert "Turma da Mônica" in pen
    assert not any("personagem removido" in c for c in corrigidos)


# ═══ Deduplicação de instruções repetidas (V9, achado na demo real) ══════════

def test_frases_iguais_uma_so_vez():
    de = "Compose ONLY design elements on top. "
    texto = de + de + "No cartoon characters."
    saida, removidas = _dedup_frases(texto)
    assert saida.count("Compose ONLY design elements") == 1
    assert len(removidas) == 1


def test_parafrase_e_removida_e_a_clausula_do_motor_sobrevive():
    # O caso real: o Gemini reescreveu a instrução da foto intocável e a regra 12
    # anexou a versão canônica por cima. Sobravam duas quase iguais.
    parafrase = (
        "Use the provided reference photo of the school facade exactly as-is as "
        "the full-bleed background -- do not regenerate, redraw, restyle, recolor."
    )
    texto = parafrase + " " + FRASE_FACHADA
    saida, removidas = _dedup_frases(texto, preferidos=_CLAUSULAS_DO_MOTOR)
    assert saida == FRASE_FACHADA
    assert len(removidas) == 1


def test_clausula_do_motor_quebrada_em_frases_continua_protegida():
    # A cláusula da fachada são três frases: sem proteção de bloco, a dedup a
    # desmontava e o validador depois reprovava o slide.
    texto = "Compose ONLY design elements on top: overlays. " + FRASE_FACHADA
    saida, _ = _dedup_frases(texto, preferidos=_CLAUSULAS_DO_MOTOR)
    assert FRASE_FACHADA in saida
    # a variante do modelo sai; a da cláusula do motor permanece (ela própria
    # contém "Compose ONLY design elements", então o teste mira o final da frase)
    assert "top: overlays" not in saida


def test_parafrase_nao_some_quando_a_clausula_do_motor_nao_esta_no_prompt():
    # Regressão: a dedup apagava a instrução do modelo de slides que não tinham
    # a cláusula do motor, deixando o slide sem regra nenhuma.
    parafrase = (
        "Use the provided reference photo of the school facade exactly as-is as "
        "the full-bleed background -- do not regenerate or restyle."
    )
    saida, _ = _dedup_frases(parafrase, preferidos=_CLAUSULAS_DO_MOTOR)
    assert parafrase in saida


def test_frases_distintas_sobrevem():
    texto = (
        "Bold Brand Blue #007799 text overlay in Brazilian Portuguese: 'x'. "
        "No cartoon characters. "
        "In the bottom right corner, a small discreet text says 'Mova'."
    )
    saida, removidas = _dedup_frases(texto, preferidos=_CLAUSULAS_DO_MOTOR)
    assert removidas == []
    assert saida == texto


def test_clausula_curta_nao_e_protegida_como_bloco():
    # Regressão: "no cartoon characters" é um fragmento curto. Protegido como
    # bloco, ele virava marcador no meio da frase e a dedup descartava o resto —
    # apagando a própria cláusula do motor do prompt.
    from batch_engine import _proteger_blocos
    from prompts import CLAUSULA_SEM_PERSONAGENS

    texto = "Clean layout. No cartoon characters, generic minimalist icons only."
    protegido, blocos = _proteger_blocos(texto, (CLAUSULA_SEM_PERSONAGENS,))
    assert CLAUSULA_SEM_PERSONAGENS in protegido.lower()
    assert blocos == []


def test_regra_7_sobrevive_a_dedup_no_slide_real():
    # Payloads reais trazem a cláusula em ordem e formato diferentes; a regra 7
    # precisa continuar presente depois de todas as passadas.
    slide = {
        "slide_num": 3,
        "prompt_en": (
            "Educational delivery slide with soft off-white #F7F9FF background, "
            "pastel blue card #E0F2FE, rounded corners 16px. "
            "text overlay in Brazilian Portuguese: '1) Identifique se o erro foi de "
            "conceito ou de desatenção. Separe o erro de cálculo do branco na "
            "teoria.'. In the bottom right corner, a small discreet text in "
            "Brazilian Portuguese says 'Mova para o próximo ➔'."
        ),
        "text_overlay": "1) Identifique se o erro foi de conceito ou de desatenção.",
        "prompt_pt": "Entrega",
        "referencias": [],
    }
    _garantir_regras(slide, None)
    assert "no cartoon characters" in slide["prompt_en"].lower()
    assert slide["prompt_en"].rstrip().endswith("Mova para o próximo ➔'.")


# ═══ Regra 4 — o overlay é cortado, não só avisado ══════════════════════════

def test_overlay_longo_dentro_do_limite():
    from batch_engine import MAX_PALAVRAS_OVERLAY, _cortar_overlay
    texto = " ".join(f"palavra{i}" for i in range(20))
    cortado, mudou = _cortar_overlay(texto, MAX_PALAVRAS_OVERLAY)
    assert mudou
    assert len(cortado.split()) <= MAX_PALAVRAS_OVERLAY


def test_overlay_dentro_do_limite_nao_e_tocado():
    from batch_engine import MAX_PALAVRAS_OVERLAY, _cortar_overlay
    texto = "A prova voltou vermelha."
    assert _cortar_overlay(texto, MAX_PALAVRAS_OVERLAY) == (texto, False)


def test_corte_prefere_frase_inteira_a_fracao_de_palavra():
    from batch_engine import _cortar_overlay
    texto = "Primeira frase completa. Segunda frase que é bem maior que o limite."
    cortado, _ = _cortar_overlay(texto, 8)
    assert cortado == "Primeira frase completa."


def test_corte_recua_ate_a_virgula_em_vez_de_quebrar_no_meio():
    # Sem recuo, saía "a criança associa o erro a…" — que lê como erro de escrita.
    from batch_engine import _cortar_overlay
    texto = "Quando a nota baixa é recebida como falha pessoal, a criança associa o erro a uma ameaça."
    cortado, _ = _cortar_overlay(texto, 9)
    assert cortado == "Quando a nota baixa é recebida como falha pessoal,"
    assert not cortado.endswith("…")


def test_thumbnail_tem_limite_mais_apertado():
    slide = {"slide_num": 1, "prompt_en": "", "text_overlay": ""}
    assert _limite_overlay(1) == 8
    assert _limite_overlay(3) == 15


def test_overlay_curto_no_slide_fica_intacto_no_prompt():
    slide = {
        "slide_num": 3,
        "prompt_en": (
            "Educational slide with soft background #F7F9FF. "
            "In the bottom right corner, a small discreet text in Brazilian "
            "Portuguese says 'Mova para o próximo ➔'."
        ),
        "text_overlay": "1) Separe o erro de cálculo do erro de conceito.",
        "prompt_pt": "Entrega",
        "referencias": [],
    }
    _garantir_regras(slide, None)
    assert slide["text_overlay"] == "1) Separe o erro de cálculo do erro de conceito."
    assert "no cartoon characters" in slide["prompt_en"].lower()


def test_overlay_longo_e_registrado_nas_correcoes():
    slide = {
        "slide_num": 2,
        "prompt_en": "Clean slide. In the bottom right corner, a small discreet text "
                     "in Brazilian Portuguese says 'Mova para o próximo ➔'.",
        "text_overlay": " ".join(f"palavra{i}" for i in range(19)),
        "prompt_pt": "Segunda capa",
        "referencias": [],
    }
    corrigidos: list[str] = []
    _garantir_regras(slide, corrigidos)
    assert len(slide["text_overlay"].split()) <= 15
    assert any("encurtado" in c for c in corrigidos), "corte de texto tem que ser visível"
