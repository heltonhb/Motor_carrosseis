"""
gerar_exemplo_glass.py
Gera um carrossel completo (8 slides) na pasta teste_glass_09-11-2026/
para avaliar o novo efeito de vidro (glassmorphism realista).

Uso:
    uv run python3 gerar_exemplo_glass.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Garante que o projeto está no path
sys.path.insert(0, str(Path(__file__).parent))

from image_utils import render_slide_hd

SAIDA = Path(__file__).parent / "teste_glass_09-11-2026"
SAIDA.mkdir(exist_ok=True)

# Carrossel de exemplo: tema real da unidade
SLIDES = [
    {
        "num": 1,
        "texto": "Seu filho trava na hora da prova mesmo sabendo a matéria?",
        "eixo": "Diagnóstico",
        "cena": "aluno_programacao",
        "ctr": {
            "lado_negative_space": "direita",
            "texto_de_impacto": "trava na prova",
            "paleta_complementar": {"destaque": "#FFC20E"},
        },
    },
    {
        "num": 2,
        "texto": "O problema não é falta de esforço — é falta de método ativo.",
        "eixo": "Diagnóstico",
        "cena": "recepcao_unidade",
    },
    {
        "num": 3,
        "texto": "Rotina passiva vs. Método Ensina Mais: pratica até fixar.",
        "eixo": "Didático",
        "cena": "laboratorio",
    },
    {
        "num": 4,
        "texto": "Cada aluno recebe um plano personalizado de estudo e revisão.",
        "eixo": "Didático",
        "cena": "aluno_programacao",
        "ctr": {
            "lado_negative_space": "esquerda",
            "texto_de_impacto": "plano personalizado",
            "paleta_complementar": {"destaque": "#58B947"},
        },
    },
    {
        "num": 5,
        "texto": "Em 4 semanas, a maioria dos alunos já recupera até 2 notas.",
        "eixo": "Comportamental",
        "cena": "alunos_apoio",
        "ctr": {
            "lado_negative_space": "direita",
            "texto_de_impacto": "recupera 2 notas",
            "paleta_complementar": {"destaque": "#FFC20E"},
        },
    },
    {
        "num": 6,
        "texto": "Programação, robótica, apoio escolar e reforço — tudo em Tatuapé.",
        "eixo": "Didático",
        "cena": "laboratorio",
    },
    {
        "num": 7,
        "texto": "\"Meu filho passou direto no 9º ano depois de 3 meses aqui.\"",
        "eixo": "Comportamental",
        "cena": "fachada",
    },
    {
        "num": 8,
        "texto": "Agende uma aula experimental gratuita esta semana.",
        "eixo": "Didático",
        "cena": "recepcao_unidade",
        "cta_keyword": "AULA",
    },
]

NONCE = 20261109  # fixo para fotos determinísticas

def main() -> None:
    total = len(SLIDES)
    print(f"Gerando {total} slides em {SAIDA} ...")

    for s in SLIDES:
        num = s["num"]
        print(f"  Slide {num:02d}/{total} — {s['texto'][:55]}...", end=" ", flush=True)

        png_bytes, info = render_slide_hd(
            slide_num=num,
            texto=s["texto"],
            eixo=s.get("eixo", "Didático"),
            cta_keyword=s.get("cta_keyword", "AULA"),
            referencias=[s["cena"]],
            destaques=None,
            ctr=s.get("ctr"),
            total_slides=total,
            nonce=NONCE,
        )

        destino = SAIDA / f"slide_{num:02d}.png"
        destino.write_bytes(png_bytes)

        flags = []
        if info.get("auto_shrunk"):
            flags.append("fonte↓")
        if info.get("truncated"):
            flags.append(f"truncado({info['dropped']}lin)")
        if info.get("ctr_aplicado"):
            c = info["ctr_aplicado"]
            flags.append(f"ctr={c['lado']}")
        flag_str = f"  [{', '.join(flags)}]" if flags else ""
        tam_kb = len(png_bytes) // 1024
        print(f"OK  {tam_kb} KB{flag_str}")

    print(f"\nPronto. Abra a pasta:\n  {SAIDA}/")

if __name__ == "__main__":
    main()
