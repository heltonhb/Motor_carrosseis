"""
exemplo_carrossel_vivo.py — Demonstração ponta a ponta do motor.
Roda o fluxo real: ideia pelo Gemini (com tom e fidelidade do V5/V6), brief e
storyboard do V8, slides locais e o MP4 do V9.
Uso:
    uv run python exemplo_carrossel_vivo.py [nome_da_pasta]
O que é real e o que é rascunho está registrado no relatório final da pasta.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import acervo
import batch_engine
import brief as brief_mod
import carrossel_vivo as cv
import persistence
from prompts import TEMPERATURAS, formatar_txt_prompts, get_prompt_ideias, validate_prompts

PASTA = Path(sys.argv[1] if len(sys.argv) > 1 else f"{datetime.now():%d-%m-%Y}_exemplo")
def log(msg: str) -> None:
    print(msg, flush=True)
def main() -> int:
    PASTA.mkdir(parents=True, exist_ok=True)
    # 1 ─ Ideia real pelo Gemini
    log("1/5 · gerando ideias no Gemini…")
    contexto = (
        "Unidade: Ensina Mais Tatuapé. Tema do pedido do operador: um carrossel "
        "sobre a criança ficar com raiva quando erra a prova, para pais do "
        "Tatuapé."
    )
    from gemini import call_gemini_json
    dados = call_gemini_json(get_prompt_ideias("didatico"), contexto, temperature=TEMPERATURAS["ideias"])
    ideias = (dados or {}).get("ideias") or []
    if not ideias:
        log("   ! Gemini não devolveu ideias — seguindo com uma ideia local.")
        ideias = [{
            "id": "ideia_exemplo",
            "titulo": "Por que a criança explode depois da prova",
            "eixo": "Comportamental",
            "tema": "raiva ao errar a prova",
            "publico_alvo": "Pais do Tatuapé com filho no Fundamental",
            "persona_alvo": "Vigilante",
            "tipo_hook": "dado_chocante",
            "slides_sugeridos": [
                {"slide": 1, "tipo": "Capa", "texto": "Ele errou cinco e a culpa foi da professora"},
                {"slide": 2, "tipo": "Segunda Capa", "texto": "Ninguém ensinou o método que resolve"},
                {"slide": 3, "tipo": "Entrega", "texto": "Leia a questão duas vezes antes de responder"},
                {"slide": 4, "tipo": "Entrega", "texto": "Grife o verbo: o que a questão está pedindo"},
                {"slide": 5, "tipo": "Entrega", "texto": "Resolva de trás para a frente, conferindo cada etapa"},
                {"slide": 6, "tipo": "Ponte", "texto": "Aula individual corrige a lacuna antes da prova"},
                {"slide": 7, "tipo": "Prova", "texto": "Unidade no Tatuapé, com turmas pequenas"},
                {"slide": 8, "tipo": "CTA", "texto": "Comente FOCO ou fale no WhatsApp"},
            ],
        }]
    ideia_atual = ideias[0]
    log(f"   ideia escolhida: {ideia_atual['titulo']} ({ideia_atual['eixo']})")

    # 2 ─ Brief (V8)
    log("2/5 · montando brief…")
    brief = brief_mod.montar_brief(
        {**ideia_atual, "id": ideia_atual.get("id", "ideia_exemplo")},
        tom="storyteller",
        fidelidade="alta",
        modo="vivo",
    )
    avisos_brief = brief_mod.validar_brief(brief)
    persistence.salvar_brief(brief)
    (PASTA / "brief.json").write_text(
        json.dumps(brief, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"   avisos: {avisos_brief or 'nenhum'}")

    # 3 ─ Prompts de imagem reais (V5/V6/V7 no prompt)
    log("3/5 · gerando prompts de imagem…")
    avisos: list[str] = []
    payload = batch_engine.gerar_prompts_ideia(
        ideia_atual, forcar=True, avisos=avisos, fidelidade="alta"
    )
    if payload:
        (PASTA / "prompts_imagem.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    log(f"   prompts: {len((payload or {}).get('slides', []))} · avisos: {len(avisos)}")
    for a in avisos[:6]:
        log(f"   ⚠️ {a}")

    # O txt do pipeline de automação sai do payload JÁ NORMALIZADO (dedup +
    # cláusulas do motor), nunca do bruto — senão a extensão recebe o prompt com
    # instrução repetida.
    if payload:
        bruto = json.loads(json.dumps(payload))
        payload = batch_engine.normalizar_prompts(bruto)
        avisos_final = validate_prompts(payload)
        (PASTA / "prompts_imagem.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        txt = formatar_txt_prompts(payload)
        (PASTA / "prompts_automaticacao.txt").write_text(txt, encoding="utf-8")
        blocos = [b for b in txt.split("\n\n") if b.strip()]
        log(f"   txt do pipeline: {len(blocos)} blocos · {len(txt.split())} palavras")
        for a in avisos_final:
            log(f"   ⚠️ {a}")

    # 4 ─ Storyboard (V8)
    log("4/5 · montando storyboard…")
    storyboard = brief_mod.montar_storyboard(brief, prompts=payload, texto_na_imagem=True)
    persistence.salvar_storyboard(storyboard)
    (PASTA / "storyboard.json").write_text(
        json.dumps(storyboard, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"   {cv.descrever(storyboard)}")

    # 5 ─ MP4 (V9)
    log("5/5 · renderizando o carrossel vivo (leva cerca de 1 minuto)…")
    resultado = cv.renderizar_carrossel_vivo(
        ideia_atual,
        storyboard,
        saida=PASTA / "carrossel.mp4",
        diretorio_pngs=PASTA / "slides",
        progresso=lambda i, n: log(f"   slide {i}/{n}"),
    )

    relatorio = f"""# Demonstração — {PASTA.name}

