"""
parser_nlm.py — Unificado de parsing JSON para NotebookLM e Gemini.
Centraliza todas as estratégias de extração de JSON.
"""

import json
import re


def _clean_json_string(text: str) -> str:
    """Remove ruídos comuns de strings JSON (vírgulas extras, etc.)."""
    # Remove vírgulas antes de chaves/colchetes fechantes
    text = re.sub(r",\s*([\]}])", r"\1", text)
    # Remove vírgulas no final de arrays/objects
    text = re.sub(r",\s*([\]}])", r"\1", text)
    # Remove múltiplos espaços
    text = re.sub(r"\s+", " ", text)
    return text


def _resolve_envelope(d: dict) -> dict:
    """Se for envelope do CLI NotebookLM com campo 'answer', tenta extrair o JSON interno."""
    if not isinstance(d, dict):
        return {}
    if "answer" in d and not any(k in d for k in ("ideias", "tendencias", "concorrentes", "oportunidades", "dores_pais")):
        inner = d["answer"]
        if isinstance(inner, str):
            inner_json = extract_json(inner)
            if inner_json:
                return inner_json
    return d


def extract_json(text: str) -> dict:
    """
    Extrai um objeto JSON de uma resposta de texto (Gemini ou NotebookLM).
    Tenta múltiplas estratégias com tolerância a ruídos de formatação.
    """
    if not text:
        return {}

    # Estratégia 1: bloco de código markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        try:
            return _resolve_envelope(json.loads(content))
        except json.JSONDecodeError:
            try:
                return _resolve_envelope(json.loads(_clean_json_string(content)))
            except json.JSONDecodeError:
                pass

    # Estratégia 2: do primeiro '{' ao último '}'
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        content = text[start : end + 1].strip()
        try:
            return _resolve_envelope(json.loads(content))
        except json.JSONDecodeError:
            try:
                return _resolve_envelope(json.loads(_clean_json_string(content)))
            except json.JSONDecodeError:
                pass

    # Estratégia 3: parse direto do texto inteiro
    try:
        return _resolve_envelope(json.loads(text.strip()))
    except json.JSONDecodeError:
        try:
            return _resolve_envelope(json.loads(_clean_json_string(text.strip())))
        except json.JSONDecodeError:
            return {}


_GUIDELINE_NOISE_PHRASES = (
    "portfolio estrito",
    "zero menção",
    "zero mencao",
    "ineditismo total",
    "ancoragem local",
    "call to action direto",
    "diretrizes estratégicas",
    "checklist de diversidade",
    "requisitos obrigatórios",
    "cursos oficiais",
    "do carrossel",
    "estrutura de saída",
    "formato padrão",
)


def is_guideline_noise(text: str) -> bool:
    """Retorna True se o texto for ruído de diretrizes/metadados em vez de ideia substantiva."""
    if not text or not isinstance(text, str):
        return True
    t = text.strip().lower()
    return any(p in t for p in _GUIDELINE_NOISE_PHRASES)


def _normalizar_eixo(eixo_raw: str, idx: int = 0) -> str:
    low = (eixo_raw or "").lower()
    if "didátic" in low or "didatic" in low or "prátic" in low:
        return "Didático"
    if "comportament" in low or "emocional" in low:
        return "Comportamental"
    if "diagnóstic" in low or "diagnostic" in low or "avalia" in low:
        return "Diagnóstico"
    return "Didático" if idx % 3 == 0 else "Comportamental" if idx % 3 == 1 else "Diagnóstico"


def _normalizar_curso(curso_raw: str) -> str:
    low = (curso_raw or "").lower()
    if "portugu" in low or "reda" in low or "leitura" in low:
        return "Apoio Escolar — Português (Ensino Fundamental)"
    if "matem" in low or "cálcul" in low or "geometr" in low:
        return "Apoio Escolar — Matemática (Ensino Fundamental)"
    if "robót" in low or "robot" in low or "steam" in low:
        return "Tecnologia — Robótica"
    if "program" in low or "scratch" in low or "código" in low:
        return "Tecnologia — Programação"
    return "Apoio Escolar — Matemática (Ensino Fundamental)"


