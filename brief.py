"""
brief.py — V8: o contrato entre a ideia, a imagem e a animação.

O brief responde às lacunas que o modelo deixaria em aberto (para quem, com que
objetivo, em que voz, com que aparência). O storyboard é o mesmo contrato visto
no tempo: cada slide com papel, duração, movimento e cue de áudio.

Dois princípios:

1. **Montagem determinística.** O brief nasce da ideia, do template do eixo e da
   config — sem chamar o Gemini. Ele organiza o que o motor já sabe, então uma
   ida à API aqui seria custo sem informação nova.
2. **Tempo fechado no storyboard, não no renderer.** A duração de cada slide é
   ajustada aqui até `frames_do_slide % frames_do_beat == 0`. Arredondar na hora
   de renderizar é como a trilha e o efeito deixam de bater.

O modo "vivo" ainda não renderiza nada (V9). O que existe aqui é o contrato que
o renderer vai consumir — e ele já é validado por teste.
"""

import re

from config import EIXOS, FORMATO, TONES_PADRAO, UNIDADE
from prompts import FIDELIDADES, resolver_fidelidade, resolver_tom
from refs_catalog import cena_valida, chaves_cenas
from templates import TEMPLATES, eixo_para_template

# ─── Parâmetros de render ────────────────────────────────────────────────────
FPS = 30

# Mood por eixo. As durações e os BPM vêm da tabela verificada em
# .claude/skills/carrossel-vivo/references/motion.md — beat inteiro em frames é
# o que garante a sincronia.
MOODS: dict[str, dict] = {
    "didatico_energetico": {
        "bpm": 120, "duracao_s": 3.0, "curva": "ease_out_cubic",
        "intensidade": "alta", "eixo": "Didático",
    },
    "urbano": {
        "bpm": 100, "duracao_s": 3.0, "curva": "ease_out_quart",
        "intensidade": "alta", "eixo": "Diagnóstico",
    },
    "intimista": {
        "bpm": 60, "duracao_s": 4.0, "curva": "ease_in_out_quad",
        "intensidade": "baixa", "eixo": "Comportamental",
    },
    "frio": {
        "bpm": 120, "duracao_s": 2.5, "curva": "linear",
        "intensidade": "baixa", "eixo": "Diagnóstico",
    },
}

MOOD_PADRAO_POR_EIXO = {
    "Didático": "didatico_energetico",
    "Comportamental": "intimista",
    "Diagnóstico": "urbano",
}

# Movimento por papel do slide. Slide de leitura pede movimento contido: quem
# está lendo não quer a cena se mexendo por baixo.
MOVIMENTO_POR_TIPO: dict[str, dict] = {
    "Capa":         {"entrada": "fade_subida", "movimento": "ken_burns", "intensidade": 0.06},
    "Segunda Capa": {"entrada": "slide_esquerda", "movimento": "ken_burns", "intensidade": 0.05},
    "Entrega":      {"entrada": "fade_subida", "movimento": "estatico", "intensidade": 0.0},
    "Ponte":        {"entrada": "fade_subida", "movimento": "ken_burns", "intensidade": 0.04},
    "Prova":        {"entrada": "fade", "movimento": "estatico", "intensidade": 0.0},
    "CTA":          {"entrada": "zoom_saia", "movimento": "ken_burns", "intensidade": 0.05},
}

CUE_POR_TIPO = {
    "Capa": "impacto",
    "Segunda Capa": "impacto",
    "Entrega": "click",
    "Ponte": "pad",
    "Prova": "pad",
    "CTA": "impacto",
}

# Texto sobreposto no slide: o roteiro tem 30-50 palavras, o overlay tem muito
# menos. É o que o pai lê no celular em meio segundo.
MAX_PALAVRAS_OVERLAY = 15
MAX_PALAVRAS_OVERLAY_THUMB = 8  # slides 1, 4 e 5


# ─── Brief ───────────────────────────────────────────────────────────────────