Gerado em {datetime.now():%Y-%m-%d %H:%M} pelo fluxo ponta a ponta do motor.

## O que é real

- **Ideia**: gerada pelo Gemini (`get_prompt_ideias("didatico")`).
- **Prompts de imagem**: gerados pelo Gemini com fidelidade alta e validados por
  `validate_prompts` — prontos para colar no Google Flow.
- **Brief e storyboard**: determinísticos, dentro das invariantes de tempo.
- **MP4**: renderizado de verdade com Pillow + ffmpeg.

## O que é rascunho

- **As imagens dos slides** são o rascunho local do template (`image_utils`),
  não as artes finais do Google Flow. O movimento, o tempo e o áudio são reais;
  o visual não. Para animar a arte final, gere os PNGs no Flow e coloque na
  pasta `slides/` antes de renderizar.

## Arquivos

| arquivo | o que é |
|---|---|
| `carrossel.mp4` | {resultado.frames} frames · {resultado.duracao_s}s · {storyboard['fps']} fps |
| `carrossel.wav` | trilha sintetizada no grid de {storyboard['bpm']} bpm |
| `slides/*.png` | rascunhos locais |
| `brief.json` | contrato do carrossel (V8) |
| `storyboard.json` | contrato no tempo (V8) |
| `prompts_imagem.json` | prompts para o Google Flow (V5/V6) |

## Brief

- Tema: {brief['tema']}
- Eixo: {brief['eixo']} (KPI: {brief['kpi_alvo']})
- Tom: {brief['tom']} · Fidelidade: {brief['fidelidade']}
- CTA: {brief['cta']['palavra_chave']} · {brief['cta']['telefone']}
- Mood: {brief['trilha']['mood']} ({storyboard['bpm']} bpm, beat de {storyboard['frames_beat']} frames)
- Referências: {', '.join(brief['referencias'])}

## Avisos da geração

{chr(10).join(f'- {a}' for a in avisos) or '- nenhum'}
{chr(10).join(f'- {a}' for a in storyboard['avisos']) or '- nenhum (tempo dentro da invariante)'}

## Acervo

{json.dumps(acervo.resumo_acervo(), ensure_ascii=False)}
"""
    (PASTA / "RELATORIO.md").write_text(relatorio, encoding="utf-8")
    log(f"\nPronto: {PASTA.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