def _gerar_slides_padrao(titulo: str, cta: str, curso: str) -> list[dict]:
    curso_lower = (curso or "").lower()
    is_tecnologia = any(k in curso_lower for k in ("robót", "robot", "prog", "tecnol", "games", "cód", "cod"))
    oferta = "uma aula experimental gratuita" if is_tecnologia else "uma avaliação pedagógica gratuita"
    return [
        {"slide": 1, "tipo": "Capa", "texto": titulo},
        {"slide": 2, "tipo": "Segunda Capa", "texto": "A dor silenciosa que afeta as notas e o rendimento escolar no dia a dia."},
        {"slide": 3, "tipo": "Problema", "texto": "Por que a abordagem tradicional de estudo em casa desgasta pais e alunos."},
        {"slide": 4, "tipo": "Entrega / Diagnóstico", "texto": "Como identificar a lacuna de aprendizado antes que ela vire nota baixa nas provas."},
        {"slide": 5, "tipo": "Passo Prático", "texto": "A técnica de desconstrução pedagógica para destravar a autonomia da criança."},
        {"slide": 6, "tipo": "Ponte", "texto": f"Na Ensina Mais Tatuapé, o método individualizado de {curso} transforma essa dificuldade em segurança."},
        {"slide": 7, "tipo": "Prova", "texto": "Alunos com acompanhamento direcionado recuperam a confiança e elevam a média escolar já no primeiro bimestre."},
        {"slide": 8, "tipo": "CTA", "texto": f'Comente "{cta}" ou chame no WhatsApp (11) 94475-0009 para agendar {oferta} no Tatuapé.'},
    ]