def montar_brief(
    ideia: dict,
    tom: str | None = None,
    fidelidade: str | None = None,
    referencias: list[str] | None = None,
    modo: str = "png",
    restricoes: list[str] | None = None,
) -> dict:
    """
    Monta o brief a partir da ideia selecionada.

    Tudo que é invariável do motor (palavra-chave do CTA, WhatsApp, tamanho do
    slide, referências obrigatórias) entra aqui por conta própria — o usuário não
    precisa preenchê-los e não pode quebrá-los.
    """
    ideia = ideia or {}
    eixo = ideia.get("eixo", "Didático")
    if eixo not in EIXOS:
        eixo = "Didático"

    tkey = eixo_para_template(eixo)
    template = TEMPLATES.get(tkey, {})

    if referencias is None:
        # As referências que o próprio template já exige (fachada no 7, cena de
        # atividade nos demais) são o mínimo; a ideia pode querer mais.
        referencias = _referencias_do_template(tkey)

    tom_efetivo = resolver_tom(tom, eixo)
    fid_efetiva, avisos_fid = resolver_fidelidade(fidelidade, tem_imagem=False)

    brief = {
        "tema": ideia.get("tema") or ideia.get("titulo", ""),
        "titulo": ideia.get("titulo", ""),
        "ideia_id": ideia.get("id", ""),
        "eixo": eixo,
        "template": tkey,
        "publico_alvo": ideia.get("publico_alvo") or UNIDADE["publico"],
        "persona_alvo": ideia.get("persona_alvo", ""),
        "tipo_hook": ideia.get("tipo_hook", ""),
        "objetivo": EIXOS.get(eixo, {}).get("meta", "salvamentos"),
        "kpi_alvo": EIXOS.get(eixo, {}).get("kpi", ""),
        "tom": tom_efetivo,
        "tom_solicitado": tom or TONES_PADRAO,
        "cta": {
            "palavra_chave": template.get("cta_padrao", "DESAFIO"),
            "canal": "whatsapp",
            "telefone": UNIDADE["whatsapp"],
        },
        "formato": {
            "largura": FORMATO["largura"],
            "altura": FORMATO["altura"],
            "proporcao": FORMATO["proporcao"],
        },
        "roteiro": _roteiro(ideia, template),
        "num_slides": len(ideia.get("slides_sugeridos") or template.get("estrutura") or []),
        "referencias": list(referencias),
        "fidelidade": fid_efetiva,
        "modo": modo if modo in {"png", "vivo"} else "png",
        "trilha": _trilha(eixo, modo),
        "restricoes": list(restricoes or _RESTRICOES_BASE),
        "avisos": avisos_fid,
    }
    return brief


_RESTRICOES_BASE = [
    "não gerar personagens da Turma da Mônica",
    "não citar concorrente pelo nome",
    "nenhum número sem fonte real",
    "palavra-chave e WhatsApp exatamente como no motor",
]


def _roteiro(ideia: dict, template: dict) -> list[dict]:
    """
    Roteiro do carrossel: o da ideia quando existe, senão a estrutura do template.

    O storyboard usa isto para o texto do overlay. Um overlay cortado no meio da
    frase porque o roteiro sumiu é pior que nenhum overlay.
    """
    slides = ideia.get("slides_sugeridos") or []
    if slides:
        return [
            {"slide": s.get("slide", i), "tipo": s.get("tipo", "Entrega"), "texto": s.get("texto", "")}
            for i, s in enumerate(slides, start=1)
            if isinstance(s, dict)
        ]
    return [
        {"slide": s.slide, "tipo": s.tipo, "texto": s.texto}
        for s in template.get("estrutura", [])
    ]


def _referencias_do_template(tkey: str) -> list[str]:
    """Chaves de cena que o template exige, sem repetir."""
    chaves: list[str] = []
    for slide in TEMPLATES.get(tkey, {}).get("estrutura", []):
        chave = slide.tipo_foto
        if chave and chave not in chaves:
            chaves.append(chave)
    return chaves


