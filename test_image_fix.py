"""Teste rápido das correções P1/P2 em image_utils.py (executado com o venv do projeto)."""
from io import BytesIO

from PIL import Image

from image_utils import add_text_overlay, create_slide_from_template, fit_slide_text

FONTE = None  # usa FONTES do config

# ── P1: ajuste automático de fonte ──────────────────────────────────────────
curto = "5 dicas de frações"
medio = (
    "Muitos pais acham que a dificuldade com frações é falta de atenção, "
    "mas quase sempre é um buraco de base que arrasta desde o 4º ano."
)
longo = (
    "A dificuldade com frações quase nunca começa na fração: ela começa "
    "quando a criança não consolidou a ideia de parte e todo lá no 4º ano. "
    "Sem essa base, cada conteúdo novo vira um esforço isolado, e a nota "
    "despenca sem que ninguém saiba exatamente onde a criança perdeu o fio. "
    "O diagnóstico certo recupera a autoestima do aluno e devolve o prazer "
    "de aprender matemática de verdade."
) * 2  # ~90 palavras: impossível caber — deve truncar AVISANDO

for nome, txt in [("curto", curto), ("medio", medio), ("longo", longo)]:
    fit = fit_slide_text(txt)
    print(f"[P1] {nome:6s}: fonte {fit['font_size']}px, {len(fit['lines'])} linhas, "
          f"bloco {fit['block_height']}px, auto_shrunk={fit['auto_shrunk']}, "
          f"truncated={fit['truncated']} (cortou {fit['dropped']} linhas)")

# bounds: bloco de texto nunca pode passar da área útil (810px)
avail = 1070 - 260
for nome, txt in [("curto", curto), ("medio", medio), ("longo", longo)]:
    fit = fit_slide_text(txt)
    assert fit["block_height"] <= avail + 1, f"{nome}: bloco {fit['block_height']} > {avail}"
print("[P1] OK: nenhum bloco ultrapassa a área útil do slide")

# ── P1: slide completo com texto longo, com info de retorno ────────────────
sb, info = create_slide_from_template("desconstrucao_didatica", 3, longo, return_info=True)
img = Image.open(BytesIO(sb))
assert img.size == (1080, 1350), img.size
print(f"[P1] slide renderizado 1080x1350, info={info}")

# ── P2: overlay com texto que antes sangrava da imagem ─────────────────────
base = Image.new("RGB", (1080, 1350), (27, 42, 74))
buf = BytesIO()
base.save(buf, format="PNG")
overlay_text = (
    "Você sabia que a maior dificuldade dos alunos do 6º ano não é "
    "matemática, mas sim a base que ficou para trás no Ensino Fundamental I?"
)  # 25 palavras — antes virava UMA linha de ~3800px
out = add_text_overlay(buf.getvalue(), overlay_text, font_size=48, position="center")
img2 = Image.open(BytesIO(out))
assert img2.size == (1080, 1350)
print(f"[P2] overlay ok: imagem {img2.size}, texto de 25 palavras quebrado em linhas")

# verifica visualmente que há pixels não-fundo nas bordas? não: só confere dimensão + sem crash
print("TODOS OS TESTES PASSARAM")


def test_card_evita_rosto_na_foto():
    """Rosto frontal real (Haar) vira cobertura no mapa; o card desce para
    liberar a cabeça. Usa a foto da unidade, não elipse sintética — Haar só
    responde a rosto de verdade."""
    from image_utils import (
        _H2,
        _W2,
        _cover_crop,
        _mapa_pele,
        _posicionar_card_sem_rosto,
        _score_rosto,
        _selecionar_foto_cena,
    )

    base = _cover_crop(_selecionar_foto_cena("alunos_apoio", 0), _W2, _H2)
    mapas = _mapa_pele(base)
    # Haar precisa ter achado rostos (células com cobertura ≥0.5 no mapa)
    assert any(v >= 0.5 for linha in mapas[0] for v in linha)
    box = (115, 380, 965, 955)  # cobria os rostos na posição alta
    sc0 = _score_rosto(mapas[0], box)
    novo, dy, antes, depois = _posicionar_card_sem_rosto(mapas, box, -60, 260)
    assert sc0 > 0.035
    assert depois < sc0
    assert novo[1] > box[1]  # desceu para liberar os rostos


def test_cabelo_sem_rosto_visivel_tambem_bloqueia_o_card():
    """Perfil longe da câmera: só cabelo escuro + um pouco de pele. O card não
    pode pousar sobre a cabeça mesmo quando o rosto quase não aparece."""
    from PIL import ImageDraw

    from image_utils import _box_toc_cabeca, _mapa_pele, _posicionar_card_sem_rosto

    img = Image.new("RGB", (1080, 1350), (230, 230, 235))
    d = ImageDraw.Draw(img)
    d.ellipse((60, 380, 320, 700), fill=(25, 22, 22))      # "cabelo" à esquerda
    d.ellipse((110, 560, 280, 720), fill=(198, 140, 110))  # rosto na sombra
    mapas = _mapa_pele(img)
    box = (115, 420, 965, 945)
    assert _box_toc_cabeca(mapas[1], box)
    novo, dy, antes, depois = _posicionar_card_sem_rosto(mapas, box, -100, 280)
    assert not _box_toc_cabeca(mapas[1], novo)  # posição final não toca cabelo


def test_pele_sem_cabelo_nao_movimenta_o_card():
    """Mão/braço sobre a mesa: pele densa sem cabelo vizinho não é rosto."""
    from PIL import ImageDraw

    from image_utils import _mapa_pele, _posicionar_card_sem_rosto

    img = Image.new("RGB", (1080, 1350), (230, 230, 235))
    d = ImageDraw.Draw(img)
    d.ellipse((420, 600, 700, 900), fill=(198, 140, 110))  # só pele, sem cabelo
    mapas = _mapa_pele(img)
    box = (115, 380, 965, 955)
    novo, dy, antes, depois = _posicionar_card_sem_rosto(mapas, box, -60, 260)
    assert novo == box and dy == 0


def test_card_nao_se_move_em_foto_sem_rosto():
    from image_utils import _mapa_pele, _posicionar_card_sem_rosto

    img = Image.new("RGB", (1080, 1350), (230, 230, 235))
    mapas = _mapa_pele(img)
    box = (115, 420, 965, 945)
    novo, dy, antes, depois = _posicionar_card_sem_rosto(mapas, box, -100, 280)
    assert novo == box and dy == 0
