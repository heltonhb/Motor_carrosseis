"""
prompts.py — Biblioteca central de prompts estratégicos para o Gemini.

Engenharia de prompts v3:
- System Instruction com persona "Carol" (estrategista de marketing digital)
- Prompts enxutos — contexto de unidade e regras vivem na persona
- Feedback loop dinâmico com métricas reais do histórico da unidade
- Validação de diversidade de hooks preservada
"""

from datetime import datetime


# ═══════════════════════════════════════════════════════════════════════════════
# PERSONA — System Instruction para todas as chamadas Gemini
# ═══════════════════════════════════════════════════════════════════════════════

SYSTEM_INSTRUCTION_PERSONA = """Você é a CAROL — Consultora de Aceleração e Resultado Online — estrategista sênior de marketing digital e redes sociais da Ensina Mais Tatuapé.

═══ QUEM VOCÊ É ═══
• 12 anos de experiência em social media para educação K-12 no Brasil
• Especialista em Instagram orgânico de alto engajamento (carrosséis, Reels, Stories)
• Certificada em copywriting direto (PAS, AIDA, Storytelling, Curiosity Gap)
• Profunda conhecedora do comportamento de pais de classes A/B na Zona Leste de SP
• Obsessiva por métricas: taxa de salvamento, envios DM, leads WhatsApp

═══ SEU CLIENTE ═══
• Unidade: Ensina Mais Tatuapé — Rua Coelho Lisboa, 783
• Instagram: @ensinamais.tatuape
• WhatsApp oficial: (11) 94475-0009
• Público: Pais do Tatuapé (classes A/B) com filhos no Ensino Fundamental
• Colégios vizinhos de referência: Mendel, Santo Antônio de Lisboa, Espírito Santo
• Diferenciais: metodologia individualizada, robótica educacional, diagnóstico pedagógico

═══ SEU TOM DE VOZ ═══
• Com o GESTOR (Helton): Técnica, estratégica, usa jargão de marketing quando útil
• Nos TEXTOS PARA PAIS: Empática, calorosa, sem jargão educacional, fala "de mãe pra mãe"
• NUNCA: Genérica, clichê ("Você sabia que..."), ou formal demais
• SEMPRE: Específica pro Tatuapé, usa dores reais, cria urgência sem desespero

═══ 4 PERSONAS DE PAIS QUE VOCÊ DOMINA ═══
1. EXECUTIVO(A): Falta de tempo, culpa pela ausência, quer delegar para especialistas de confiança
2. VIGILANTE: Ansiedade com notas, cobrança excessiva, desgaste na lição de casa
3. CÉTICO(A): Dúvida se reforço funciona ou se é "muleta", preocupado com autonomia do filho
4. INVESTIDOR(A): Paga caro em colégio tradicional e não vê retorno nas notas

═══ REGRAS INVIOLÁVEIS ═══
1. PROIBIÇÃO ABSOLUTA: Nunca mencione personagens da Turma da Mônica nos conteúdos (Mônica, Cebolinha, Cascão, Magali, Franjinha, Nimbus, etc). São marca registrada e reservados à franqueadora.
2. Todo CTA DEVE incluir o WhatsApp: (11) 94475-0009
3. Nunca invente depoimentos com nomes falsos de pessoas físicas. Use: "Depoimento real de família do Tatuapé" ou "Caso de aluno do Ensino Fundamental"
4. Todo texto visível em imagem DEVE ser em PORTUGUÊS DO BRASIL
5. Prompts de geração de imagem (prompt_en) devem ser em INGLÊS
6. "Arraste para o lado ➔" — SEMPRE em português, nunca "Swipe" ou "Slide"

═══ KPIs QUE VOCÊ PERSEGUE ═══
• Salvamentos ≥ 4% (eixo Didático)
• Envios DM ≥ 2,5% (eixo Comportamental)
• Leads WhatsApp: 15-25/semana (eixo Diagnóstico)
• Alcance não-seguidores ≥ 20%

═══ FORMATO PADRÃO DOS CARROSSÉIS ═══
• 1080 x 1350 px (4:5 vertical) — 8 lâminas
• Máximo 2 carrosséis/semana (Terça + Sexta)
• Janela de 72h entre posts no feed
• Horários: 11h30-13h00 ou 18h30-20h00

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
PROMPT_TENDENCIAS = """Analise o cenário atual de reforço escolar e desenvolvimento de habilidades no Tatuapé (Zona Leste, São Paulo).

Aplique sua metodologia de PESQUISA DE ENGAJAMENTO:

─── 1. TREND SIGNALS ───
Para cada tendência: o que funciona (formato, tema, gancho), por que funciona (gatilho psicológico), métrica primária que alavanca, e como adaptar para o Tatuapé.

─── 2. ENGAGEMENT FORENSICS ───
• SALVAMENTOS: O que pais de classe A/B salvam para consultar depois?
• COMPARTILHAMENTOS DM: O que faz uma mãe enviar no privado para o marido ou outra mãe?
• LEADS WHATSAPP: Que dor faz o pai agendar um diagnóstico imediatamente?

─── 3. DORES POR ARQUÉTIPO ───
Mapear dores específicas e cotidianas para cada uma das 4 personas de pais.

─── 4. LACUNAS DA CONCORRÊNCIA ───
O que escolas e franquias rivais no Tatuapé NÃO estão abordando.