def _trilha(eixo: str, modo: str) -> dict:
    """Mood da trilha derivado do eixo. Em modo png fica declarada e inerte."""
    nome = MOOD_PADRAO_POR_EIXO.get(eixo, "didatico_energetico")
    mood = MOODS[nome]
    return {
        "mood": nome,
        "bpm": mood["bpm"],
        "duracao_s": mood["duracao_s"],
        "curva": mood["curva"],
        "intensidade": mood["intensidade"],
        "ativa": modo == "vivo",
    }


def validar_brief(brief: dict) -> list[str]:
    """
    Devolve a lista de problemas do brief (vazia = brief pronto).

    Valida o que o motor consegue garantir por conta própria: faixa de slides,
    chave de referência do catálogo, palavra-chave do eixo, tom e fidelidade
    existentes. Erro aqui é erro de interface, não do conteúdo.
    """
    avisos: list[str] = []
    if not brief:
        return ["Brief vazio."]

    eixo = brief.get("eixo", "")
    if eixo not in EIXOS:
        avisos.append(f"Eixo \"{eixo}\" não existe — esperado um de {list(EIXOS)}.")
    else:
        esperado = TEMPLATES.get(eixo_para_template(eixo), {}).get("cta_padrao")
        if brief.get("cta", {}).get("palavra_chave") != esperado:
            avisos.append(
                f"Palavra-chave do CTA não bate com o template do eixo {eixo} "
                f"(esperado \"{esperado}\")."
            )

    num = brief.get("num_slides", 0)
    if not (FORMATO["slides_min"] <= num <= FORMATO["slides_max"]):
        avisos.append(
            f"{num} slides — o padrão do motor é {FORMATO['slides_min']} a "
            f"{FORMATO['slides_max']}."
        )

    validas = set(chaves_cenas())
    for chave in brief.get("referencias", []):
        if chave not in validas and not cena_valida(chave):
            avisos.append(
                f"Referência \"{chave}\" não existe no catálogo de fotos. "
                f"Válidas: {', '.join(sorted(validas))}."
            )

    if brief.get("fidelidade") not in FIDELIDADES:
        avisos.append(f"Fidelidade \"{brief.get('fidelidade')}\" não existe.")
    if brief.get("modo") not in {"png", "vivo"}:
        avisos.append(f"Modo \"{brief.get('modo')}\" inválido — use png ou vivo.")

    return avisos


# ─── Storyboard ──────────────────────────────────────────────────────────────

