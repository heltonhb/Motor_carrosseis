"""
acervo.py — Nível 7 do motor: o processo aprende com o que foi aprovado.

O acervo guarda carrosséis **publicados e com métrica no alvo**, destilados em
DNA (estrutura, recursos, paleta, tipografia). É esse DNA que entra no prompt
das gerações seguintes, para o feed não nascer com cara de template.

Duas regras que sustentam o resto do módulo:

1. **Promoção é por mérito, não por sorte.** Entra no acervo a ideia marcada
   como `publicado` cuja taxa de salvamento atinge o alvo do eixo. Promoção
   manual existe (o `forcar=True`), mas é a exceção, não o caminho normal.
2. **O DNA é descrição, não cópia.** Guardamos estrutura e linguagem visual,
   nunca o texto dos slides. Acervo que guarda conteúdo envelhece junto com o
   post e vira ruído.
"""

import re
import unicodedata
from datetime import datetime

from config import EIXOS, KPIS
from persistence import load_acervo, load_ideias_estado, load_metricas, save_acervo

# Paleta da peça — padroesVisuais.txt / PROMPT_PROMPTS_IMAGEM. Este é o recorte
# válido; hex fora daqui é o bug de paleta que o validador já sinaliza.
HEXES_DA_MARCA = {
    "#007799", "#0084B4", "#58B947", "#F58220", "#FFC20E",
    "#E0F2FE", "#FFE4E6", "#FFEDD5", "#ECFCCB", "#F7F9FF", "#EEF4FF", "#1E293B",
}

_FAMILIAS_TIPOGRAFIA = {
    "poppins": "geometric sans",
    "jakarta": "geometric sans",
    "montserrat": "geometric sans",
    "nunito": "geometric sans arredondada",
    "inter": "sans neutra",
}


# ─── Utilidades ──────────────────────────────────────────────────────────────

def slugify(texto: str, maxlen: int = 60) -> str:
    """Normaliza um título em slug estável para nome de arquivo."""
    base = unicodedata.normalize("NFKD", texto or "")
    base = base.encode("ascii", "ignore").decode("ascii").lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return (base[:maxlen].strip("-") or "carrossel")


def alvo_do_eixo(eixo: str) -> float | None:
    """
    Extrai a taxa-alvo de salvamento do eixo, em %.

    A fonte é `config.EIXOS[eixo]["kpi"]` ("Salvamentos ≥ 4,0%"). Parsear a
    string em vez de duplicar o número aqui evita que o alvo do prompt e o alvo
    do acervo se separem — e eles precisam concordar.

    O portão do acervo é SEMPRE taxa de salvamento, nos três eixos. O eixo
    Diagnóstico tem KPI próprio de leads ("Leads WhatsApp 15-25/semana"), que
    não é uma porcentagem — nesse caso vale o alvo global de salvamentos.
    Salvamento é a métrica que existe para os três eixos e é a que mede
    "esse conteúdo vale guardar".
    """
    kpi = EIXOS.get(eixo or "", {}).get("kpi", "")
    achado = re.search(r"(\d+(?:[.,]\d+)?)\s*%", kpi)
    if achado:
        return float(achado.group(1).replace(",", "."))
    return KPIS.get("salvamentos_pct")


def _metrica_da_ideia(titulo: str, metricas: list[dict]) -> dict | None:
    """Procura a métrica que corresponde ao título do post. A mais recente vence."""
    alvo = (titulo or "").strip().lower()
    if not alvo:
        return None
    candidatas = [
        m for m in metricas
        if (m.get("titulo") or "").strip().lower() == alvo and m.get("alcance", 0) > 0
    ]
    if not candidatas:
        return None
    return sorted(candidatas, key=lambda m: m.get("data", ""), reverse=True)[0]


# ─── DNA ─────────────────────────────────────────────────────────────────────

