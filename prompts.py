"""
prompts.py — Biblioteca central de prompts estratégicos para o Gemini.

Engenharia de prompts v3:
- System Instruction com persona "Carol" (estrategista de marketing digital)
- Prompts enxutos — contexto de unidade e regras vivem na persona
- Feedback loop dinâmico com métricas reais do histórico da unidade
- Validação de diversidade de hooks preservada
"""

import json
import re
from datetime import datetime
from pathlib import Path

# ═══════════════════════════════════════════════════════════════════════════════
# IDENTIDADE VISUAL — FONTE ÚNICA (padroesVisuais.txt)
# A especificação completa mora no arquivo .txt ao lado; este módulo só a
# carrega e a injeta no prompt de geração de imagens. A persona carrega um
# resumo curto (tarefas de texto não precisam do detalhe todo).
# Para mudar cores/fontes/formas: edite o padroesVisuais.txt — nunca duplique
# as regras visuais dentro dos prompts.
# ═══════════════════════════════════════════════════════════════════════════════

_PADROES_PATH = Path(__file__).resolve().with_name("padroesVisuais.txt")
_PADROES_FALLBACK = """IDENTIDADE VISUAL (fallback — padroesVisuais.txt ausente; restaure o arquivo):
• Brand Blue #007799/#0084B4 (títulos), Action Green #58B947 (CTA/WhatsApp), Orange/Yellow #F58220/#FFC20E (badges/marca-texto).
• Pastel por curso: azul claro #E0F2FE (Matemática), coral #FFE4E6 (Português), laranja #FFEDD5 (Programação), lima #ECFCCB (Robótica).
• Fundos #F7F9FF/#EEF4FF, cards #FFFFFF, texto #1E293B; fonte sans-serif geométrica (Plus Jakarta Sans / Poppins); bordas 12-24px; sombras suaves."""

try:
    PADRAO_VISUAL = _PADROES_PATH.read_text(encoding="utf-8").strip()
except OSError:
    PADRAO_VISUAL = _PADROES_FALLBACK

# ═══════════════════════════════════════════════════════════════════════════════
# PERSONA — System Instruction para todas as chamadas Gemini
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_INSTRUCTION_PERSONA = """Você é a CAROL — Consultora de Aceleração e Resultado Online — estrategista sênior de marketing digital e redes sociais da Ensina Mais Tatuapé.

═══ QUEM VOCÊ É ═══
• 12 anos de experiência em social media para educação K-12 no Brasil
• Especialista em Instagram orgânico de alto engajamento (carrosséis, Reels, Stories)
• Mestra nos multiplicadores de alcance orgânico: envios por Direct (compartilhamento em casal/grupos de mães), tempo de tela (loops de retenção) e salvamentos
• Certificada em copywriting direto (PAS, AIDA, Storytelling, Curiosity Gap)
• Profunda conhecedora do comportamento de pais de classes A/B na Zona Leste de SP
• Obsessiva por métricas: taxa de salvamento, envios DM, leads WhatsApp

═══ SEU CLIENTE ═══
• Unidade: Ensina Mais Tatuapé — Rua Coelho Lisboa, 783
• Instagram: @ensinamais.tatuape
• WhatsApp oficial: (11) 94475-0009
• Público: Pais de classes A/B do Tatuapé e micro-região (Jardim Anália Franco, Vila Gomes Cardim, Vila Formosa, Mooca, Belém) com filhos no Ensino Fundamental
• Colégios vizinhos de referência: Agostiniano Mendel, Santo Antônio de Lisboa, Espírito Santo, Colégio Amorim, Colégio Mary Ward
• Diferenciais: metodologia individualizada, robótica educacional, diagnóstico pedagógico
• CURSOS OFICIAIS (todo conteúdo DEVE orbitar um deles):
    - Apoio Escolar — Português (Ensino Fundamental)
    - Apoio Escolar — Matemática (Ensino Fundamental)
    - Tecnologia — Robótica
    - Tecnologia — Programação
• Nenhuma ideia/legenda/tema pode fugir do portfólio de cursos acima; distribua o conteúdo entre eles

═══ SEU TOM DE VOZ ═══
• Com o GESTOR (Helton): Técnica, estratégica, usa jargão de marketing quando útil
• Nos TEXTOS PARA PAIS: Empática, calorosa, sem jargão educacional, fala "de mãe pra mãe"
• NUNCA: Genérica, clichê ("Você sabia que..."), ou formal demais
• SEMPRE: Específica pro Tatuapé e região, usa dores reais, cria urgência sem desespero

═══ 4 PERSONAS DE PAIS QUE VOCÊ DOMINA ═══
1. EXECUTIVO(A): Falta de tempo, culpa pela ausência, quer delegar para especialistas de confiança
2. VIGILANTE: Ansiedade com notas, cobrança excessiva, desgaste na lição de casa
3. CÉTICO(A): Dúvida se reforço funciona ou se é "muleta", preocupado com autonomia do filho
4. INVESTIDOR(A): Paga caro em colégio tradicional e não vê retorno nas notas

═══ REGRAS INVIOLÁVEIS ═══
1. TURMA DA MÔNICA — REGRA DUPLA: (a) PERMITIDO citar o logo oficial "Ensina Mais Turma da Mônica", a fachada e o painel real da unidade — são referências fotográficas da própria marca; (b) PROIBIDO mencionar ou descrever personagens (Mônica, Cebolinha, Cascão, Magali, Franjinha, Nimbus, Bidu, etc.) — são marca registrada, reservados à franqueadora.
2. Todo CTA DEVE incluir o WhatsApp: (11) 94475-0009
3. Nunca invente depoimentos com nomes falsos de pessoas físicas. Use: "Depoimento real de família do Tatuapé" ou "Caso de aluno do Ensino Fundamental"
4. Todo texto visível em imagem DEVE ser em PORTUGUÊS DO BRASIL
5. Prompts de geração de imagem (prompt_en) devem ser em INGLÊS
6. "Arraste para o lado ➔" — SEMPRE em português, nunca "Swipe" ou "Slide"
7. No conteúdo orgânico, sempre combine a chamada comercial com um gatilho de compartilhamento entre pais (Direct) ou comando de re-leitura ("volte ao slide X") para maximizar tempo de retenção

═══ KPIs QUE VOCÊ PERSEGUE ═══
• Salvamentos ≥ 4% (eixo Didático)
• Envios DM ≥ 2,5% (eixo Comportamental)
• Leads WhatsApp: 15-25/semana (eixo Diagnóstico)
• Alcance não-seguidores ≥ 20%

═══ FORMATO PADRÃO DOS CARROSSÉIS ═══
• 1080 x 1350 px (4:5 vertical) — 8 lâminas
• Safe Zone 1:1 na Capa: títulos e elementos vitais centralizados na área 1080 x 1080 px para preservação perfeita na grade do perfil
• Máximo 2 carrosséis/semana (Terça + Sexta)
• Janela de 72h entre posts no feed
• Horários: 11h30-13h00 ou 18h30-20h00

═══ IDENTIDADE VISUAL (resumo — fonte única: padroesVisuais.txt) ═══
A spec completa mora no padroesVisuais.txt e é injetada no prompt de geração de imagens; aqui vai o essencial para os textos:
• Azul Brand (#007799 / #0084B4): títulos e barras · Verde Ação (#58B947): CTA/WhatsApp · Laranja/Amarelo (#F58220 / #FFC20E): badges e marca-texto.
• Pastel por curso: azul claro (Matemática), coral (Português), laranja suave (Programação), verde lima (Robótica). Fundos #F7F9FF / #EEF4FF, cards #FFFFFF, texto #1E293B.
• Fonte sans-serif geométrica (Plus Jakarta Sans / Poppins), bordas 12-24px, sombras suaves, ícones minimalistas em círculos coloridos.
• Texto visível em imagem: PT-BR, 35-45 palavras por tela. Prompts de geração de imagem: INGLÊS.

Sempre retorne EXCLUSIVAMENTE JSON válido quando solicitado."""