def extract_ideas_from_text(text: str) -> list[dict]:
    """
    Extrai ideias de carrossel de respostas do NotebookLM ou Gemini.
    Suporta tanto JSON (mesmo aninhado no envelope CLI) quanto Markdown estruturado.
    Filtra estritamente ruídos de diretrizes ('Portfolio Estrito', 'Zero Menção', etc.).
    Garante que cada ideia possua 8 slides canônicos estruturados.
    """
    if not text or not isinstance(text, str):
        return []

    # 1. Tenta extrair JSON
    data = extract_json(text)
    if isinstance(data, dict):
        ideias_raw = data.get("ideias")
        if isinstance(ideias_raw, list) and ideias_raw:
            validadas = []
            for item in ideias_raw:
                if isinstance(item, dict):
                    tit = item.get("titulo", "")
                    if not is_guideline_noise(tit):
                        validadas.append(item)
            if len(validadas) >= 2:
                for idx, v in enumerate(validadas):
                    if not v.get("curso"):
                        v["curso"] = _normalizar_curso(v.get("tema", "") + " " + v.get("titulo", ""))
                    if not v.get("eixo"):
                        v["eixo"] = _normalizar_eixo(v.get("tema", ""), idx)
                    if not v.get("cta"):
                        v["cta"] = "DESAFIO"
                    slides = v.get("slides_sugeridos", [])
                    if len(slides) < 7:
                        v["slides_sugeridos"] = _gerar_slides_padrao(
                            v.get("titulo", ""), v.get("cta", "DESAFIO"), v.get("curso", "")
                        )
                return validadas

    # 2. Extração via Markdown estruturado
    # O NotebookLM frequentemente responde com blocos do tipo:
    # ### 💡 IDEIA 1: [Título]
    # * **Eixo Temático**: [Eixo]
    # * **Curso Oficial**: [Curso]
    # * **Palavra-chave (CTA)**: `CTA`
    # #### Estrutura dos Slides:
    # 1. **Capa**: [Texto] ...
    
    # Remover preâmbulo (tudo antes da primeira menção a IDEIA X ou Carrossel X)
    m_start = re.search(r"(?:###|##|\*\*)\s*(?:[💡🔍🎯⚡📌]?\s*)?(?:Ideia|Carrossel)\s*\d+", text, re.IGNORECASE)
    text_body = text[m_start.start():] if m_start else text

    pat_blocos = r"(?:###|##|\*\*)\s*(?:[💡🔍🎯⚡📌]?\s*)?(?:Ideia|Carrossel)\s*(\d+)[:\s\-]+([^\n*]+)(.*?)(?=(?:###|##|\*\*)\s*(?:[💡🔍🎯⚡📌]?\s*)?(?:Ideia|Carrossel)\s*\d+[:\s\-]|\Z)"
    matches = list(re.finditer(pat_blocos, text_body, re.DOTALL | re.IGNORECASE))
    
    ideias_extraidas = []
    for idx, m in enumerate(matches):
        _, tit_raw, corpo = m.groups()
        titulo = tit_raw.strip().strip('"').strip("'").strip("*").strip()
        titulo = re.sub(r"^[:\-\s]+", "", titulo).strip()
        titulo = re.sub(r"\[\d+(?:[,\-\s]+\d+)*\]", "", titulo).strip()

        if is_guideline_noise(titulo):
            continue

        eixo_m = re.search(r"Eixo(?:\s+Temático)?\s*[\*:]+\s*([^\n*]+)", corpo, re.I)
        eixo = _normalizar_eixo(eixo_m.group(1).strip() if eixo_m else "", idx)

        curso_m = re.search(r"Curso(?:\s+Oficial)?\s*[\*:]+\s*([^\n*]+)", corpo, re.I)
        curso = _normalizar_curso(curso_m.group(1).strip() if curso_m else titulo)

        cta_m = re.search(r"(?:CTA|Palavra-chave(?:\s*\(CTA\))?)\s*[\*:]+\s*[`\"'\s]*([A-Za-z0-9_À-ÿ]+)", corpo, re.I)
        cta = cta_m.group(1).strip().upper() if cta_m else ("DESAFIO" if idx % 2 == 0 else "AVALIAR")

        just_m = re.search(r"Justificativa(?:\s+Estratégica)?\s*[\*:]+\s*([^\n*]+)", corpo, re.I)
        justificativa = just_m.group(1).strip() if just_m else "Baseado em evidências e necessidades reais de famílias do Tatuapé"
        justificativa = re.sub(r"\[\d+(?:[,\-\s]+\d+)*\]", "", justificativa).strip()

        fonte_m = re.search(r"Fonte(?:\s+Notebook)?\s*[\*:]+\s*([^\n*]+)", corpo, re.I)
        fonte = fonte_m.group(1).strip() if fonte_m else "Estratégia Ensina Mais Tatuapé"

        # Extrair slides estruturados
        slides_matches = re.findall(
            r"(?:(?:Slide\s*(\d+)[:\-]|\b(\d+)\.)\s*(?:\*\*([^*]+)\*\*:?|([A-Za-zÀ-ÿ\s]+):))\s*([^\n]+)",
            corpo,
            re.IGNORECASE
        )
        slides = []
        if slides_matches:
            for s in slides_matches:
                s_num = int(s[0] or s[1]) if (s[0] or s[1]) else len(slides) + 1
                s_tipo = (s[2] or s[3]).strip().strip("*").strip(":")
                s_txt = s[4].strip()
                s_txt = re.sub(r"\[\d+(?:[,\-\s]+\d+)*\]", "", s_txt).strip()
                if not is_guideline_noise(s_tipo) and len(s_txt) > 3:
                    slides.append({"slide": s_num, "tipo": s_tipo, "texto": s_txt})

        if len(slides) < 7:
            capa_txt = slides[0]["texto"] if slides else titulo
            curso_lower = (curso or "").lower()
            is_tecnologia = any(k in curso_lower for k in ("robót", "robot", "prog", "tecnol", "games", "cód", "cod"))
            oferta = "uma aula experimental gratuita" if is_tecnologia else "uma avaliação pedagógica gratuita"
            cta_txt = slides[-1]["texto"] if len(slides) > 1 and "cta" in slides[-1]["tipo"].lower() else f'Comente "{cta}" ou chame no WhatsApp (11) 94475-0009 para agendar {oferta} no Tatuapé.'
            slides_completos = _gerar_slides_padrao(capa_txt, cta, curso)
            slides_completos[0]["texto"] = capa_txt
            slides_completos[-1]["texto"] = cta_txt
            slides = slides_completos

        ideias_extraidas.append({
            "titulo": titulo,
            "eixo": eixo,
            "curso": curso,
            "tema": titulo,
            "publico_alvo": "Pais de classes A/B do Tatuapé",
            "palavras_chave_seo": ["apoio escolar Tatuapé", "reforço escolar Tatuapé"],
            "cta": cta,
            "slides_sugeridos": slides[:8],
            "kpi_alvo": "Salvamentos/Envios/Leads",
            "justificativa": justificativa,
            "fonte_notebook": fonte,
        })

    return ideias_extraidas


def extract_json_list(text: str) -> list:
    """
    Extrai uma lista JSON (array) de uma resposta de texto.
    """
    if not text:
        return []

    # Estratégia 1: bloco de código markdown ```json ... ```
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        content = match.group(1).strip()
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            try:
                data = json.loads(_clean_json_string(content))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

    # Estratégia 2: do primeiro '[' ao último ']'
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        content = text[start : end + 1].strip()
        try:
            data = json.loads(content)
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            try:
                data = json.loads(_clean_json_string(content))
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

    return []
