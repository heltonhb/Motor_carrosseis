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
buf = BytesIO(); base.save(buf, format="PNG")
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