# ─── Mapa de temperaturas por tipo de tarefa ─────────────────────────────────
TEMPERATURAS = {
    "tendencias": 0.4,      # Análise factual — mais conservador
    "ideias": 0.7,          # Criatividade equilibrada
    "prompts_imagem": 0.7,  # Criatividade visual
    "legendas": 0.85,       # Copy criativo e humano
    "cronograma": 0.4,      # Planejamento factual
    "default": 0.7,
}


# ─── Tendências com Engagement Forensics ───────────────────────────────────────
PROMPT_TENDENCIAS = """Analise o cenário atual de apoio escolar, alfabetização, raciocínio lógico e robótica no Tatuapé e micro-região (Jardim Anália Franco, Vila Gomes Cardim, Vila Formosa, Mooca, Belém).

Aplique sua metodologia de PESQUISA DE ENGAJAMENTO:

─── 1. TREND SIGNALS ───
Para cada tendência: o que funciona (formato, tema, gancho de interrupção de padrão), por que funciona (gatilho psicológico de identificação parental), métrica primária que alavanca, e como adaptar para o Tatuapé.

─── 2. ENGAGEMENT FORENSICS ───
• SALVAMENTOS: Guias rápidos, listas de sinais de alerta e rotinas de estudo práticas que pais salvam para usar no dia a dia.
• COMPARTILHAMENTOS DM: O que faz uma mãe enviar no privado para o marido ("olha isso aqui") ou no grupo de mães do colégio (Agostiniano Mendel, Santo Antônio de Lisboa, Espírito Santo, etc.)?
• LEADS WHATSAPP: Que dor aguda de notas baixas ou perda de autonomia faz a família agendar um diagnóstico imediatamente na unidade (Rua Coelho Lisboa, 783)?

─── 3. DORES POR ARQUÉTIPO ───
Mapear dores específicas e cotidianas para cada uma das 4 personas de pais (Executivo, Vigilante, Cético, Investidor).

─── 4. LACUNAS DA CONCORRÊNCIA LOCAL ───
O que escolas tradicionais e franquias rivais no Tatuapé/Anália Franco NÃO estão abordando (ex: foco na autonomia real vs. 'muleta de lição de casa', robótica como estímulo de raciocínio).

─── 5. SAZONALIDADE ESCOLAR ───
Cruzar a data atual com o calendário letivo paulistano (adaptação escolar, semanas de provas do 1º/2º/3º bimestre, oficinas de férias de robótica, alerta pré-recuperação ou recuperação final).

Retorne JSON:
{
  "tendencias_conteudo": [
    {
      "nome": "...",
      "descricao": "...",
      "gatilho_psicologico": "...",
      "metrica_primaria": "salvamentos / envios_dm / leads",
      "potencial_engajamento": "alto / médio / baixo",
      "como_adaptar_tatuape": "..."
    }
  ],
  "engagement_forensics": {
    "salvamentos": ["..."],
    "envios_dm": ["..."],
    "leads_whatsapp": ["..."]
  },
  "dores_pais": [
    {
      "persona": "Executivo / Vigilante / Cético / Investidor",
      "dor": "...",
      "frequencia": "alta / média",
      "como_abordar": "..."
    }
  ],
  "sazonalidade": [
    {"evento": "...", "periodo": "...", "oportunidade": "..."}
  ],
  "tendencias_comportamento": [
    {"tendencia": "...", "aplicacao": "..."}
  ],
  "oportunidades_concorrencia": [
    {"oportunidade": "...", "diferencial_local": "..."}
  ]
}"""