def montar_storyboard(
    brief: dict,
    prompts: dict | None = None,
    texto_na_imagem: bool = True,
) -> dict:
    """
    Monta o storyboard no tempo: papel, duração, movimento e cue por slide.

    A duração de cada slide é ajustada em passos de 1 frame até fechar na grade
    de beats. Isso é o que separa "o efeito cai no segundo certo" de "quase
    certo" — e é verificável em teste, antes do renderer existir.
    """
    bpm = int(brief.get("trilha", {}).get("bpm") or 120)
    frames_beat = int(round(1800 / bpm))
    avisos: list[str] = []

    base = _slides_base(brief, prompts)
    for item in base:
        item["texto_na_imagem"] = texto_na_imagem
    slides: list[dict] = []
    tempo_acumulado = 0.0

    for indice, item in enumerate(base, start=1):
        tipo = item["tipo"]
        movimento = MOVIMENTO_POR_TIPO.get(tipo, MOVIMENTO_POR_TIPO["Entrega"])

        frames, duracao, ajuste = _encaixar_frames(
            item.get("duracao_s") or brief["trilha"]["duracao_s"],
            frames_beat,
            indice,
        )
        if ajuste:
            avisos.append(
                f"Slide {indice}: {ajuste} — duração ajustada para {duracao:.3f}s "
                f"({frames} frames) para fechar na grade de {bpm} bpm."
            )

        cue = CUE_POR_TIPO.get(tipo, "pad")
        cue_frames = tempo_acumulado * FPS
        # O cue cai no beat mais próximo do início do slide; o olho não percebe
        # meio beat de diferença, mas um beat fora do lugar denuncia dessincronia.
        k = round(cue_frames / frames_beat) if frames_beat else 0
        cue_tempo = round(k * frames_beat / FPS, 3)

        overlay, corte = _texto_overlay(item.get("texto", ""), indice)

        slides.append({
            "slide": indice,
            # A arte do Google Flow já recebe o texto sobreposto (regra 8 dos
            # prompts de imagem). Redesenhar por cima duplica a frase — e o
            # storyboard precisa dizer isso explicitamente, porque o renderer
            # não tem como deduzir de um PNG.
            "texto_na_imagem": bool(item.get("texto_na_imagem", True)),
            "tipo": tipo,
            "papel": _papel(tipo, indice),
            "texto": item.get("texto", ""),
            "texto_overlay": overlay,
            "overlay_cortado": corte,
            "imagem": {
                "origem": f"refs:{item['referencia']}" if item.get("referencia") else "template",
                "fidelidade": brief.get("fidelidade", "media"),
            },
            "animacao": {
                "duracao_s": round(duracao, 3),
                "frames": frames,
                "entrada": {"tipo": movimento["entrada"], "duracao_ms": 400},
                "movimento": {
                    "tipo": movimento["movimento"],
                    "intensidade": movimento["intensidade"],
                },
                "saida": {"tipo": "corte_seco"},
            },
            "audio": {"cue": cue, "tempo_s": cue_tempo, "intensidade": 1.0},
        })
        tempo_acumulado += duracao

    total_frames = sum(s["animacao"]["frames"] for s in slides)
    storyboard = {
        "modo": brief.get("modo", "png"),
        "fps": FPS,
        "bpm": bpm,
        "frames_beat": frames_beat,
        "duracao_total_s": round(total_frames / FPS, 3),
        "total_frames": total_frames,
        "tempo_audio_s": round(1.0 / (bpm / 60.0) * round(total_frames / frames_beat), 3),
        "slides": slides,
        "avisos": avisos,
    }
    avisos.extend(validar_storyboard(storyboard))
    storyboard["avisos"] = avisos
    return storyboard


def _encaixar_frames(duracao_s: float, frames_beat: int, indice: int) -> tuple[int, float, str]:
    """Ajusta a duração, em passos de 1 frame, até fechar na grade de beats."""
    frames = max(1, round(duracao_s * FPS))
    ajuste = ""
    if frames % frames_beat != 0:
        # Procura o múltiplo de beat mais próximo, sem sair da faixa de leitura.
        alvo = frames_beat * max(1, round(frames / frames_beat))
        if alvo < round(2.0 * FPS):
            alvo = frames_beat
        if alvo > round(4.5 * FPS):
            alvo = frames_beat * max(1, round(4.5 * FPS / frames_beat))
        ajuste = f"duração {duracao_s:.2f}s não fecha em beats de {frames_beat} frames"
        frames = int(alvo)
    return int(frames), frames / FPS, ajuste


def _slides_base(brief: dict, prompts: dict | None) -> list[dict]:
    """Une a estrutura do template, o roteiro da ideia e os prompts gerados."""
    template = TEMPLATES.get(brief.get("template", ""), {})
    por_numero = {s.slide: s for s in template.get("estrutura", [])}
    roteiro = {r.get("slide"): r for r in brief.get("roteiro", []) if isinstance(r, dict)}

    itens: list[dict] = []
    slides_prompts = _slides_do_prompt(prompts)

    total = brief.get("num_slides") or len(por_numero) or 8
    for numero in range(1, total + 1):
        base = por_numero.get(numero)
        prompt = slides_prompts.get(numero, {})
        linha = roteiro.get(numero, {})
        itens.append({
            "numero": numero,
            "tipo": (prompt.get("tipo") or linha.get("tipo") or (base.tipo if base else "Entrega")),
            "texto": (prompt.get("texto") or linha.get("texto") or (base.texto if base else "")),
            "referencia": (
                (prompt.get("referencias") or [None])[0]
                or (base.tipo_foto if base else None)
            ),
            "duracao_s": brief.get("trilha", {}).get("duracao_s"),
        })
    return itens


