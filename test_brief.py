"""Testes do V8 — brief e storyboard.

O storyboard é o contrato que o renderer de animação vai consumir, e ele ainda
não existe (V9). A garantia que este arquivo faz é mais valiosa por isso: as
invariantes de tempo são verificadas aqui, como teste, em vez de aparecerem como
mp4 dessincronizado na mão do usuário.
"""

import pytest

import brief as brief_mod
import config
import persistence
from brief import (
    FPS,
    MOODS,
    montar_brief,
    montar_storyboard,
    resumo_storyboard,
    validar_brief,
    validar_storyboard,
)
from templates import TEMPLATES, eixo_para_template

IDEIA = {
    "id": "ideia_brief",
    "titulo": "Por que o filho explode depois da prova",
    "tema": "raiva ao errar",
    "eixo": "Comportamental",
    "persona_alvo": "Vigilante",
    "tipo_hook": "dado_chocante",
    "slides_sugeridos": [
        {"slide": 1, "tipo": "Capa", "texto": "Ele errou três questões e perdeu a prova inteira"},
        {"slide": 2, "tipo": "Segunda Capa", "texto": "A culpa parece ser da prova"},
        {"slide": 3, "tipo": "Entrega", "texto": "Primeiro passo"},
        {"slide": 4, "tipo": "Entrega", "texto": "Segundo passo"},
        {"slide": 5, "tipo": "Entrega", "texto": "Terceiro passo"},
        {"slide": 6, "tipo": "Ponte", "texto": "Ensino individualizado"},
        {"slide": 7, "tipo": "Prova", "texto": "Fachada da unidade"},
        {"slide": 8, "tipo": "CTA", "texto": "Comente FOCO"},
    ],
}


@pytest.fixture(autouse=True)
def disco_isolado(monkeypatch, tmp_path):
    monkeypatch.setattr(persistence, "BRIEF_FILE", str(tmp_path / "brief.json"))
    monkeypatch.setattr(persistence, "STORYBOARD_FILE", str(tmp_path / "storyboard.json"))


# ─── Brief ───────────────────────────────────────────────────────────────────

def test_brief_monta_invariantes_do_motor():
    b = montar_brief(IDEIA)
    assert b["eixo"] == "Comportamental"
    assert b["template"] == eixo_para_template("Comportamental")
    # palavra-chave e WhatsApp vêm do motor, não do usuário
    assert b["cta"]["palavra_chave"] == TEMPLATES["alivio_pressao"]["cta_padrao"] == "FOCO"
    assert b["cta"]["telefone"] == config.UNIDADE["whatsapp"]
    assert b["formato"]["proporcao"] == config.FORMATO["proporcao"]
    assert validar_brief(b) == []


def test_brief_resolve_tom_e_fidelidade():
    b = montar_brief(IDEIA, tom="viral", fidelidade="baixa")
    assert b["tom"] == "viral"
    assert b["tom_solicitado"] == "viral"
    assert b["fidelidade"] == "baixa"
    assert montar_brief(IDEIA)["tom"] == "storyteller"  # automático segue o eixo


def test_brief_degrada_fidelidade_alta_sem_foto():
    # abrir a aba já mostra o resultado do pedido, não a intenção dele
    b = montar_brief(IDEIA, fidelidade="alta")
    assert b["fidelidade"] == "media"
    assert any("FLOW_FOTOS" in a for a in b["avisos"])


def test_brief_eixo_desconhecido_cai_no_padrao():
    assert montar_brief({**IDEIA, "eixo": "Eixo Novo"})["eixo"] == "Didático"


def test_brief_pega_referencias_do_template():
    b = montar_brief(IDEIA)
    assert "fachada" in b["referencias"]
    assert len(b["referencias"]) == len(set(b["referencias"]))


def test_brief_modo_invalido_vira_png():
    assert montar_brief(IDEIA, modo="gif")["modo"] == "png"


def test_brief_carrega_roteiro_da_ideia():
    b = montar_brief(IDEIA)
    assert b["roteiro"][0]["texto"].startswith("Ele errou")
    assert b["num_slides"] == 8


def test_validar_brief_aponta_cada_erro():
    ruim = {
        "eixo": "Nope",
        "cta": {"palavra_chave": "QUALQUER"},
        "num_slides": 30,
        "referencias": ["nao_existe"],
        "fidelidade": "altissima",
        "modo": "gif",
    }
    avisos = validar_brief(ruim)
    texto = " ".join(avisos).lower()
    assert "eixo" in texto and "slides" in texto and "catálogo" in texto
    assert "fidelidade" in texto and "modo" in texto


def test_validar_brief_vazio():
    assert validar_brief({}) != []


# ─── Storyboard: tempo ───────────────────────────────────────────────────────

def test_storyboard_tem_invariante_de_tempo():
    for eixo in config.EIXOS:
        b = montar_brief({**IDEIA, "eixo": eixo, "slides_sugeridos": IDEIA["slides_sugeridos"]}, modo="vivo")
        sb = montar_storyboard(b)
        frames_beat = sb["frames_beat"]
        assert frames_beat == round(1800 / sb["bpm"]), "beat tem que ser inteiro em frames"
        for slide in sb["slides"]:
            assert slide["animacao"]["frames"] % frames_beat == 0
            assert abs(slide["animacao"]["duracao_s"] * FPS - slide["animacao"]["frames"]) < 0.01
        assert validar_storyboard(sb) == []