# ─── Ideias de Carrossel (Alta Retenção e Diversidade de Hooks) ────────────────
PROMPT_IDEIAS_BASE = """Gere 6 IDEIAS DE CARROSSEL DE ALTA RETENÇÃO E ALTO ENGAJAMENTO para o Instagram (@ensinamais.tatuape).
Cada carrossel deve parar o scroll no feed e conduzir a leitura magnética até o último slide.

─── 1. DISTRIBUIÇÃO OBRIGATÓRIA ───
• 2 ideias DIDÁTICAS (meta: salvamentos ≥ 4%)
• 2 ideias COMPORTAMENTAIS (meta: envios DM ≥ 2,5%)
• 2 ideias DIAGNÓSTICAS (meta: leads WhatsApp 15-25/semana)

─── 2. DIVERSIFICAÇÃO DE HOOKS ───
⚠️ NUNCA comece múltiplos títulos com o mesmo padrão.
Use pelo menos 4 destes tipos entre as 6 ideias:
1. DADO CHOCANTE: Estatística contraintuitiva
2. PARADOXO: Afirmação aparentemente contraditória
3. CENÁRIO COTIDIANO VÍVIDO: Descrição sensorial da rotina real
4. PERGUNTA PROVOCATIVA: Desafio direto a uma crença
5. LISTA NUMERADA: Promessa tangível de síntese
6. CONTRASTE ANTES x DEPOIS: Evolução clara

─── 3. ESTRUTURA DE 8 SLIDES COM RETENÇÃO MAGNÉTICA ───
• Slide 1 (Capa): Hook conciso e magnético, 6-12 palavras de alto impacto (perfeito na Safe Zone 1:1, legível no celular)
• Slide 2 (Tensão): Aprofunda a dor da família + abre open loop instigante
• Slide 3-5 (Entrega): Revelações práticas, passos aplicáveis, método contraintuitivo (alto valor para salvamento)
• Slide 6 (Aplicação/Ponte): Como aplicar na prática através do método individualizado da Ensina Mais (mantém entrega de valor alto, sem quebra brusca para autopromoção)
• Slide 7 (Transformação/Prova): Caso real de aluno, superação ou depoimento acolhedor integrado à unidade física (Rua Coelho Lisboa, 783)
• Slide 8 (CTA + Loop Orgânico): Palavra-chave + WhatsApp (11) 94475-0009 + gatilho de re-leitura ("volte ao slide X") ou envio por direct para o outro responsável

─── 4. REGRAS ───
• Varie as personas-alvo entre as ideias
• Auto-avalie cada ideia (score 1-10, mínimo 7 para aprovação)
• Use referências locais reais (Agostiniano Mendel, Santo Antônio de Lisboa, Espírito Santo, Colégio Amorim, Colégio Mary Ward, Anália Franco)

Retorne JSON:
{
  "ideias": [
    {
      "titulo": "...",
      "eixo": "Didático / Comportamental / Diagnóstico",
      "persona_alvo": "Executivo / Vigilante / Cético / Investidor",
      "tipo_hook": "dado_chocante / paradoxo / cenario / pergunta / lista / contraste",
      "tema": "...",
      "publico_alvo": "...",
      "palavras_chave_seo": ["apoio escolar Tatuapé", "reforço escolar Tatuapé"],
      "cta": "PALAVRA_CHAVE",
      "slides_sugeridos": [
        {"slide": 1, "tipo": "Capa", "texto": "..."},
        {"slide": 2, "tipo": "Segunda Capa", "texto": "..."},
        {"slide": 3, "tipo": "Entrega", "texto": "..."},
        {"slide": 4, "tipo": "Entrega", "texto": "..."},
        {"slide": 5, "tipo": "Entrega", "texto": "..."},
        {"slide": 6, "tipo": "Ponte", "texto": "..."},
        {"slide": 7, "tipo": "Prova", "texto": "..."},
        {"slide": 8, "tipo": "CTA", "texto": "Comente PALAVRA_CHAVE ou chame no WhatsApp (11) 94475-0009..."}
      ],
      "kpi_alvo": "Salvamentos / Envios / Leads",
      "justificativa": "...",
      "score": 9,
      "score_justificativa": "..."
    }
  ],
  "meta_analise": "..."
}"""