def extrair_dna(ideia: dict, prompts: dict | None = None) -> dict:
    """
    Destila um carrossel em DNA reaproveitável.

    Tudo aqui é determinístico: sai do payload que o Gemini já devolveu, sem
    chamada extra. Chamar o modelo para "resumir o estilo" custaria uma ida à
    API por carrossel para descobrir algo que o payload já diz.
    """
    prompts = prompts or {}
    slides = _slides(prompts)

    estrutura: list[str] = []
    for s in slides:
        tipo = (s.get("tipo") or "").strip()
        if tipo and tipo not in estrutura:
            estrutura.append(tipo)

    recursos: list[str] = []
    for s in slides:
        numero = s.get("slide")
        if s.get("usa_foto_real"):
            recursos.append(f"foto_real_slide_{numero}")
        for chave in s.get("referencias") or []:
            tag = f"referencia:{chave}"
            if tag not in recursos:
                recursos.append(tag)

    paleta: list[str] = []
    tipografia: list[str] = []
    for s in slides:
        texto = s.get("prompt_en") or s.get("prompt") or ""
        for hexa in re.findall(r"#[0-9A-Fa-f]{6}", texto):
            alvo = hexa.upper()
            if alvo in HEXES_DA_MARCA and alvo not in paleta:
                paleta.append(alvo)
        baixo = texto.lower()
        for familia, nome in _FAMILIAS_TIPOGRAFIA.items():
            if familia in baixo and nome not in tipografia:
                tipografia.append(nome)

    return {
        "estrutura": estrutura,
        "recursos": recursos,
        "paleta": paleta[:6],
        "tipografia": tipografia[:2] or ["geometric sans"],
        "ritmo": {
            "modo": "png",
            "observacao": "preencher quando o carrossel vivo (V9) existir",
        },
        "hook": (ideia.get("tipo_hook") or "").strip(),
    }


def _slides(prompts: dict) -> list[dict]:
    """Normaliza o payload de prompts em lista de slides."""
    if isinstance(prompts, list):
        return [s for s in prompts if isinstance(s, dict)]
    if isinstance(prompts, dict):
        for chave in ("slides", "prompts_slides"):
            if isinstance(prompts.get(chave), list):
                return [s for s in prompts[chave] if isinstance(s, dict)]
    return []


# ─── Promoção ────────────────────────────────────────────────────────────────

def avaliar_promocao(
    ideia: dict,
    metricas: list[dict] | None = None,
    estados: dict | None = None,
) -> tuple[bool, str]:
    """
    Decide se a ideia tem direito a entrar no acervo. Devolve (pode, motivo).

    O motivo é sempre preenchido: quem chama mostra o motivo na interface, e
    "não entrou no acervo" sem explicação é a forma mais rápida de o usuário
    parar de confiar na ferramenta.
    """
    if not (ideia or {}).get("titulo"):
        return False, "Ideia sem título não tem o que promover."

    metricas = load_metricas() if metricas is None else metricas
    estados = load_ideias_estado() if estados is None else estados

    ideia_id = ideia.get("id", "")
    status = (estados.get(ideia_id) or {}).get("status", "") if ideia_id else ""
    if status != "publicado":
        return False, (
            f"A ideia está como \"{status or 'sem status'}\". O acervo só recebe "
            "post publicado com métrica no alvo — é isso que separa aprendizado "
            "de sorte."
        )

    metrica = _metrica_da_ideia(ideia.get("titulo", ""), metricas)
    if not metrica:
        return False, (
            "Não há métrica com esse título em metricas.json. Importe o CSV do "
            "Meta Business Suite com o mesmo título do post para o acervo saber "
            "seu desempenho."
        )

    eixo = ideia.get("eixo", "")
    alvo = alvo_do_eixo(eixo)
    taxa = float(metrica.get("taxa_salvamentos") or 0.0)
    if alvo and taxa < alvo:
        return False, (
            f"Taxa de salvamento de {taxa}% abaixo do alvo do eixo {eixo} "
            f"({alvo}%). Abaixo do alvo não é padrão a aprender."
        )

    return True, f"Publicado com {taxa}% de salvamentos (alvo do eixo {eixo}: {alvo}%)."


