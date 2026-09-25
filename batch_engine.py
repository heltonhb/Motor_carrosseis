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
import logging
import re

from config import FLOW_FOTOS, TAG_NAVEGACAO
from gemini import call_gemini_json, invalidate_cache
from image_utils import generate_all_slides
from prompts import (
    PADROES_PROIBIDOS_FOTO,
    PROMPT_LEGENDAS,
    PROMPT_PROMPTS_IMAGEM,
    TEMPERATURAS,
    get_prompt_cronograma,
    validate_prompts,
)
from refs_catalog import CENAS_FOTO, anexos_gemini, cena_valida, desc_en
from templates import eixo_para_template

logger = logging.getLogger(__name__)

# ─── Cenas reais para compor os prompts de foto ─────────────────────────────
# Mapeamento tipo_foto → fragmento descritivo padrão em inglês, direto do
# catálogo único (refs/catalogo.json) — mesma fonte do validador.
_CENAS_FOTO: dict[str, str] = {chave: desc_en(chave) for chave in CENAS_FOTO}

# Rodízio explícito de cena para os slides thumbnail quando o Gemini não
# informa um tipo_foto válido (1→recepção, 4→robótica, 5→programação).
_TIPOS_RODIZIO: dict[int, str] = {
    1: "recepcao_unidade",
    4: "alunos_robotica",
    5: "aluno_programacao",
}

# Padrões de layout genérico que NÃO devem aparecer nos slides thumbnail
# (fonte única: prompts.PADROES_PROIBIDOS_FOTO).
_PADROES_PROIBIDOS_RE = re.compile(
    "|".join(re.escape(p) for p in PADROES_PROIBIDOS_FOTO),
    re.IGNORECASE,
)

_FRASE_TAG = (
    f"In the bottom right corner, a small discreet text in Brazilian "
    f"Portuguese says '{TAG_NAVEGACAO}'."
)