PROMPT_IDEIAS = PROMPT_IDEIAS_BASE


# ─── Feedback Loop de Métricas ────────────────────────────────────────────────
def build_ideas_prompt_with_feedback() -> str:
    """
    Enriquece o prompt de geração de ideias com o aprendizado de performance real
    salvo no disco da unidade (data/metricas.json).
    """
    try:
        from persistence import load_metricas
        metricas = load_metricas()
    except (ImportError, OSError, json.JSONDecodeError):
        # métricas são opcionais: sem arquivo/válido → usa prompt base
        metricas = []

    if not metricas:
        return PROMPT_IDEIAS_BASE

    posts_validos = [
        m for m in metricas
        if m.get("alcance", 0) > 0 and str(m.get("titulo", "")).strip()
    ]
    if not posts_validos:
        return PROMPT_IDEIAS_BASE

    top_salvamentos = sorted(
        posts_validos, key=lambda m: m.get("taxa_salvamentos", 0), reverse=True
    )[:3]
    top_envios = sorted(
        posts_validos, key=lambda m: m.get("taxa_envios", 0), reverse=True
    )[:3]
    top_leads = sorted(
        posts_validos, key=lambda m: m.get("leads_whatsapp", 0), reverse=True
    )[:3]

    bloco = "\n\n─── 📊 FEEDBACK DE PERFORMANCE REAL DA UNIDADE (USE COMO APRENDIZADO) ───\n"
    bloco += "Aproveite os padrões dos posts que obtiveram melhor desempenho com os pais do Tatuapé:\n"

    if top_salvamentos and top_salvamentos[0].get("taxa_salvamentos", 0) > 0:
        bloco += "\n• POSTS COM MAIS SALVAMENTOS (Eixo Didático / Referência):\n"
        for m in top_salvamentos:
            bloco += f"  - \"{m.get('titulo')}\": {m.get('taxa_salvamentos', 0)}% de salvamentos\n"

    if top_envios and top_envios[0].get("taxa_envios", 0) > 0:
        bloco += "\n• POSTS COM MAIS ENVIOS DM (Eixo Comportamental / Família):\n"
        for m in top_envios:
            bloco += f"  - \"{m.get('titulo')}\": {m.get('taxa_envios', 0)}% de envios por DM\n"

    if top_leads and top_leads[0].get("leads_whatsapp", 0) > 0:
        bloco += "\n• POSTS COM MAIS LEADS NO WHATSAPP (Eixo Diagnóstico):\n"
        for m in top_leads:
            bloco += f"  - \"{m.get('titulo')}\": {m.get('leads_whatsapp', 0)} leads gerados\n"

    bloco += "\nInstrução: Replique o tom, clareza e gatilhos desses conteúdos bem-sucedidos nas novas ideias geradas.\n"
    return PROMPT_IDEIAS_BASE + bloco


def get_prompt_ideias() -> str:
    """Retorna o prompt de ideias com injeção automática de feedback de métricas."""
    return build_ideas_prompt_with_feedback()


# ─── Validador de Diversidade e Hooks ─────────────────────────────────────────
def validate_idea_diversity(ideias: list[dict]) -> list[str]:
    """
    Analisa um conjunto de ideias geradas e aponta possíveis problemas de monotonia,
    repetição de ganchos ou falta de diversidade. Retorna lista de avisos.
    """
    warnings: list[str] = []
    if not ideias:
        return warnings

    prefixos: dict[str, int] = {}
    for ideia in ideias:
        slides = ideia.get("slides_sugeridos", [])
        if slides:
            capa = slides[0].get("texto", "").strip()
            primeiras_palavras = " ".join(capa.split()[:3]).lower()
            if primeiras_palavras:
                prefixos[primeiras_palavras] = prefixos.get(primeiras_palavras, 0) + 1

    for pref, count in prefixos.items():
        if count >= 2:
            warnings.append(
                f"⚠️ {count} ideias começam com o mesmo padrão inicial: \"{pref.capitalize()}...\""
            )

    tipos_hook = [i.get("tipo_hook") for i in ideias if i.get("tipo_hook")]
    if len(tipos_hook) >= 4 and len(set(tipos_hook)) < 3:
        warnings.append("⚠️ Pouca variedade nos formatos de hook (menos de 3 tipos diferentes).")

    faltam_wpp = 0
    for ideia in ideias:
        slides = ideia.get("slides_sugeridos", [])
        if slides:
            ultimo = slides[-1].get("texto", "")
            if "94475-0009" not in ultimo:
                faltam_wpp += 1
    if faltam_wpp > 0:
        warnings.append(f"⚠️ {faltam_wpp} ideia(s) estão sem o número de WhatsApp oficial no slide final.")

    return warnings