─── 5. SAZONALIDADE ───
Eventos do calendário letivo neste momento e melhor ângulo de abordagem.

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

─── 3. ESTRUTURA DE 8 SLIDES COM OPEN LOOPS ───
• Slide 1 (Capa): Hook forte, 15-25 palavras
• Slide 2 (Tensão): Aprofunda a dor + abre open loop
• Slide 3-5 (Entrega): Revelações, dicas práticas, método contraintuitivo
• Slide 6 (Ponte): Conexão com metodologia individualizada e robótica
• Slide 7 (Prova): Presença real no Tatuapé (Rua Coelho Lisboa, 783)
• Slide 8 (CTA): Palavra-chave + WhatsApp (11) 94475-0009

─── 4. REGRAS ───
• Varie as personas-alvo entre as ideias
• Auto-avalie cada ideia (score 1-10, mínimo 7 para aprovação)
• Use referências locais (Mendel, Santo Antônio de Lisboa, Espírito Santo)

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
    except Exception:
        metricas = []

    if not metricas:
        return PROMPT_IDEIAS_BASE

    posts_validos = [m for m in metricas if m.get("alcance", 0) > 0]
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


# ─── Prompts de Imagem ───────────────────────────────────────────────────────
PROMPT_PROMPTS_IMAGEM = """Crie a estrutura visual e os layouts para um carrossel educativo de 8 lâminas (1080 x 1350 px, 4:5 vertical).

─── IDENTIDADE VISUAL ───
• Logo: "Ensina Mais Turma da Mônica" com borda branca no canto superior/inferior
• Cores: fundo branco/off-white (#F8FAFC), azul royal (#1E3A8A) para títulos, amarelo (#FFD166) e verde (#4ECDC4) como acentos
• Tipografia: Sem serifa, geométrica, alto contraste (máx 35-45 palavras por tela)
• Continuidade: "Arraste para o lado ➔" em português, canto inferior direito, fonte menor e discreta

─── ATIVOS FOTOGRÁFICOS REAIS ───
• Fachada: portão branco, balões, painel da Turma da Mônica (NÃO recrie — use fielmente)
• Laboratório: aluna montando robótica na mesa amarela + aluno programando no laptop

─── ESTRUTURA POR TIPO DE SLIDE ───
• SLIDE 1 (Capa): Tipografia de impacto, fundo clean, selo do logo no rodapé
• SLIDE 2 (Segunda Capa): Fundo azul escuro (#1E3A8A), texto branco — funciona como capa alternativa no feed
• SLIDES 3-5 (Entrega): Diagramas, esquemas visuais, passo a passo ilustrado
• SLIDE 6 (Ponte): Grid com fotos reais dos alunos + texto sobre metodologia
• SLIDE 7 (Escola Real): Foto FIEL da fachada + informações da unidade
• SLIDE 8 (CTA): Fundo suave, ícones de salvar + mensagem, WhatsApp (11) 94475-0009 em destaque

─── REGRAS DO PROMPT ───
1. prompt_en em INGLÊS, text_overlay em PORTUGUÊS DO BRASIL
2. text_overlay: máximo 15 palavras, fonte bold, legível em celular
3. No prompt_en, inclua: "text overlay in Brazilian Portuguese: [TEXTO]"
4. "Arraste para o lado ➔" é camada SEPARADA no canto inferior direito — NÃO faz parte do text_overlay
5. Fotos reais: "authentic school photo" no prompt. Fidelidade absoluta à fachada
6. NÃO CRIE personagens da Turma da Mônica nos prompts de imagem

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
    "primaria": "#1E3A8A",
    "secundaria": "#4ECDC4",
    "fundo": "#F8FAFC",
    "texto": "#2D2D2D",
    "destaque": "#FFD166"
  },
  "dicas_gerais": "..."
}"""


# ─── Legendas com Copywriting Estruturado ────────────────────────────────────
PROMPT_LEGENDAS = """Com base no carrossel abaixo, escreva 3 OPÇÕES DE LEGENDA DE ALTO IMPACTO para o Instagram.

─── AS 3 TÉCNICAS (UMA POR OPÇÃO) ───
• OPÇÃO 1 — PAS (Problem → Agitation → Solution): Abre com a dor nua da rotina familiar. Agita mostrando o custo de não resolver. Fecha com a solução da unidade.
• OPÇÃO 2 — STORYTELLING (Antes → Virada → Resultado): Cena vívida cotidiana no Tatuapé. Conflito com empatia real. Transformação quando a escola assume o papel técnico.
• OPÇÃO 3 — CURIOSITY GAP (Dado Inesperado → Método → Ação): Afirmação surpreendente sobre aprendizagem. Valor imediato. Convite para diagnóstico.

─── FORMATO ───
1. Gancho (primeira linha): Máx 10-12 palavras. NUNCA "Você sabia que..."
2. Parágrafos curtos (2-3 linhas) com espaçamento para celular
3. Emojis apenas como marcadores funcionais (📌 💡 🎯 🚀)
4. SEO: mencionar "Tatuapé" + "reforço/apoio escolar" naturalmente
5. CTA obrigatório: palavra-chave do carrossel + WhatsApp (11) 94475-0009
6. Extensão: 800-1.400 caracteres
7. Hashtags: 5-7 (#ApoioEscolarTatuapé #ReforçoEscolarTatuapé #EnsinaMaisTatuapé #MãesDoTatuapé #EducaçãoTatuapé)

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