def test_todos_os_moods_da_tabela_fecham():
    # A tabela de mood veio da skill; se alguém mexer no BPM sem recalcular, este
    # teste falha antes do primeiro mp4 sair errado.
    for nome, mood in MOODS.items():
        frames_beat = round(1800 / mood["bpm"])
        frames = round(mood["duracao_s"] * FPS)
        assert frames % frames_beat == 0, f"{nome} não fecha na própria grade"
        assert frames / FPS == mood["duracao_s"]


def test_duracao_total_dentro_da_faixa_de_retencao():
    sb = montar_storyboard(montar_brief(IDEIA, modo="vivo"))
    assert 20 <= sb["duracao_total_s"] <= 32
    assert sb["total_frames"] == sb["duracao_total_s"] * FPS


def test_duracao_sempre_ajustada_e_avisada():
    b = montar_brief(IDEIA, modo="vivo")
    b["trilha"]["duracao_s"] = 3.7  # não fecha em beats de 30 frames
    sb = montar_storyboard(b)
    assert sb["avisos"], "ajuste de duração precisa aparecer como aviso"
    assert validar_storyboard(sb) == []


def test_encaixar_frames_corrige_dentro_da_faixa():
    frames_beat = 20
    frames, duracao, ajuste = brief_mod._encaixar_frames(2.5, frames_beat, 1)
    assert frames % frames_beat == 0
    assert 2.0 <= duracao <= 4.5
    assert ajuste  # houve ajuste, então avisou


def test_cue_cai_na_grade():
    sb = montar_storyboard(montar_brief(IDEIA, modo="vivo"))
    for slide in sb["slides"]:
        cue_frames = round(slide["audio"]["tempo_s"] * FPS)
        assert cue_frames % sb["frames_beat"] == 0


# ─── Storyboard: conteúdo ────────────────────────────────────────────────────

def test_overlay_respeita_o_limite_de_palavras():
    sb = montar_storyboard(montar_brief(IDEIA, modo="vivo"))
    for slide in sb["slides"]:
        limite = brief_mod.MAX_PALAVRAS_OVERLAY_THUMB if slide["slide"] in (1, 4, 5) else brief_mod.MAX_PALAVRAS_OVERLAY
        assert len(slide["texto_overlay"].split()) <= limite
    assert sb["slides"][0]["overlay_cortado"] is True


def test_movimento_de_slide_de_leitura_e_estatico():
    # Quem está lendo não quer a cena se mexendo por baixo do texto.
    sb = montar_storyboard(montar_brief(IDEIA, modo="vivo"))
    por_tipo = {s["tipo"]: s["animacao"]["movimento"]["tipo"] for s in sb["slides"]}
    assert por_tipo["Entrega"] == "estatico"
    assert por_tipo["Capa"] == "ken_burns"
    assert por_tipo["Prova"] == "estatico"


def test_capa_e_cta_ganham_entrada_forte():
    sb = montar_storyboard(montar_brief(IDEIA, modo="vivo"))
    entradas = {s["tipo"]: s["animacao"]["entrada"]["tipo"] for s in sb["slides"]}
    assert entradas["Capa"] == "fade_subida"
    assert entradas["CTA"] == "zoom_saia"


def test_prompt_gerado_tem_precedencia_sobre_o_roteiro():
    prompts = {"slides": [{"slide": 1, "tipo": "Capa", "texto": "Texto vindo do prompt gerado"}]}
    sb = montar_storyboard(montar_brief(IDEIA), prompts=prompts)
    assert sb["slides"][0]["texto"] == "Texto vindo do prompt gerado"


def test_referencia_do_prompt_vai_para_imagem():
    prompts = {"slides": [{"slide": 1, "tipo": "Capa", "referencias": ["laboratorio"]}]}
    sb = montar_storyboard(montar_brief(IDEIA), prompts=prompts)
    assert sb["slides"][0]["imagem"]["origem"] == "refs:laboratorio"


def test_storyboard_vazio_e_avaliado():
    assert validar_storyboard({}) == ["Storyboard vazio."]
    assert validar_storyboard({"slides": []}) == ["Storyboard vazio."]


def test_validar_storyboard_aponta_desync_real():
    sb = montar_storyboard(montar_brief(IDEIA, modo="vivo"))
    sb["slides"][0]["animacao"]["frames"] += 1  # dessincroniza
    avisos = validar_storyboard(sb)
    assert any("grade" in a for a in avisos)


def test_storyboard_marca_que_o_texto_esta_na_arte():
    # Default do motor: a arte do Flow já tem o texto, então o renderer não
    # redesenha. Quem usa foto pura desliga explicitamente.
    sb = montar_storyboard(montar_brief(IDEIA, modo="vivo"))
    assert all(s["texto_na_imagem"] is True for s in sb["slides"])
    sb2 = montar_storyboard(montar_brief(IDEIA, modo="vivo"), texto_na_imagem=False)
    assert all(s["texto_na_imagem"] is False for s in sb2["slides"])


def test_resumo_storyboard():
    r = resumo_storyboard(montar_storyboard(montar_brief(IDEIA, modo="vivo")))
    assert r["slides"] == 8
    assert r["duracao_total_s"] > 0
    assert set(r["movimentos"]) <= {"ken_burns", "estatico", "pulso", "parallax"}


# ─── Persistência ────────────────────────────────────────────────────────────

def test_brief_e_storyboard_persistem():
    assert persistence.carregar_brief() is None
    persistence.salvar_brief({"titulo": "T", "eixo": "Didático"})
    persistence.salvar_storyboard({"slides": [], "fps": 30})
    assert persistence.carregar_brief()["titulo"] == "T"
    assert persistence.carregar_storyboard()["fps"] == 30
    assert "atualizado_em" in persistence.carregar_brief()