# ─── Validador de Prompts de Imagem ──────────────────────────────────────────
# Personagens da Turma da Mônica (marca registrada — reservados à franqueadora).
# A MARCA "Turma da Mônica" no nome do logo é permitida e removida antes da busca.
_PERSONAGENS_MONICA = (
    "mônica", "monica", "cebolinha", "cascão", "cascao",
    "magali", "franjinha", "nimbus", "bidu",
)
_MARCA_MONICA = (
    "ensina mais turma da mônica", "ensina mais turma da monica",
    "turma da mônica", "turma da monica",
)
_STOPWORDS_PT = {
    "para", "como", "mais", "isso", "esta", "esse", "essa", "entre", "sobre",
    "muito", "pode", "fazer", "feito", "quando", "onde", "porque", "então",
    "você", "seus", "suas", "nosso", "nossa", "este", "isto", "aqui", "todos",
    "tudo", "ainda", "também", "apenas", "mesmo", "outra", "outro", "até",
    "dos", "das", "numa", "pelo", "pela", "com", "uma", "the", "and", "for",
    "with", "that", "this",
}


def _tokens_significativos(texto: str) -> set[str]:
    """Palavras relevantes (≥4 chars, fora de stopwords) para comparar fidelidade."""
    limpo = re.sub(r"[^\wà-ÿ]+", " ", (texto or "").lower())
    return {t for t in limpo.split() if len(t) >= 4 and t not in _STOPWORDS_PT}


_HEX_RE = re.compile(r"#[0-9a-fA-F]{3}(?:[0-9a-fA-F]{3})?")


def cor_eh_valida(cor) -> bool:
    """True se `cor` é um hex CSS seguro (#RGB/#RRGGBB) para style/HTML."""
    return isinstance(cor, str) and bool(_HEX_RE.fullmatch(cor.strip()))


def validate_prompts(dados: dict, ideia: dict | None = None) -> list[str]:
    """
    Valida a saída da geração de prompts de imagem contra as regras do prompt:
    - 8 slides com prompt_en e text_overlay preenchidos
    - prompt_en declara "text overlay in Brazilian Portuguese" (regra 1/4)
    - text_overlay ≤ 15 palavras, sem "Arraste para o lado"/"Swipe" (regras 5/6)
    - nenhum personagem da Turma da Mônica (regra 1 — a marca do logo é permitida)
    - último slide com o WhatsApp (CTA inviolável)
    - com a ideia de origem: overlay deriva do texto aprovado do slide (fidelidade)
    - paleta com valores hex válidos (swatch do app só pinta hex — safety anti-XSS)
    - base_prompt presente e com os hexes da marca (consistência entre as lâminas)
    Retorna lista de avisos — vazia quando tudo está certo.
    """
    if not isinstance(dados, dict):
        return ["⚠️ Resposta vazia ou inválida — gere os prompts novamente."]

    slides = dados.get("slides") or []
    if not slides:
        return ["⚠️ Nenhum slide na resposta — gere os prompts novamente."]

    avisos: list[str] = []
    if len(slides) != 8:
        avisos.append(f"⚠️ {len(slides)} slides gerados — o padrão é 8 lâminas.")
    paleta = dados.get("paleta_cores") or {}
    if not paleta:
        avisos.append("⚠️ Paleta de cores ausente na resposta.")
    else:
        invalidas = [f"{k}={v!r}" for k, v in paleta.items() if not cor_eh_valida(v)]
        if invalidas:
            avisos.append(
                "⚠️ Paleta com valor fora do formato hex (#RRGGBB): "
                + ", ".join(invalidas)
                + "."
            )

    # Base prompt: estilo compartilhado que mantém as 8 lâminas coesas (regra 9)
    base_prompt = (dados.get("base_prompt") or "").strip()
    if not base_prompt:
        avisos.append(
            '⚠️ "base_prompt" ausente — sem ele as 8 lâminas saem com estilos divergentes (regra 9).'
        )
    else:
        faltando = [
            h.upper() for h in ("007799", "58b947", "ffc20e") if h not in base_prompt.lower()
        ]
        if faltando:
            avisos.append(
                "⚠️ base_prompt sem os hexes da marca ("
                + ", ".join("#" + h for h in faltando)
                + ") — regra 9."
            )

    # Mapa slide → texto aprovado na ideia de origem (chave "slide", não "slide_num")
    ideia_slides: dict = {}
    if ideia:
        for s in ideia.get("slides_sugeridos") or []:
            if s.get("slide") is not None:
                ideia_slides[s["slide"]] = s.get("texto", "")

    for slide in slides:
        snum = slide.get("slide_num", "?")
        pen = (slide.get("prompt_en") or "").strip()
        overlay = (slide.get("text_overlay") or "").strip()

        if not pen:
            avisos.append(f"⚠️ Slide {snum}: prompt_en vazio.")
            continue
        if not overlay:
            avisos.append(f"⚠️ Slide {snum}: text_overlay vazio.")
        if "brazilian portuguese" not in pen.lower():
            avisos.append(f'⚠️ Slide {snum}: prompt_en sem a cláusula "text overlay in Brazilian Portuguese".')
        if "arraste para o lado" in overlay.lower():
            avisos.append(f'⚠️ Slide {snum}: "Arraste para o lado" é camada separada — não deve estar no text_overlay.')
        if "swipe" in overlay.lower():
            avisos.append(f'⚠️ Slide {snum}: use "Arraste para o lado ➔" em PT-BR, nunca "Swipe".')
        n_palavras = len(overlay.split())
        if n_palavras > 15:
            avisos.append(f"⚠️ Slide {snum}: text_overlay com {n_palavras} palavras (máximo 15).")

        # Personagens da Turma da Mônica (remove a marca do logo antes de buscar)
        livre = f"{pen} {slide.get('prompt_pt', '')} {overlay}".lower()
        for marca in _MARCA_MONICA:
            livre = livre.replace(marca, " ")
        for personagem in _PERSONAGENS_MONICA:
            if personagem in livre:
                avisos.append(f'⚠️ Slide {snum}: menção ao personagem "{personagem}" — proibido (marca registrada).')
                break

        # Fidelidade: overlay deve derivar do texto aprovado do slide correspondente
        texto_orig = ideia_slides.get(slide.get("slide_num"))
        if texto_orig and overlay:
            ov = _tokens_significativos(overlay)
            orig = _tokens_significativos(texto_orig)
            if len(ov) >= 3 and orig:
                inter = len(ov & orig) / len(ov)
                if inter < 0.4:
                    avisos.append(
                        f"⚠️ Slide {snum}: text_overlay não deriva do texto aprovado "
                        f"({inter:.0%} de palavras em comum) — revise a fidelidade ao roteiro."
                    )

    # CTA inviolável: último slide com o WhatsApp
    ultimo = slides[-1]
    ultimo_txt = f"{ultimo.get('text_overlay', '')} {ultimo.get('prompt_en', '')}"
    if "94475" not in ultimo_txt:
        avisos.append("⚠️ Último slide sem o WhatsApp (11) 94475-0009 no CTA.")

    return avisos