def _para_int(valor) -> int | None:
    """slide_num pode vir como 1, '1' ou 'Slide 1' — qualquer forma serve."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        m = re.search(r"\d+", str(valor or ""))
        return int(m.group()) if m else None


def _normaliza_refs(slide: dict, tipo: str | None) -> None:
    """Só chaves do catálogo; ≥1 cena fotográfica nos slides 1, 4, 5 e 7."""
    refs = [r for r in (slide.get("referencias") or []) if cena_valida(r)]
    snum = _para_int(slide.get("slide_num"))
    if snum in {1, 4, 5, 7} and not any(r in CENAS_FOTO for r in refs):
        refs.append(tipo if tipo in CENAS_FOTO else CENAS_FOTO[0])
    if not refs:
        refs.append("logo")
    slide["referencias"] = refs


def _anexar(prompt: str, frase: str) -> str:
    """Anexa uma frase ao final do prompt, com pontuação limpa (idempotente)."""
    if frase.lower() in prompt.lower():
        return prompt
    return f"{prompt.rstrip('. ')}. {frase}"


def _garantir_regras(slide: dict, corrigidos: list | None) -> None:
    """Garante as regras 5, 6 e 7 em TODO slide, seja qual for a origem do JSON."""
    snum = _para_int(slide.get("slide_num"))
    if snum is None:
        return
    prompt_en = (slide.get("prompt_en") or "").strip()
    if not prompt_en:
        return
    overlay = (slide.get("text_overlay") or "").strip()
    antes = prompt_en

    # Regra 5 — cláusula de idioma do overlay
    if overlay and "text overlay in brazilian portuguese" not in prompt_en.lower():
        prompt_en = _anexar(
            prompt_en, f"text overlay in Brazilian Portuguese: '{overlay}'."
        )

    # Regra 7 — cláusula anti-personagem
    if "no cartoon characters" not in prompt_en.lower():
        prompt_en = _anexar(
            prompt_en, "No cartoon characters, generic minimalist line-art icons only."
        )

    # Regra 6 — tag de navegação no prompt_en (presente fora do slide 8, ausente no 8)
    if snum == 8:
        if _FRASE_TAG.lower() in prompt_en.lower():
            prompt_en = re.sub(
                re.escape(_FRASE_TAG), "", prompt_en, flags=re.IGNORECASE
            ).strip()
        slide["tag_navegacao"] = ""
    else:
        prompt_en = _anexar(prompt_en, _FRASE_TAG)
        slide["tag_navegacao"] = TAG_NAVEGACAO

    # prompt_pt nunca fica vazio quando existe overlay
    if overlay and not (slide.get("prompt_pt") or "").strip():
        slide["prompt_pt"] = overlay

    if prompt_en != antes:
        slide["prompt_en"] = prompt_en
        if corrigidos is not None:
            corrigidos.append(
                f"slide {snum}: cláusulas obrigatórias completadas (regras 5/6/7)"
            )


def _enforce_foto_real(dados: dict, corrigidos: list | None = None) -> dict:
    """Pós-processamento dos prompts de imagem — idempotente.

    Regras programáticas que o Gemini ignora com frequência:
    - slides 1, 4 e 5: prompt_en reescrito com foto real ("Authentic school
      photo of...") e padrões genéricos removidos (regra 2);
    - todos os slides: tag de navegação no prompt_en (fora do 8), cláusula
      "no cartoon characters" e "text overlay in Brazilian Portuguese"
      (regras 5, 6 e 7);
    - referencias limpas contra o catálogo (regra 11).

    Preserva o text_overlay original. Cada correção vira uma linha em
    `corrigidos` (out-collector opcional).
    """
    if not isinstance(dados, dict):
        return dados

    slides = dados.get("slides")
    if not slides:
        return dados

    for slide in slides:
        snum = _para_int(slide.get("slide_num"))
        if snum is None:
            continue

        prompt_en = (slide.get("prompt_en") or "").strip()
        overlay = (slide.get("text_overlay") or "").strip()

        if snum in {1, 4, 5} and prompt_en:
            if prompt_en.lower().startswith("authentic school photo"):
                # Conforme: só limpa padrões genéricos residuais e ancora os campos
                limpo = _PADROES_PROIBIDOS_RE.sub("", prompt_en).strip()
                if limpo != prompt_en:
                    slide["prompt_en"] = limpo
                    if corrigidos is not None:
                        corrigidos.append(f"slide {snum}: padrões genéricos removidos")
                slide["usa_foto_real"] = True
                if slide.get("tipo_foto") not in _CENAS_FOTO:
                    slide["tipo_foto"] = _TIPOS_RODIZIO[snum]
                _normaliza_refs(slide, slide["tipo_foto"])
            else:
                # ── Slide NÃO-conforme: reescrever o prompt_en ──────────────
                logger.info(
                    "Slide %d: prompt_en não iniciava com 'Authentic school photo'. "
                    "Reescrevendo automaticamente.",
                    snum,
                )
                tipo = slide.get("tipo_foto")
                if tipo not in _CENAS_FOTO:
                    tipo = _TIPOS_RODIZIO[snum]
                cena = _CENAS_FOTO[tipo]

                # Só o que está entre aspas — a frase da tag não pode entrar
                overlay_match = re.search(
                    r"text overlay in Brazilian Portuguese:\s*['\"]([^'\"]+)['\"]",
                    prompt_en,
                    re.IGNORECASE,
                )
                overlay_texto = (
                    overlay_match.group(1).strip() if overlay_match else overlay
                )

                slide["prompt_en"] = (
                    f"Authentic school photo of {cena}, "
                    f"1080x1350 px vertical 4:5 format, "
                    f"centered elements respecting a 1:1 square safe zone (1080x1080 px) "
                    f"for Instagram grid preview. "
                    f"Bold Brand Blue #007799 text overlay with vibrant yellow #FFC20E "
                    f"marker highlight, modern geometric sans-serif typography. "
                    f"Official 'Ensina Mais Turma da Mônica' logo badge at the bottom corner. "
                    f"No cartoon characters, generic minimalist line-art icons only. "
                    f"text overlay in Brazilian Portuguese: '{overlay_texto}'. "
                    f"{_FRASE_TAG}"
                )
                slide["usa_foto_real"] = True
                slide["tipo_foto"] = tipo
                _normaliza_refs(slide, tipo)
                if corrigidos is not None:
                    corrigidos.append(
                        f"slide {snum}: prompt_en reescrito com foto real ({tipo})"
                    )

        _normaliza_refs(slide, slide.get("tipo_foto"))
        _garantir_regras(slide, corrigidos)

    return dados


def normalizar_prompts(dados: dict) -> dict:
    """Normaliza um payload de prompts (inclusive gerações antigas do histórico)."""
    return _enforce_foto_real(dados)


def _ctx_ideia(ideia: dict) -> str:
    """Contexto enxuto do carrossel para o Gemini.

    Serializa uma única vez só os campos relevantes: sem score/justificativa
    (ruído) e sem duplicar slides_sugeridos — antes o JSON ia 2x.
    """
    campos = (
        "titulo", "eixo", "curso", "persona_alvo", "tipo_hook", "tema", "publico_alvo",
        "palavras_chave_seo", "cta", "kpi_alvo",
    )
    slim = {c_: ideia[c_] for c_ in campos if ideia.get(c_)}
    slim["slides_sugeridos"] = [
        {k: sl.get(k) for k in ("slide", "tipo", "texto")}
        for sl in ideia.get("slides_sugeridos") or []
    ]
    return f"Carrossel:\n{json.dumps(slim, ensure_ascii=False)}"


def gerar_prompts_ideia(
    ideia: dict,
    forcar: bool = False,
    avisos: list | None = None,
    corrigidos: list | None = None,
) -> dict | None:
    """Gera prompts de imagem para UMA ideia. Retorna dict ou None.

    forcar=True invalida o cache de sessão antes — cada clique do usuário
    gera um lote novo (mesmo comportamento da aba Ideias, M6).

    Ordem: bruto → validate_prompts → _enforce_foto_real → validate de novo.
    `avisos` (out-collector) recebe os avisos finais; `corrigidos` recebe o
    que o pós-processamento resolveu — assim o pós-processamento deixa de
    corrigir às cegas atrás do validador (E3 do MELHORIAS.md).

    Com FLOW_FOTOS=true as fotos do catálogo (refs/) são anexadas ao Gemini;
    no padrão (false) a geração é só texto.
    """
    ctx = _ctx_ideia(ideia)
    imagens = anexos_gemini() if FLOW_FOTOS else None
    if imagens:
        logger.info("FLOW_FOTOS ativo: anexando %d fotos do catálogo", len(imagens))
    if forcar:
        invalidate_cache(PROMPT_PROMPTS_IMAGEM, ctx, images=imagens)
    dados = call_gemini_json(
        PROMPT_PROMPTS_IMAGEM,
        ctx,
        temperature=TEMPERATURAS["prompts_imagem"],
        images=imagens,
    )
    if dados:
        avisos_bruto = validate_prompts(dados, ideia)
        dados = _enforce_foto_real(dados, corrigidos=corrigidos)
        avisos_finais = validate_prompts(dados, ideia)
        if avisos is not None:
            avisos.extend(avisos_finais)
        if corrigidos is not None and len(avisos_bruto) > len(avisos_finais):
            corrigidos.append(
                f"{len(avisos_bruto) - len(avisos_finais)} aviso(s) do Gemini resolvidos no pós-processamento"
            )
    return dados


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
      "prompts_{idx}": {"titulo": ..., "prompts": ..., "avisos": [...], "corrigidos": [...]},
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
            avisos: list = []
            corrigidos: list = []
            dados = gerar_prompts_ideia(ideia, forcar=forcar, avisos=avisos, corrigidos=corrigidos)
            if dados:
                results[f"prompts_{idx}"] = {
                    "titulo": titulo,
                    "prompts": dados,
                    "ideia": ideia,
                    "avisos": avisos,
                    "corrigidos": corrigidos,
                }

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