def promover_para_acervo(
    ideia: dict,
    prompts: dict | None = None,
    metricas: list[dict] | None = None,
    estados: dict | None = None,
    forcar: bool = False,
) -> tuple[dict | None, str]:
    """
    Promove a ideia ao acervo e devolve (registro, motivo).

    forcar=True pula a avaliação de mérito — existe para quando o usuário
    realmente sabe mais que o motor, não para contornar regra.
    """
    pode, motivo = avaliar_promocao(ideia, metricas, estados)
    if not pode and not forcar:
        return None, motivo
    if not pode:
        motivo = f"Promovido manualmente. Motivo da recusa automática: {motivo}"

    metricas = load_metricas() if metricas is None else metricas
    metrica = _metrica_da_ideia(ideia.get("titulo", ""), metricas) or {}

    slug = f"{slugify(ideia.get('titulo', ''))}-{datetime.now().strftime('%Y%m%d')}"
    registro = {
        "slug": slug,
        "titulo": ideia.get("titulo", ""),
        "eixo": ideia.get("eixo", ""),
        "tom": ideia.get("tom", "automatico"),
        "template": ideia.get("template", ""),
        "criado_em": datetime.now().strftime("%Y-%m-%d"),
        "aprovado_em": datetime.now().strftime("%Y-%m-%d"),
        "dna": extrair_dna(ideia, prompts),
        "metricas": {
            "alcance": metrica.get("alcance", 0),
            "taxa_salvamentos": metrica.get("taxa_salvamentos", 0.0),
            "taxa_envios": metrica.get("taxa_envios", 0.0),
            "leads_whatsapp": metrica.get("leads_whatsapp", 0),
        },
    }
    save_acervo(registro)
    return registro, motivo


# ─── Injeção no prompt ───────────────────────────────────────────────────────

def bloco_dna(limite: int = 5) -> str:
    """
    Síntese do acervo para injetar no prompt de imagem.

    Vai os `limite` registros mais recentes, em forma de tags. Injetar o acervo
    inteiro faria o modelo diluir as regras da marca — contexto grande demais
    é a forma mais cara de não ensinar nada.
    """
    registros = load_acervo()[:limite]
    if not registros:
        return ""

    linhas = [
        "\n\n─── \N{HANDSHAKE} O QUE JÁ FUNCIONOU NESTA UNIDADE (REFERÊNCIA DE ESTILO) ───\n",
        "Estes carrosséis foram publicados e bateram a meta de salvamento. Use-os "
        "como referência de estrutura e linguagem visual, nunca para copiar o "
        "conteúdo:\n",
    ]
    for r in registros:
        dna = r.get("dna") or {}
        linhas.append(
            f"  • \"{r.get('titulo', '')}\" (eixo {r.get('eixo', '?')}, "
            f"tom {r.get('tom', '?')}, hook {dna.get('hook') or '—'}): "
            f"estrutura {'/'.join(dna.get('estrutura') or []) or '—'}; "
            f"recursos {', '.join(dna.get('recursos') or []) or '—'}; "
            f"paleta {', '.join(dna.get('paleta') or []) or '—'}\n"
        )
    linhas.append(
        "Mantenha a identidade da Ensina Mais Tatuapé acima: a régua da marca não "
        "cede ao precedente de um post.\n"
    )
    return "".join(linhas)


def resumo_acervo() -> dict:
    """Números do acervo para exibir na interface."""
    registros = load_acervo()
    com_metrica = [r for r in registros if (r.get("metricas") or {}).get("alcance")]
    taxas = [
        float((r.get("metricas") or {}).get("taxa_salvamentos") or 0)
        for r in com_metrica
    ]
    return {
        "total": len(registros),
        "com_metrica": len(com_metrica),
        "taxa_media": round(sum(taxas) / len(taxas), 1) if taxas else 0.0,
        "ultimo": registros[0].get("titulo", "") if registros else "",
    }