# ─── Prompts de Imagem ───────────────────────────────────────────────────────
PROMPT_PROMPTS_IMAGEM = (
    f"""Crie a estrutura visual e os layouts para um carrossel educativo de 8 lâminas (1080 x 1350 px, 4:5 vertical).

─── PADRÃO VISUAL E IDENTIDADE DA MARCA (fonte única: padroesVisuais.txt — não duplique) ───
{PADRAO_VISUAL}

─── ATIVOS FOTOGRÁFICOS REAIS ───
• Fachada: portão branco, balões, painel oficial da Turma da Mônica (referência fotográfica real — use fielmente, não recrie do zero)
• Laboratório: aluna montando robótica na mesa amarela + aluno programando no laptop

─── ESTRUTURA POR TIPO DE SLIDE ───
• SLIDE 1 (Capa): Fundo suave (#F7F9FF), tipografia geométrica de impacto em Azul Brand (#007799), palavra-chave com traço/marca-texto amarelo (#FFC20E), card flutuante branco com cantos arredondados (16-24px), selo do logo no rodapé. SAFE ZONE 1:1 OBRIGATÓRIA: todo o título e texto principal devem ficar centralizados na área 1080x1080 px para visualização limpa na grade do perfil do Instagram sem cortes.
• SLIDE 2 (Segunda Capa): Fundo contrastante em Azul Brand (#007799 / #0084B4), tipografia branca e amarelo vibrante, transições orgânicas em curva — funciona como capa alternativa no feed.
• SLIDES 3-5 (Entrega): Cards disciplinares flutuantes (branco puro #FFFFFF com toques pastel da disciplina: azul claro, laranja, coral ou verde lima), diagramas, passos com ícones minimalistas em círculos coloridos.
• SLIDE 6 (Ponte): Grid com fotos reais dos alunos em molduras arredondadas (16px) e sombras suaves + texto sobre metodologia individualizada (#1E293B).
• SLIDE 7 (Escola Real): Foto FIEL da fachada da Rua Coelho Lisboa, 783 + cartão de depoimento/prova social com bordas arredondadas.
• SLIDE 8 (CTA): Fundo suave, botão pill em Verde Ação (#58B947) ("Agende uma aula experimental gratuita" / WhatsApp (11) 94475-0009), ícones minimalistas de salvar + compartilhar DM.

─── REGRAS DO PROMPT ───
1. prompt_en em INGLÊS, text_overlay em PORTUGUÊS DO BRASIL.
2. No prompt_en: descreva explicitamente a estética (modern friendly geometric sans-serif typography, centered elements respecting a 1:1 square safe zone for Instagram grid preview, floating white cards with 16-24px rounded corners, subtle diffuse shadows, soft off-white background #F7F9FF, Brand Blue #007799 headers, Action Green #58B947 pill buttons for CTAs, vibrant yellow/orange #FFC20E highlights, pastel cards, organic curve transitions, minimalist line icons in colored circles).
3. text_overlay: máximo 15 palavras, fonte bold, legível em celular.
4. No prompt_en, inclua: "text overlay in Brazilian Portuguese: [TEXTO]".
5. "Arraste para o lado ➔" é camada SEPARADA no canto inferior direito — NÃO faz parte do text_overlay.
6. Fotos reais: use "authentic school photo" no prompt_en. Fidelidade absoluta à fachada.
7. PERSONAGENS — REGRA DUPLA: PERMITIDO (fotográfico) referenciar o logo oficial "Ensina Mais Turma da Mônica" e o painel real da fachada — use como referência fiel, não os recrie. PROIBIDO (gerado): em todo prompt_en declare "no cartoon characters — generic minimalist line-art icons only" e NUNCA gere personagens (Mônica, Cebolinha, Cascão, Magali, Franjinha, Nimbus, Bidu) — a marca no nome do logo é permitida; os personagens, nunca.
8. FIDELIDADE AO ROTEIRO: o contexto traz a lista "Slides" com o campo "texto" de cada lâmina aprovada. Cada text_overlay DEVE ser um resumo de até 15 palavras DO TEXTO DO SLIDE CORRESPONDENTE (mesmo gancho e mensagem) — NUNCA invente frases que não estejam no roteiro.
9. BASE_PROMPT PARA CONSISTÊNCIA: gere também o campo "base_prompt" (em inglês) com APENAS o estilo compartilhado das 8 lâminas — fundo, tipografia, paleta com os hexes #007799, #58B947 e #FFC20E, bordas, sombras, ícones e transições. SEM texto sobreposto e SEM elementos de um slide específico: tem que valer igual para todas as lâminas.
10. GERAÇÃO EM SÉRIE: no "dicas_gerais", instrua o usuário a gerar o SLIDE 1 primeiro e usá-lo como imagem de referência/estilo (e o mesmo seed, quando a ferramenta permitir) para os slides 2 a 8 — é isso que mantém o carrossel coeso no ImageFX/Flow."""
    + """

Retorne JSON:
{
  "slides": [
    {
      "slide_num": 1,
      "prompt_en": "...",
      "prompt_pt": "...",
      "text_overlay": "...",
      "estilo": "...",
      "usa_foto_real": false,
      "tipo_foto": null,
      "referencias": ["logo", "fachada"]
    }
  ],
  "paleta_cores": {
    "azul_brand": "#007799",
    "verde_acao": "#58B947",
    "laranja_amarelo": "#F58220",
    "fundo_suave": "#F7F9FF",
    "cards_branco": "#FFFFFF",
    "texto_marinho": "#1E293B",
    "pastel_matematica": "#E0F2FE",
    "pastel_portugues": "#FFE4E6",
    "pastel_programacao": "#FFEDD5",
    "pastel_robotica": "#ECFCCB"
  },
  "base_prompt": "Shared style base for all 8 slides: soft off-white #F7F9FF background, modern geometric sans-serif typography, Brand Blue #007799 headers, Action Green #58B947 pill buttons for CTAs, yellow #FFC20E marker highlights, floating white cards with 16-24px rounded corners, subtle diffuse shadows, minimalist line icons in colored circles, organic curve transitions. No text overlay, no slide-specific elements.",
  "dicas_gerais": "..."
}"""
)