def _slides_do_prompt(prompts: dict | None) -> dict:
    """Indexa o payload de prompts por número de slide."""
    if isinstance(prompts, list):
        lista = prompts
    elif isinstance(prompts, dict):
        lista = prompts.get("slides") or prompts.get("prompts_slides") or []
    else:
        lista = []
    return {s.get("slide"): s for s in lista if isinstance(s, dict)}


def _papel(tipo: str, indice: int) -> str:
    """Função narrativa do slide dentro deste carrossel."""
    if tipo == "Capa":
        return "interromper o scroll"
    if tipo == "CTA":
        return "converter"
    if tipo == "Prova":
        return "dar credibilidade"
    if tipo == "Ponte":
        return "ligar problema a marca"
    if indice in (4, 5):
        return "entregar o miolo"
    return "entregar o miolo"


def _texto_overlay(texto: str, indice: int) -> tuple[str, bool]:
    """Corta o overlay no limite de palavras do slide. Retorna (texto, cortado)."""
    limite = MAX_PALAVRAS_OVERLAY_THUMB if indice in (1, 4, 5) else MAX_PALAVRAS_OVERLAY
    limpo = re.sub(r"\s+", " ", (texto or "")).strip()
    palavras = limpo.split()
    if len(palavras) <= limite:
        return limpo, False
    return " ".join(palavras[:limite]), True


def validar_storyboard(storyboard: dict) -> list[str]:
    """
    Verifica as invariantes de tempo do vídeo antes de qualquer render.

    As mesmas regras que o renderer vai ter de obedecer, checadas aqui porque
    aqui elas são um teste em vez de um mp4 misterioso.
    """
    avisos: list[str] = []
    if not storyboard or not storyboard.get("slides"):
        return ["Storyboard vazio."]

    fps = storyboard.get("fps", FPS)
    frames_beat = storyboard.get("frames_beat", 0)
    total = 0

    for slide in storyboard.get("slides", []):
        numero = slide.get("slide", "?")
        anim = slide.get("animacao") or {}
        frames = anim.get("frames")
        duracao = anim.get("duracao_s", 0)
        if frames is None:
            avisos.append(f"Slide {numero}: sem contagem de frames.")
            continue
        if abs(duracao * fps - frames) > 0.01:
            avisos.append(
                f"Slide {numero}: {duracao}s não bate com {frames} frames a {fps} fps."
            )
        if frames_beat and frames % frames_beat != 0:
            avisos.append(
                f"Slide {numero}: {frames} frames não fecha na grade de "
                f"{frames_beat} frames/beat — o efeito vai dessincronizar."
            )
        cue = (slide.get("audio") or {}).get("tempo_s")
        if cue is not None and frames_beat:
            if abs(round(cue * fps) % frames_beat) > 0.01:
                avisos.append(f"Slide {numero}: cue em {cue}s está fora do beat.")
        total += frames

    duracao_total = total / fps
    n = len(storyboard.get("slides", []))
    if n and not (20 <= duracao_total <= 32):
        avisos.append(
            f"Duração total de {duracao_total:.1f}s para {n} slides — a faixa que "
            "segura retenção é 20 s a 32 s."
        )
    return avisos


def resumo_storyboard(storyboard: dict) -> dict:
    """Números do storyboard para a interface."""
    slides = (storyboard or {}).get("slides", [])
    movimentos: dict[str, int] = {}
    for s in slides:
        tipo = (s.get("animacao", {}).get("movimento") or {}).get("tipo", "?")
        movimentos[tipo] = movimentos.get(tipo, 0) + 1
    return {
        "slides": len(slides),
        "duracao_total_s": (storyboard or {}).get("duracao_total_s", 0),
        "bpm": (storyboard or {}).get("bpm", 0),
        "movimentos": movimentos,
        "avisos": (storyboard or {}).get("avisos", []),
    }
