"""
batch_engine.py — Orquestrador único de geração em lote/pipeline.

E2 do MELHORIAS.md: Lote (tab 7) e Pipeline (tab 8) compartilhavam a mesma
lógica de orquestração duplicada. Este módulo centraliza as etapas:

- gerar_prompts_ideia(ideia)  → prompts de imagem (PROMPT_PROMPTS_IMAGEM)
- gerar_legendas_ideia(ideia) → legendas (PROMPT_LEGENDAS)
- gerar_cronograma(ideias)     → cronograma 2 semanas (get_prompt_cronograma)
- gerar_slides_ideia(ideia)    → slides renderizados (generate_all_slides)

Cada função devolve o resultado cru; a UI decide como exibir/persistir.
"""

import json

from gemini import call_gemini_json, invalidate_cache
from image_utils import generate_all_slides
from prompts import (
    PROMPT_LEGENDAS,
    PROMPT_PROMPTS_IMAGEM,
    TEMPERATURAS,
    get_prompt_cronograma,
)
from templates import eixo_para_template


def _ctx_ideia(ideia: dict) -> str:
    """Contexto enxuto do carrossel para o Gemini.

    Serializa uma única vez só os campos relevantes: sem score/justificativa
    (ruído) e sem duplicar slides_sugeridos — antes o JSON ia 2x.
    """
    campos = (
        "titulo", "eixo", "persona_alvo", "tipo_hook", "tema", "publico_alvo",
        "palavras_chave_seo", "cta", "kpi_alvo",
    )
    slim = {c_: ideia[c_] for c_ in campos if ideia.get(c_)}
    slim["slides_sugeridos"] = [
        {k: sl.get(k) for k in ("slide", "tipo", "texto")}
        for sl in ideia.get("slides_sugeridos") or []
    ]
    return f"Carrossel:\n{json.dumps(slim, ensure_ascii=False)}"


def gerar_prompts_ideia(ideia: dict, forcar: bool = False) -> dict | None:
    """Gera prompts de imagem para UMA ideia. Retorna dict ou None.

    forcar=True invalida o cache de sessão antes — cada clique do usuário
    gera um lote novo (mesmo comportamento da aba Ideias, M6).
    """
    ctx = _ctx_ideia(ideia)
    if forcar:
        invalidate_cache(PROMPT_PROMPTS_IMAGEM, ctx)
    return call_gemini_json(PROMPT_PROMPTS_IMAGEM, ctx, temperature=TEMPERATURAS["prompts_imagem"])


def gerar_legendas_ideia(ideia: dict, forcar: bool = False) -> dict | None:
    """Gera 3 opções de legenda para UMA ideia. Retorna dict ou None."""
    ctx = _ctx_ideia(ideia)
    if forcar:
        invalidate_cache(PROMPT_LEGENDAS, ctx)
    return call_gemini_json(PROMPT_LEGENDAS, ctx, temperature=TEMPERATURAS["legendas"])


def gerar_cronograma(ideias: list, forcar: bool = False) -> dict | None:
    """Gera cronograma de 2 semanas para a lista de ideias. Retorna dict ou None."""
    ctx = f"Ideias selecionadas:\n{json.dumps(ideias, ensure_ascii=False)}"
    if forcar:
        invalidate_cache(get_prompt_cronograma(), ctx)
    return call_gemini_json(get_prompt_cronograma(), ctx, temperature=TEMPERATURAS["cronograma"])


def gerar_slides_ideia(ideia: dict) -> list:
    """Renderiza os slides de UMA ideia com o template do eixo.
    Retorna lista de tuplas (nº slide, bytes, info)."""
    tkey = eixo_para_template(ideia.get("eixo", "Didático"))
    return generate_all_slides(tkey, ideia.get("slides_sugeridos", []))


def processar_lote(
    ideias: list,
    fazer_prompts: bool = True,
    fazer_slides: bool = True,
    fazer_cronograma: bool = True,
    forcar: bool = False,
    on_progress=None,
) -> dict:
    """
    Orquestra o processamento de N ideias.

    on_progress: callback opcional (step: int, total: int, msg: str).

    Retorna dict no formato usado pela tab 7 (Lote):
    {
      "prompts_{idx}": {"titulo": ..., "prompts": ...},
      "slides_{idx}":  {"titulo": ..., "images": [...]},
      "cronograma": {...},
    }
    """
    results: dict = {}
    total = len(ideias) + (1 if fazer_cronograma else 0)
    step = 0

    for idx, ideia in enumerate(ideias):
        titulo = ideia.get("titulo", f"Ideia {idx + 1}")
        if on_progress:
            on_progress(step, total, f"⚙️ Processando: {titulo}…")

        if fazer_prompts:
            dados = gerar_prompts_ideia(ideia, forcar=forcar)
            if dados:
                results[f"prompts_{idx}"] = {"titulo": titulo, "prompts": dados}

        if fazer_slides:
            imgs = gerar_slides_ideia(ideia)
            results[f"slides_{idx}"] = {"titulo": titulo, "images": imgs}

        step += 1
        if on_progress:
            on_progress(step, total, f"✅ {titulo}")

    if fazer_cronograma:
        if on_progress:
            on_progress(step, total, "📅 Gerando cronograma…")
        cron_data = gerar_cronograma(ideias, forcar=forcar)
        if cron_data:
            results["cronograma"] = cron_data
        step += 1
        if on_progress:
            on_progress(step, total, "📅 Cronograma pronto")

    return results