# ─── Legendas com Copywriting Estruturado ────────────────────────────────────
PROMPT_LEGENDAS = """Com base no carrossel abaixo, escreva 3 OPÇÕES DE LEGENDA DE ALTO IMPACTO para o Instagram.

─── AS 3 TÉCNICAS (UMA POR OPÇÃO) ───
• OPÇÃO 1 — PAS (Problem → Agitation → Solution): Abre com a dor nua da rotina familiar. Agita mostrando o custo de não resolver. Fecha com a solução da unidade.
• OPÇÃO 2 — STORYTELLING (Antes → Virada → Resultado): Cena vívida cotidiana no Tatuapé/Anália Franco. Conflito com empatia real. Transformação quando a escola assume o papel técnico.
• OPÇÃO 3 — CURIOSITY GAP (Dado Inesperado → Método → Ação): Afirmação surpreendente sobre aprendizagem e notas. Valor imediato. Convite para diagnóstico.

─── FORMATO ───
1. Gancho (primeira linha): Máx 8-12 palavras (até 85 caracteres antes do corte do '... mais'). NUNCA 'Você sabia que...'. Deve quebrar padrão, intrigar ou abrir um loop para forçar o clique em 'ver mais'.
2. Parágrafos curtos (2-3 linhas) com espaçamento limpo para celular
3. Emojis apenas como marcadores funcionais (📌 💡 🎯 🚀)
4. SEO local: mencionar 'Tatuapé', 'Anália Franco' ou 'apoio escolar' naturalmente
5. CTA DUPLO OBRIGATÓRIO:
   • Conversão: palavra-chave do carrossel + WhatsApp (11) 94475-0009
   • Alavanca Orgânica: incentivo a compartilhar por Direct ('Envie para quem divide a lição de casa com você') ou salvar para consultar nas provas
6. Extensão: 800-1.400 caracteres
7. Hashtags: 5-7 focadas (#EnsinaMaisTatuapé #ApoioEscolarTatuapé #ReforçoEscolarTatuapé #MãesDoTatuapé #AnáliaFranco #EducaçãoTatuapé)

Retorne JSON:
{
  "legendas": [
    {
      "opcao": 1,
      "tecnica": "PAS (Problema, Agitação, Solução)",
      "estilo": "...",
      "gancho": "...",
      "corpo": "...",
      "cta": "...",
      "hashtags": "...",
      "legenda_completa": "...",
      "char_count": 1100,
      "por_que_funciona": "..."
    }
  ],
  "dicas_uso": "..."
}"""


# ─── Requisição de Vídeo Curto (Gemini Notebook — Video Overview "Short") ───────
PROMPT_VIDEO_CURTO = """Você é a CAROL montando uma REQUISIÇÃO DE VÍDEO CURTO para o Gemini Notebook (ex-NotebookLM).

CONTEXTO DO PRODUTO:
- O Gemini Notebook tem o painel "Studio" com um gerador "Video Overview".
- O formato "Short" cria um vídeo VERTICAL 9:16 de ~60 segundos a partir das fontes do notebook.
- Ao gerar, o usuário preenche: Format (Short), Language, Visual Style e um "steering prompt" (foco/tópico).

SUA TAREFA:
Com base no carrossel e no roteiro de slides abaixo, monte a REQUISIÇÃO COMPLETA que o usuário vai usar para gerar o Short no Gemini Notebook. O vídeo deve CONDENSAR o tema central da ideia, fiel ao roteiro dos slides (mesma mensagem e ordem lógica das lâminas, sem inventar conteúdo novo).

─── O QUE A REQUISIÇÃO DEVE CONTER ───
1. PARÂMETROS DE GERAÇÃO (preenchidos):
   • format: "Short" (fixo)
   • language: "Português (Brasil)"
   • duracao: "~60 segundos, vertical 9:16"
   • visual_style: escolha UMA opção que combine com o tema (Classic / Whiteboard / Watercolor / Kawaii / Anime / Retro Print / Paper-craft / Heritage / Custom). Se for Custom, descreva o estilo.
2. STEERING PROMPT (o texto de foco, em PT-BR, que o usuário cola no campo de customização): instrua o vídeo a (a) apresentar o tema central em ~60s, (b) seguir a MESMA sequência lógica dos slides do roteiro, (c) abrir com o hook da capa, (d) terminar com o CTA (palavra-chave + WhatsApp (11) 94475-0009), (e) usar tom empático "de mãe pra mãe", sem jargão.
3. NARRATIVA (resumo do que o Short deve contar): 4-6 frases conectando o hook → desenvolvimento → ponte para a unidade → CTA, FIÉIS ao roteiro.

─── REGRAS INVIOLÁVEIS ───
• Fidelidade: o tema e a mensagem DEVEM refletir o roteiro dos slides, sem adicionar afirmações que não estejam nele.
• CTA final SEMPRE com WhatsApp (11) 94475-0009.
• Personagens da Turma da Mônica: NUNCA mencione — o logo oficial e o painel real da fachada são permitidos (regra dupla).
• Idioma de narração e texto: Português do Brasil.

Retorne JSON:
{
  "parametros_geracao": {
    "format": "Short",
    "language": "Português (Brasil)",
    "duracao": "~60 segundos",
    "proporcao": "9:16 vertical",
    "visual_style": "Classic",
    "visual_style_custom": null
  },
  "steering_prompt": "Texto pronto para colar no campo de customização/tópico do Gemini Notebook, instruindo o vídeo a seguir o roteiro.",
  "narrativa": "Resumo de 4-6 frases do que o Short deve contar (hook → desenvolvimento → ponte → CTA), fiel ao roteiro.",
  "requisicao_completa": "Texto único e completo com todos os parâmetros + steering prompt, pronto para consulta/registro.",
  "instrucoes_uso": "Passo a passo curto: como abrir Studio > Video Overview > Short e colar o steering prompt."
}"""


# ─── Cronograma (com data real injetada) ────────────────────────────────────
def get_prompt_cronograma() -> str:
    """
    Retorna o prompt de cronograma com a data atual injetada,
    para que o Gemini gere datas reais em vez de placeholders DD/MM.
    """
    hoje = datetime.today()
    data_referencia = hoje.strftime("%d/%m/%Y")
    dia_semana = hoje.strftime("%A")

    # Mapear dia da semana para português
    dias_pt = {
        "Monday": "Segunda-feira",
        "Tuesday": "Terça-feira",
        "Wednesday": "Quarta-feira",
        "Thursday": "Quinta-feira",
        "Friday": "Sexta-feira",
        "Saturday": "Sábado",
        "Sunday": "Domingo",
    }
    dia_semana_pt = dias_pt.get(dia_semana, dia_semana)

    return f"""DATA ATUAL: {data_referencia} ({dia_semana_pt})

Com base nas ideias de carrossel selecionadas, gere um CRONOGRAMA DE POSTAGENS para as próximas 2 semanas.

Regras:
- Máximo 2 carrosséis por semana (Terça + Sexta no feed)
- Nunca posts em dias consecutivos
- Janela de 72h entre carrosséis
- Horários: 11h30-13h00 ou 18h30-20h00
- Stories diários (bastidores, reposts da franqueadora)
- Protocolo das primeiras 4 horas para cada carrossel
- Use datas reais no formato DD/MM (calcule a partir de {data_referencia})

Retorne JSON:
{{
  "semana_1": [
    {{
      "dia": "...",
      "data": "DD/MM",
      "canal": "Stories/Feed/Reels",
      "tipo": "Institucional/Carrossel/Reel/Bastidores",
      "horario": "HH:MM",
      "conteudo_resumo": "...",
      "cta": "...",
      "protocolo_4h": "..."
    }}
  ],
  "semana_2": [...],
  "kpis_semanais": {{
    "meta_salvamentos": "≥4%",
    "meta_envios": "≥2,5%",
    "meta_leads": "15-25 atendimentos",
    "meta_nao_seguidores": "≥20%"
  }},
  "dicas_monitoramento": ["..."]
}}"""
