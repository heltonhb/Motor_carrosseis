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

from config import TAG_NAVEGACAO, TONES_PADRAO, TONES_POR_EIXO
from refs_catalog import (
    CENAS_FOTO,
    cena_valida,
    chaves_cenas,
    texto_catalogo_para_prompt,
)

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
1. TURMA DA MÔNICA — REGRA DUPLA: (a) PERMITIDO citar o logo oficial "Ensina Mais Turma da Mônica", a fachada e o painel real da unidade — são referências fotográficas da própria marca; (b) PROIBIDO mencionar ou descrever personagens (Mônica, Cebolinha, Cascão, Magali, Franjinha, Nimbus, Bidu, Chico Bento, Pit Lelé, etc.) — são marca registrada, reservados à franqueadora.
2. CTA / SLIDE FINAL (INVIOLÁVEL): O Slide final (CTA) DEVE SEMPRE oferecer uma aula experimental gratuita (em posts de tecnologia: Robótica ou Programação) ou avaliação pedagógica gratuita (em posts de apoio escolar: Português ou Matemática) e pedir para entrar em contato via WhatsApp oficial da unidade: (11) 94475-0009
3. Nunca invente depoimentos com nomes falsos de pessoas físicas. Use: "Depoimento real de família do Tatuapé" ou "Caso de aluno do Ensino Fundamental"
3b. DADO SEM FONTE É PROIBIDO (vale tanto para texto de slide quanto para legenda): nenhum número, porcentagem, tempo de queda, taxa de ganho, "milhares de alunos", "estudo comprova" ou "dado chocante" pode aparecer sem citar a fonte real (IBGE, INEP, PISA, SAEB, IESL/Pesquisa ABC, dados da própria unidade) ou sem estar marcado como observação da unidade ("na nossa sala", "com os alunos que atendemos", "ano passado na unidade"). Se não houver fonte, ESCREVA O FATO EM LINGUAGEM OBSERVACIONAL, SEM NÚMERO: "os alunos que chegam ao 5º ano costumam travar na mesma conta" em vez de "80% erram essa conta". Número bonito e falso é o que mais destrói a confiança de um pai — e é o que faz o post parecer de qualquer educador.
4. Todo texto visível em imagem DEVE ser em PORTUGUÊS DO BRASIL
5. Prompts de geração de imagem (prompt_en) devem ser em INGLÊS
6. A tag de navegação "Mova para o próximo ➔" deve aparecer nos slides 1 a 7 e nunca no último slide
7. No conteúdo orgânico, sempre combine a chamada comercial com um gatilho de compartilhamento entre pais (Direct) ou comando de re-leitura ("volte ao slide X") para maximizar tempo de retenção
8. SLIDES THUMBNAIL (1, 4 e 5): devem ser composições profissionais SOBRE a foto real da unidade Tatuapé (recepção ou alunos em atividades) — a foto entra como camada de fundo intacta, e o que se compõe por cima é tipografia e elementos gráficos mínimos (como um designer faria no Photoshop). Nunca banco de imagens, ilustração ou cena genérica gerada por IA

═══ KPIs QUE VOCÊ PERSEGUE ═══
• Salvamentos ≥ 4% (eixo Didático)
• Envios DM ≥ 2,5% (eixo Comportamental)
• Leads WhatsApp: 15-25/semana (eixo Diagnóstico)
• Alcance não-seguidores ≥ 20%

═══ FORMATO PADRÃO DOS CARROSSÉIS ═══
• 1080 x 1350 px (4:5 vertical) — 8 lâminas
• Safe Zone 1:1 na Capa: títulos e elementos vitais centralizados na área 1080 x 1080 px para preservação perfeita na grade do perfil
• THUMBNAILS COM FOTO REAL (slides 1, 4 e 5): composição profissional sobre a foto real da unidade Tatuapé — a foto entra como camada de fundo full-bleed, intacta. Sobre ela, overlay de texto curto (3-8 palavras) que interrompe o scroll. A foto NÃO é regenerada nem recriada — é editada/composta como um profissional faria no Photoshop.
• Máximo 2 carrosséis/semana (Terça + Sexta)
• Janela de 72h entre posts no feed
• Horários: 11h30-13h00 ou 18h30-20h00

═══ IDENTIDADE VISUAL (resumo — fonte única: padroesVisuais.txt) ═══
A spec completa mora no padroesVisuais.txt e é injetada no prompt de geração de imagens; aqui vai o essencial para os textos:
• Azul Brand (#007799 / #0084B4): títulos e barras · Verde Ação (#58B947): CTA/WhatsApp · Laranja/Amarelo (#F58220 / #FFC20E): badges e marca-texto.
• Pastel por curso: azul claro (Matemática), coral (Português), laranja suave (Programação), verde lima (Robótica). Fundos #F7F9FF / #EEF4FF, cards #FFFFFF, texto #1E293B.
• Fonte sans-serif geométrica (Plus Jakarta Sans / Poppins), bordas 12-24px, sombras suaves, ícones minimalistas em círculos coloridos.
• Texto visível em imagem: PT-BR — 30-50 palavras por tela nos slides do roteiro renderizados (meta 35-45); em prompts de imagem o text_overlay é curto (≤15 palavras; thumbnails 1, 4 e 5: 3-8 palavras). Prompts de geração de imagem: INGLÊS.

Sempre retorne EXCLUSIVAMENTE JSON válido quando solicitado."""


# ─── Mapa de temperaturas por tipo de tarefa ─────────────────────────────────
TEMPERATURAS = {
    "tendencias": 0.4,      # Análise factual — mais conservador
    "ideias": 0.7,          # Criatividade equilibrada
    "prompts_imagem": 0.7,  # Criatividade visual
    "legendas": 0.6,        # Persuasão alinhada com fidelidade estrita ao tema
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
• Distribuição equilibrada entre os 4 CURSOS OFICIAIS: Apoio Escolar (Português e Matemática) e Tecnologia (Robótica e Programação).

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
• Slide 1 (Capa/thumbnail): Composição de thumbnail sobre foto real com texto curto de 3 a 7 palavras (Safe Zone 1:1 central). Fórmula obrigatória: [Sintoma Cotidiano] + [Provocação / Quebra de Expectativa]. Exemplos: "Tira 9 na prova, mas não aprendeu?", "A ilusão do rascunho em Matemática", "Por que ele trava na redação?", "Lê muito, mas não interpreta?".
• Slide 2 (Tensão): Aprofunda a dor da família + abre open loop instigante
• Slide 3 (Entrega): Revelação prática ou contexto que prepara a aplicação
• Slides 4 e 5 (Thumbnails de aplicação): Repetir a receita do slide 1 — foto real + texto curto de 3 a 8 palavras com gancho visual forte conectado ao método
• Slide 6 (Aplicação/Ponte): Como aplicar na prática através do método individualizado da Ensina Mais (entrega de alto valor pedagógico, sem quebra brusca para autopromoção)
• Slide 7 (Transformação/Prova): Caso real de aluno, superação ou depoimento acolhedor integrado à unidade física (Rua Coelho Lisboa, 783)
• Slide 8 (CTA + Loop Orgânico): Oferta obrigatória de aula experimental gratuita (em posts de tecnologia) ou avaliação pedagógica gratuita (em posts de apoio escolar) + convite para entrar em contato via WhatsApp (11) 94475-0009 + palavra-chave de comentário + gatilho de re-leitura ("volte ao slide X") ou envio por direct para o outro responsável

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
        {"slide": 8, "tipo": "CTA", "texto": "Comente PALAVRA_CHAVE ou chame no WhatsApp (11) 94475-0009 para agendar uma aula experimental (se tecnologia) ou avaliação pedagógica (se apoio escolar)..."}
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


# ═══════════════════════════════════════════════════════════════════════════════
# TONS DE VOZ (GHOSTWRITER)
# ═══════════════════════════════════════════════════════════════════════════════
# A persona CAROL continua sendo a base de todas as chamadas. O tom é a camada
# que ajusta o registro dela para um carrossel específico — é o que impede dois
# posts do mesmo eixo de saírem com a mesma voz.
#
# Cada tom muda o TEXTO. Ele nunca afrouxa as regras do motor: WhatsApp oficial,
# palavra-chave do eixo, ausência de personagens da Turma da Mônica e CTA
# honesto continuam obrigatórios em qualquer tom.

TONES: dict[str, dict[str, str]] = {
    "natural": {
        "rotulo": "Natural — mãe falando com mãe",
        "instrucao": """REGISTRO NATURAL (fala de mãe pra mãe no grupo do bairro):
• Frases de 8 a 14 palavras, como conversa, não como texto de campanha.
• Treat a família como iguais: "a gente", "seu filho", "quem já passou por isso".
• Um detalhe doméstico concreto por slide (copo no lugar errado, tarefa de
  última hora, discussão na mesa de jantar) — nunca abstrações como "lacuna" ou "base".
• PROIBIDO: "olha, pessoal", "quer saber", "gente", "vamos aprender", tom de
  palestra, jargão pedagógico, qualquer emoji no texto dos slides.""",
    },
    "didatico": {
        "rotulo": "Didático — o professor explica o passo",
        "instrucao": """REGISTRO DIDÁTICO (quem explica e sabe mostrar o caminho):
• Frases de 12 a 20 palavras, imperativo, na ordem em que a família vai fazer.
• Numere passos quando couber ("1) leia duas vezes", "2) grife o verbo").
• Cada slide entrega UMA coisa que dá para aplicar no mesmo dia.
• Justifique o porquê em uma frase, sem defender a teoria: o pai precisa ver o
  mecanismo, não acreditar nele.
• PROIBIDO: "é importante lembrar", "vamos aprender juntos", tom de reprovação
  ("você deveria ter..."), tom Motivacional vazio.""",
    },
    "storyteller": {
        "rotulo": "Storyteller — cena concreta que vira insight",
        "instrucao": """REGISTRO STORYTELLER (cena real que vira entendimento do problema):
• A primeira frase de cada slide é uma imagem sensorial e datável — o que dá
  para ver, ouvir ou sentir na cena. Duas a três frases por slide.
• O insight vem DEPOIS da cena, nunca antes: primeiro o pai se reconhece, depois
  entende.
• Use o contraste como estrutura: "não é X, é Y" — o equívoco comum da família
  entra em cena e é desmontado.
• PROIBIDO: clichê motivacional ("no fim, tudo se encaixa"), "imagina só",
  "era uma vez", metáfora de guerra, promessa de transformação.""",
    },
    "especialista": {
        "rotulo": "Especialista — voz de quem domina o tema",
        "instrucao": """REGISTRO ESPECIALISTA (quem domina o tema e o mercado):
• Frases de 12 a 18 palavras, com critério e dado: "por padrão de sala", "no
  Fundamental, a leitura...", "quem busca isso normalmente...".
• Assuma conhecimento prévio do leitor e não explique o óbvio.
• Nomeie o método e o critério: a família precisa saber em que base você mede.
• Números só com fonte real e verificável (INEP, PISA, SAEB, dados da própria
  unidade). Sem fonte, escreva em linguagem observacional, SEM número.
• PROIBIDO: "milagre", "revolucionário", "o melhor do mercado", superlativo
  sem lastro, argumento de autoridade.""",
    },
    "viral": {
        "rotulo": "Viral — gancho forte e entrega rápida",
        "instrucao": """REGISTRO VIRAL (interrompe o scroll e entrega antes de cansar):
• Gancho de capa com no máximo 12 palavras, direto na tensão do pai.
• Entregue o valor ANTES da explicação: o slide 2 já tem que servir para
  alguma coisa, não só contextualizar.
• Listas curtas e escaneáveis; uma ideia por linha.
• O CTA final é curto e sem construção de urgência falsa.
• PROIBIDO: clickbait que o carrossel não entrega, CAIXA ALTA, excesso de emoji,
  promessa de resultado ("você vai triplicar a nota"), prazo inventado.""",
    },
}

# Registro usado quando não há eixo conhecido ainda (ex.: Ideias antes de
# qualquer triagem). O eixo resolve depois, quando a ideia já tem dono.
TONES_PADRAO_POR_EIXO = TONES_POR_EIXO


def tom_eh_valido(tom: str) -> bool:
    """True se o tom existe em TONES ou é o pseudo-tom "automatico"."""
    return tom in TONES or tom == TONES_PADRAO


def resolver_tom(tom: str | None = None, eixo: str | None = None) -> str:
    """
    Resolve o tom efetivo.

    "automatico" vira o registro do eixo (Didático→didatico,
    Comportamental→storyteller, Diagnóstico→especialista). Sem eixo conhecido,
    cai em "natural", que é o registro de menor risco: conversa, não campanha.

    Tom desconhecido não é erro — vira "natural". Um selectbox sempre devolve
    valor válido, mas um payload vindo do NotebookLM ou de um JSON antigo pode
    não trazer o campo, e aí o certo é gerar mesmo assim.
    """
    tom = (tom or TONES_PADRAO).strip().lower()
    if tom == TONES_PADRAO:
        return TONES_POR_EIXO.get(eixo or "", "natural")
    return tom if tom in TONES else "natural"


# Lembrança das regras do motor que nenhum registro pode afrouxar. Aparece em
# todos os tons, inclusive no automático: sem essa âncora, o bloco automático
# valia como "escreva do seu jeito".
TOM_NAO_AFROUXA = (
    "As regras de segurança e de verdade do motor continuam valendo por cima de "
    "qualquer registro: nenhum personagem da Turma da Mônica, nenhum número sem "
    "fonte real, nenhuma promessa de resultado, nenhum exagero."
)

def bloco_tom(tom: str | None = None, eixo: str | None = None, variacao: bool = True) -> str:
    """
    Bloco de prompt que descreve o registro de voz pedido.

    `variacao` diz se a chamada gera um lote (ideias) ou uma peça só (legenda de
    um carrossel específico). No lote, "automatico" manda misturar o registro
    conforme o eixo de cada ideia — seis ideias com a mesma voz viram seis
    carrosséis com a mesma cara. Numa peça única, "automatico" resolve pelo eixo
    da peça, porque não existe mistura possível dentro de um texto só.
    """
    if (tom or TONES_PADRAO) == TONES_PADRAO and variacao:
        return (
            "\n\n─── \N{MICROPHONE} VOZ (TOM AUTOMÁTICO) ───\n"
            "Varie o registro entre as ideias conforme o eixo de cada uma: registro "
            "didático para o eixo Didático, registro de cena e roteirizado para o "
            "Comportamental, registro de especialista com critério para o "
            "Diagnóstico. Duas ideias do mesmo eixo com a mesma voz viram duas "
            "versões do mesmo post — varye.\n"
            f"{TOM_NAO_AFROUXA}\n"
        )
    efetivo = resolver_tom(tom, eixo)
    spec = TONES[efetivo]
    return (
        f"\n\n─── \N{MICROPHONE} VOZ ({spec['rotulo']}) ───\n"
        f"Este texto inteiro é escrito com este registro. {TOM_NAO_AFROUXA}\n"
        + f"{spec['instrucao']}\n"
    )





# ─── Feedback Loop de Métricas ────────────────────────────────────────────────
def build_ideas_prompt_with_feedback(tom: str | None = None) -> str:
    """
    Enriquece o prompt de geração de ideias com o aprendizado de performance real
    salvo no disco da unidade (data/metricas.json) e com o tom de voz escolhido.
    """
    try:
        from persistence import load_metricas
        metricas = load_metricas()
    except (ImportError, OSError, json.JSONDecodeError):
        # métricas são opcionais: sem arquivo/válido → usa prompt base
        metricas = []

    voz = bloco_tom(tom)

    if not metricas:
        return PROMPT_IDEIAS_BASE + voz

    posts_validos = [
        m for m in metricas
        if m.get("alcance", 0) > 0 and str(m.get("titulo", "")).strip()
    ]
    if not posts_validos:
        return PROMPT_IDEIAS_BASE + voz

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
    return PROMPT_IDEIAS_BASE + bloco + voz


def get_prompt_ideias(tom: str | None = None) -> str:
    """
    Prompt de ideias com feedback de métricas e tom de voz injetados.

    O tom entra no texto do prompt (e não na temperatura) porque ele não é
    creativity — é registro. A temperatura sobe um pouco em tons mais ousados,
    mas o peso do efeito vem da instrução.
    """
    return build_ideas_prompt_with_feedback(tom)


def get_prompt_legendas(tom: str | None = None, eixo: str | None = None) -> str:
    """
    Prompt de legendas com o tom de voz injetado.

    A legenda é o texto que o pai lê depois de salvar o carrossel, então ela
    carrega o registro com mais peso que o slide: é aqui que o tom "natural"
    mais aparece para o leitor.
    """
    if not tom_eh_valido(tom or TONES_PADRAO):
        tom = TONES_PADRAO
    return PROMPT_LEGENDAS + bloco_tom(tom, eixo, variacao=False)


# ═══════════════════════════════════════════════════════════════════════════════
# FIDELIDADE À REFERÊNCIA
# ═══════════════════════════════════════════════════════════════════════════════
# Sem referência visual, o modelo cai no visual padrão dele — que é exatamente
# o "cara de slop" que faz o carrossel parecer de qualquer educador. A referência
# já existe no motor (refs_catalog); o que faltava era dizer ao modelo o que
# fazer com ela.
#
# Os três níveis não mandam refazer a foto: a regra 2 dos prompts de imagem (a
# foto real é camada, não matéria-prima) vale acima de qualquer fidelidade.

FIDELIDADES: dict[str, str] = {
    "baixa": (
        "Use a referência só como INSPIRAÇÃO DE ATMOSFERA: pegue o clima, a "
        "sensação de luz e a paleta geral. Layout, enquadramento e tipografia "
        "são livres para seguir a composição descrita no slide."
    ),
    "media": (
        "Use a referência como GUIA DE IDENTIDADE: respeite a paleta, a "
        "tipografia, o grid e a hierarquia visual dela. Enquadramento e layout "
        "podem se adaptar ao conteúdo do slide, mas a peça precisa parecer da "
        "mesma família visual da referência."
    ),
    "alta": (
        "Replique a referência com alta fidelidade: mesma composição, mesmo "
        "enquadramento, mesma distribuição de peso no quadro, mesmo tratamento "
        "de luz. Troque APENAS o texto e o conteúdo. Se algo da referência "
        "depender de um detalhe que não pode ser reproduzido, preserve a "
        "aparência e a posição, nunca o detalhe."
    ),
}

FIDELIDADE_PADRAO = "media"


def fidelidade_eh_valida(fidelidade: str | None) -> bool:
    """True se o nível existe em FIDELIDADES."""
    return (fidelidade or "").strip().lower() in FIDELIDADES


def resolver_fidelidade(fidelidade: str | None = None, tem_imagem: bool = True) -> tuple[str, list[str]]:
    """
    Resolve a fidelidade efetiva e devolve (nivel, avisos).

    Alta fidelidade só existe se a referência chega ao Gemini como imagem. Com
    FLOW_FOTOS desligado o modelo recebe apenas o texto da cena, e não tem o que
    copiar — prometer "alta" ali seria propaganda enganosa. O downgrade é
    automático e avisado, porque degrade silencioso só é percebido no resultado.
    """
    avisos: list[str] = []
    nivel = (fidelidade or FIDELIDADE_PADRAO).strip().lower()
    if nivel not in FIDELIDADES:
        avisos.append(
            f"Fidelidade \"{nivel}\" não existe — usando \"{FIDELIDADE_PADRAO}\"."
        )
        nivel = FIDELIDADE_PADRAO

    if nivel == "alta" and not tem_imagem:
        avisos.append(
            "Fidelidade alta pede referência como imagem, mas nenhuma foto está "
            "sendo anexada (FLOW_FOTOS desligado). Baixando para média — o modelo "
            "recebeu só o texto da cena."
        )
        nivel = "media"
    return nivel, avisos


def bloco_fidelidade(fidelidade: str | None = None, tem_imagem: bool = True) -> str:
    """
    Instrução de fidelidade injetada no prompt de imagem.

    Sempre seguida da regra que não cede: a foto real dos slides 1, 4, 5 e 7 é
    intocável. Fidelidade alta não é permissão para redesenhar o rosto de um
    aluno ou a fachada da escola.
    """
    nivel, _avisos = resolver_fidelidade(fidelidade, tem_imagem)
    return (
        f"\n\n─── \N{FRAME WITH PICTURE} FIDELIDADE À REFERÊNCIA ({nivel.upper()}) ───\n"
        f"{FIDELIDADES[nivel]}\n"
        "Esta instrução NUNCA sobrepõe a regra da foto real: nos slides 1, 4, 5 e 7 "
        "a fotografia é camada intocável e recebe apenas composição tipográfica "
        "por cima. Fidelidade alta governa o resto do frame — o que não estava na "
        "foto.\n"
    )


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
    faltam_oferta = 0
    for ideia in ideias:
        slides = ideia.get("slides_sugeridos", [])
        if slides:
            ultimo = slides[-1].get("texto", "")
            if "94475-0009" not in ultimo:
                faltam_wpp += 1
            curso_ou_tema = f"{ideia.get('tema', '')} {ideia.get('curso', '')} {ideia.get('titulo', '')}".lower()
            is_tec = any(k in curso_ou_tema for k in ("robót", "robot", "prog", "tecnol", "game", "cód", "cod"))
            ultimo_low = ultimo.lower()
            if is_tec:
                if not any(k in ultimo_low for k in ("aula experimental", "experimental")):
                    faltam_oferta += 1
            elif any(k in curso_ou_tema for k in ("matemát", "matemat", "portugu", "redação", "redacao", "apoio", "reforço", "reforco", "escola")):
                if not any(k in ultimo_low for k in ("avaliação", "avaliacao", "diagnóstic", "diagnostic")):
                    faltam_oferta += 1
    if faltam_wpp > 0:
        warnings.append(f"⚠️ {faltam_wpp} ideia(s) estão sem o número de WhatsApp oficial no slide final.")
    if faltam_oferta > 0:
        warnings.append(f"⚠️ {faltam_oferta} ideia(s) com slide final sem a oferta correta (aula experimental para tecnologia ou avaliação pedagógica para apoio escolar).")

    return warnings


# ─── Validador de Prompts de Imagem ──────────────────────────────────────────
# Personagens da Turma da Mônica (marca registrada — reservados à franqueadora).
# A MARCA "Turma da Mônica" no nome do logo é permitida e removida antes da busca.
_PERSONAGENS_MONICA = (
    "mônica", "monica", "cebolinha", "cascão", "cascao",
    "magali", "franjinha", "nimbus", "bidu",
    "chico bento", "pit lelé", "pit lele", "anabela", "aurélia", "aurelia",
)
_MARCA_MONICA = (
    "ensina mais turma da mônica", "ensina mais turma da monica",
    "turma da mônica", "turma da monica",
)


def personagens_no_texto(texto: str) -> tuple[str, ...]:
    """Nomes de personagens da Turma da Mônica citados em `texto`.

    A marca do logo ("Ensina Mais Turma da Mônica") é permitida e removida
    antes da busca. Usado pelo validador E pelo pós-processamento.
    """
    livre = (texto or "").lower()
    for marca in _MARCA_MONICA:
        livre = livre.replace(marca, " ")
    return tuple(p for p in _PERSONAGENS_MONICA if p in livre)
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

# Padrões de layout genérico proibidos nos slides thumbnail (foto real).
# Fonte única: prompts.py exporta, batch_engine.py consome (antes havia duas
# listas ligeiramente diferentes nos dois arquivos).
PADROES_PROIBIDOS_FOTO = (
    "off-white background",
    "floating white card",
    "soft background",
)

# Cláusula obrigatória em TODO prompt_en (regra 7 — personagens).
CLAUSULA_SEM_PERSONAGENS = "no cartoon characters"

# Cláusula de fachada intocável (regra 12) — obrigatória em TODO prompt_en cuja
# "referencias" inclui "fachada": a foto de referência entra como está, o Flow
# só compõe legenda/card por cima.
FRASE_FACHADA = (
    "Use the provided reference photo of the school facade exactly as-is as the "
    "full-bleed background — do not regenerate, redraw, restyle, recolor, or "
    "replace any part of the photograph. Compose ONLY design elements on top: "
    "text overlays, testimonial cards, and logo badge. The photo itself is "
    "untouched, like a professional Photoshop composite."
)

# Cláusula para slides com foto real (regras 1, 4, 5) — composição sobre foto
# de referência, não geração de cena. A foto entra como camada fixa.
FRASE_FOTO_REAL = (
    "Use the provided reference photo exactly as-is as the full-bleed background "
    "photograph — do not regenerate, redraw, restyle, or replace the scene. "
    "Compose ONLY typographic overlays and minimal graphic elements on top of "
    "the photograph, like a professional photo-editor would in Photoshop. The "
    "photograph itself must remain untouched and photorealistic."
)


def cor_eh_valida(cor) -> bool:
    """True se `cor` é um hex CSS seguro (#RGB/#RRGGBB) para style/HTML."""
    return isinstance(cor, str) and bool(_HEX_RE.fullmatch(cor.strip()))


# Números que carregam pretensão de dado. "5 questões" é conteúdo; "80%",
# "3x mais rápido" e "milhares" são estatística — e estatística sem fonte é
# mentira, mesmo quando soa verdadeira.
_RE_NUMERO_DADO = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:%|por\s?cento|x\b|vezes|milh[õo]es|milhares|\bmil\b|\bmi\b|\bbi\b)",
    re.IGNORECASE,
)

# Marcas de fonte: agency's pública, ou a experiência da própria unidade.
_MARCAS_FONTE = (
    "ibge", "inep", "pisa", "saeb", "iesl", "pesquisa abc", "cncd", "data senac",
    "unesp", "usp", "ufrgs", "folha", "estudo", "pesquisa", "dados do inei",
    "segundo o", "de acordo com",
)

# Marcas de observação própria: a unidade pode falar do que viu, desde que diga
# que é observação e não estatística.
_MARCAS_OBSERVACAO = (
    "na nossa sala", "na nossa unidade", "na unidade", "em nossa sala",
    "com os alunos que atendemos", "com as famílias que", "ano passado na unidade",
    "na prática", "no dia a dia da sala", "a gente observa", "nossas aulas",
    "dados da unidade", "nosso acompanhamento",
)


def texto_tem_fonte(texto: str) -> bool:
    """True se o texto cita fonte de verdade ou se apresenta como observação."""
    low = (texto or "").lower()
    if any(m in low for m in _MARCAS_FONTE):
        return True
    return any(m in low for m in _MARCAS_OBSERVACAO)


def numeros_sem_fonte(texto: str) -> list[str]:
    """Lista os números com aparência de dado que não têm fonte no texto."""
    achados = [m.group(0).strip() for m in _RE_NUMERO_DADO.finditer(texto or "")]
    if not achados:
        return []
    if texto_tem_fonte(texto):
        return []
    return achados


def validate_prompts(dados: dict, ideia: dict | None = None) -> list[str]:
    """
    Valida a saída da geração de prompts de imagem contra as regras do prompt:
    - 8 slides com prompt_en, prompt_pt e text_overlay preenchidos
    - prompt_en declara "text overlay in Brazilian Portuguese" exatamente UMA
      vez (regra 5) — repetir a instrução confunde o modelo
    - text_overlay ≤ 15 palavras (regra 4), sem a tag de navegação/"Swipe"
    - tag "Mova para o próximo ➔" no prompt_en dos slides 1-7 e AUSENTE no 8
      (regra 6 — a tag é gerada pelo Flow, não é camada separada aqui)
    - cláusula "no cartoon characters" em todo prompt_en (regra 7)
    - nenhum personagem da Turma da Mônica em NENHUM campo (prompt_en,
      prompt_pt, text_overlay, estilo, base_prompt, dicas_gerais) — a marca
      do logo é permitida
    - referências por slide presentes e válidas no catálogo refs/catalogo.json
      (regra 11); slides 1, 4, 5 e 7 precisam de cena fotográfica real;
      slide 7 deve incluir "fachada"
    - slides com "fachada" nas referências com a cláusula de foto intocável
      (regra 12 — a foto de referência não é modificada, só recebe legenda)
    - slides 1, 4 e 5 com foto real (prompt_en começa com "authentic school
      photo", sem padrões genéricos) — regras 2/11
    - último slide com o WhatsApp (CTA inviolável)
    - com a ideia de origem: overlay deriva do texto aprovado do slide (fidelidade)
    - paleta com valores hex válidos (swatch do app só pinta hex — safety anti-XSS)
    - base_prompt presente, com os hexes da marca e sem texto de slide específico
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
        # base_prompt não pode embutir texto de um slide específico
        bp_low = base_prompt.lower()
        for slide in slides:
            texto_slide = (slide.get("text_overlay") or "").strip()
            if len(texto_slide.split()) >= 3 and texto_slide.lower() in bp_low:
                avisos.append(
                    f'⚠️ base_prompt contém o texto do slide {slide.get("slide_num", "?")} — '
                    "deve valer igual para as 8 lâminas (regra 9)."
                )
                break
        if TAG_NAVEGACAO.lower() in bp_low:
            avisos.append(
                "⚠️ base_prompt contém a tag de navegação — ela é específica de cada lâmina (regra 9)."
            )

    # Personagens da Turma da Mônica no estilo compartilhado (marca do logo ok)
    for campo in ("base_prompt", "dicas_gerais"):
        for nome in personagens_no_texto(dados.get(campo) or ""):
            avisos.append(
                f'⚠️ {campo} menciona o personagem "{nome}" — proibido '
                "(marca registrada; só o logo é permitido)."
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
        pen_low = pen.lower()
        overlay = (slide.get("text_overlay") or "").strip()
        overlay_low = overlay.lower()
        is_ultimo = snum == 8

        if not pen:
            avisos.append(f"⚠️ Slide {snum}: prompt_en vazio.")
            continue
        if not (slide.get("prompt_pt") or "").strip():
            avisos.append(f"⚠️ Slide {snum}: prompt_pt vazio — descreva o slide em PT-BR.")
        if not overlay:
            avisos.append(f"⚠️ Slide {snum}: text_overlay vazio.")

        # Regra 3b — número com cara de dado e sem fonte. É o aviso que mais
        # importa aqui: número inventado é o que faz o post parecer genérico e
        # destrói a confiança do pai quando ele pesquisa.
        for onde, trecho in (("text_overlay", overlay), ("prompt_pt", slide.get("prompt_pt") or "")):
            sem_fonte = numeros_sem_fonte(trecho)
            if sem_fonte:
                avisos.append(
                    f"⚠️ Slide {snum}: {onde} usa {', '.join(sem_fonte)} sem citar fonte "
                    "(regra 3b). Reescreva em linguagem observacional, sem número, ou "
                    "cite a fonte no próprio texto."
                )
        # Regra 5 — cláusula de idioma do overlay: exatamente UMA ocorrência
        n_clausulas = len(
            re.findall(r"in\s+Brazilian\s+Portuguese\s*:\s*['\"]", pen, re.IGNORECASE)
        )
        if n_clausulas == 0:
            avisos.append(f'⚠️ Slide {snum}: prompt_en sem a cláusula "text overlay in Brazilian Portuguese" (regra 5).')
        elif n_clausulas > 1:
            avisos.append(
                f"⚠️ Slide {snum}: prompt_en repete a instrução de texto sobreposto "
                f"({n_clausulas} cláusulas) — mantenha apenas uma (regra 5)."
            )
        n_palavras = len(overlay.split())
        if n_palavras > 15:
            avisos.append(f"⚠️ Slide {snum}: text_overlay com {n_palavras} palavras (máximo 15) — regra 4.")

        # ── Tag de navegação: no prompt_en (1-7), nunca no overlay, nada no 8 ──
        if "arraste para o lado" in overlay_low or TAG_NAVEGACAO.lower() in overlay_low:
            avisos.append(
                f'⚠️ Slide {snum}: a tag "{TAG_NAVEGACAO}" não deve estar no text_overlay — '
                "ela é elemento próprio do prompt_en (regra 6)."
            )
        if "swipe" in overlay_low:
            avisos.append(f'⚠️ Slide {snum}: use "{TAG_NAVEGACAO}" em PT-BR, nunca "Swipe".')
        if not is_ultimo:
            if "arraste para o lado" in pen_low:
                avisos.append(f'⚠️ Slide {snum}: use "{TAG_NAVEGACAO}", nunca "Arraste para o lado" (regra 6).')
            if "swipe" in pen_low:
                avisos.append(f'⚠️ Slide {snum}: use "{TAG_NAVEGACAO}" em PT-BR, nunca "Swipe" (regra 6).')
            if TAG_NAVEGACAO.lower() not in pen_low:
                avisos.append(
                    f'⚠️ Slide {snum}: prompt_en sem a tag "{TAG_NAVEGACAO}" no canto inferior direito '
                    "(regra 6 — o Flow gera a tag junto com a imagem)."
                )
        else:
            if TAG_NAVEGACAO.lower() in pen_low:
                avisos.append("⚠️ Slide 8 (CTA): prompt_en não deve ter a tag de navegação (regra 6).")

        # Campo JSON da tag (fonte de verdade para o app/export)
        tag_json = slide.get("tag_navegacao")
        if tag_json is None:
            avisos.append(f'⚠️ Slide {snum}: campo "tag_navegacao" ausente (regra 6).')
        else:
            esperada = "" if is_ultimo else TAG_NAVEGACAO
            if str(tag_json) != esperada:
                avisos.append(
                    f'⚠️ Slide {snum}: "tag_navegacao" deveria ser '
                    f'{"string vazia" if esperada == "" else f"{esperada!r}"} (regra 6).'
                )

        # ── Regra 7: cláusula anti-personagem obrigatória em todo prompt_en ──
        if CLAUSULA_SEM_PERSONAGENS not in pen_low:
            avisos.append(
                f'⚠️ Slide {snum}: prompt_en sem "{CLAUSULA_SEM_PERSONAGENS}" (regra 7).'
            )

        if snum in {1, 4, 5}:
            if slide.get("usa_foto_real") is not True:
                avisos.append(f"⚠️ Slide {snum}: deve usar uma foto real da unidade (usa_foto_real: true) — regra 2.")
            if slide.get("tipo_foto") not in CENAS_FOTO:
                avisos.append(
                    f"⚠️ Slide {snum}: tipo_foto deve ser uma cena fotográfica real do catálogo "
                    f"({', '.join(CENAS_FOTO)})."
                )
            is_foto_real = (
                FRASE_FOTO_REAL.lower() in pen_low
                or "use the provided reference photo" in pen_low
            )
            if not is_foto_real:
                avisos.append(
                    f'⚠️ Slide {snum}: prompt_en sem cláusula de composição '
                    'sobre foto de referência (FRASE_FOTO_REAL) — regra 2.'
                )
            # Detectar "Authentic school photo" antigo (a IA gera a foto em vez de compor)
            if "authentic school photo" in pen_low and not is_foto_real:
                avisos.append(
                    f'⚠️ Slide {snum}: prompt_en contém "Authentic school photo" — '
                    "use FRASE_FOTO_REAL para composição sobre a foto de referência, não geração de cena (regra 2)."
                )
            # Detectar padrões proibidos que indicam layout genérico (sem foto real)
            for padrao in PADROES_PROIBIDOS_FOTO:
                if padrao in pen_low:
                    avisos.append(
                        f'⚠️ Slide {snum}: prompt_en contém "{padrao}" — '
                        "slides thumbnail (1, 4, 5) devem ter foto real como fundo, não layout genérico (regra 2)."
                    )
                    break
            if len(overlay.split()) > 8:
                avisos.append(f"⚠️ Slide {snum}: thumbnail deve ter texto curto de até 8 palavras.")

        # ── Regra 11: referências de imagem por slide (catálogo refs/catalogo.json) ──
        refs = slide.get("referencias")
        if not isinstance(refs, list) or not refs:
            avisos.append(f'⚠️ Slide {snum}: "referencias" vazia — sugira ao menos 1 cena do catálogo (regra 11).')
        else:
            desconhecidas = [r for r in refs if not cena_valida(r)]
            if desconhecidas:
                avisos.append(
                    f"⚠️ Slide {snum}: referência fora do catálogo: "
                    + ", ".join(repr(r) for r in desconhecidas)
                    + f" — válidas: {', '.join(chaves_cenas()) or 'catálogo indisponível'} (regra 11)."
                )
            if snum in {1, 4, 5, 7} and not any(r in CENAS_FOTO for r in refs if isinstance(r, str)):
                avisos.append(
                    f"⚠️ Slide {snum}: precisa referenciar uma foto real da unidade "
                    f"(ex.: {', '.join(CENAS_FOTO[:3])}) — regra 11."
                )
            if snum == 7 and "fachada" not in refs:
                avisos.append('⚠️ Slide 7: "referencias" deve incluir "fachada" (regra 11).')

        # ── Regra 12: fachada intocável — foto de referência só recebe legenda ──
        if isinstance(refs, list) and "fachada" in refs:
            if FRASE_FACHADA.lower() not in pen_low:
                avisos.append(
                    f'⚠️ Slide {snum}: prompt_en sem a cláusula de fachada intocável '
                    '("Use the reference facade photo exactly as provided") — a foto '
                    "de referência entra como está (regra 12)."
                )

        # Personagens da Turma da Mônica (a marca do logo é permitida) —
        # vale para QUALQUER campo do slide, não só prompt/overlay
        for campo in ("prompt_en", "prompt_pt", "text_overlay", "estilo"):
            valor = slide.get(campo) or ""
            for nome in personagens_no_texto(str(valor)):
                avisos.append(
                    f'⚠️ Slide {snum}: menção ao personagem "{nome}" em "{campo}" — '
                    "proibido (marca registrada)."
                )

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
                        f"({inter:.0%} de palavras em comum) — revise a fidelidade ao roteiro (regra 8)."
                    )

    # CTA inviolável: último slide com o WhatsApp e oferta correspondente
    ultimo = slides[-1]
    ultimo_txt = f"{ultimo.get('text_overlay', '')} {ultimo.get('prompt_en', '')}"
    if "94475" not in ultimo_txt:
        avisos.append("⚠️ Último slide sem o WhatsApp (11) 94475-0009 no CTA.")
    if ideia:
        curso_ou_tema = f"{ideia.get('tema', '')} {ideia.get('curso', '')} {ideia.get('titulo', '')}".lower()
        is_tec = any(k in curso_ou_tema for k in ("robót", "robot", "prog", "tecnol", "game", "cód", "cod"))
        is_apoio = any(k in curso_ou_tema for k in ("matemát", "matemat", "portugu", "redação", "redacao", "apoio", "reforço", "reforco", "escola"))
        ultimo_all = f"{ultimo.get('text_overlay', '')} {ultimo.get('prompt_en', '')} {ultimo.get('prompt_pt', '')}".lower()
        if is_tec and not any(k in ultimo_all for k in ("aula experimental", "experimental", "trial class")):
            avisos.append("⚠️ Último slide (CTA): carrossel de tecnologia deve oferecer aula experimental (regra 13).")
        elif is_apoio and not any(k in ultimo_all for k in ("avaliação", "avaliacao", "diagnóstic", "diagnostic", "assessment")):
            avisos.append("⚠️ Último slide (CTA): carrossel de apoio escolar deve oferecer avaliação pedagógica (regra 13).")

    return avisos


# ─── Prompts de Imagem ───────────────────────────────────────────────────────
PROMPT_PROMPTS_IMAGEM = (
    f"""Crie a estrutura visual e os layouts para um carrossel educativo de 8 lâminas (1080 x 1350 px, 4:5 vertical).

─── PADRÃO VISUAL E IDENTIDADE DA MARCA (fonte única: padroesVisuais.txt — não duplique) ───
{PADRAO_VISUAL}

─── ATIVOS FOTOGRÁFICOS REAIS (catálogo único: refs/catalogo.json) ───
Estas são as ÚNICAS fotos reais da unidade que podem ser sugeridas como referência. Chave = valor do campo "referencias" de cada slide:
{texto_catalogo_para_prompt()}
Nada fora desta lista existe como ativo: nunca cite fotos genéricas de banco de imagens nem cenas inventadas.

─── ESTRUTURA POR TIPO DE SLIDE (tipos canônicos iguais aos do roteiro: 1 Capa, 2 Segunda Capa, 3-5 Entrega, 6 Ponte, 7 Prova, 8 CTA — com a referência típica de cada lâmina) ───
• SLIDE 1 (Capa / Thumbnail de abertura — FOTO REAL OBRIGATÓRIA; referência típica: "fachada" ou "recepcao_unidade"): composição profissional SOBRE a foto de referência da unidade (como um designer faria no Photoshop). A foto real entra como camada de fundo full-bleed, intacta e photorealistic — NÃO é regenerada nem recriada. Sobre ela, componha: texto curto de 3-8 palavras em tipografia geométrica de impacto (Azul Brand #007799, com marca-texto amarelo #FFC20E), legível no celular, centralizado na Safe Zone 1:1 (1080×1080 px). Selo do logo no rodapé. O prompt_en DEVE conter a cláusula FRASE_FOTO_REAL — NUNCA "Authentic school photo of..." nem fundo genérico/gerado por IA.
• SLIDE 2 (Segunda Capa; referência típica: a cena de atividade que traduz o tema — ex.: "alunos_robotica" para um carrossel de robótica, "aluno_programacao" para programação, "alunos_apoio" para apoio escolar): Fundo contrastante em Azul Brand (#007799 / #0084B4), tipografia branca e amarelo vibrante, transições orgânicas em curva — funciona como capa alternativa no feed.
• SLIDE 3 (Entrega; referência típica: a cena da disciplina do tema, ex.: "alunos_apoio", "alunos_robotica", "aluno_programacao"): Cards disciplinares flutuantes (branco puro #FFFFFF com toques pastel da disciplina: azul claro, laranja, coral ou verde lima), diagramas, passos com ícones minimalistas em círculos coloridos.
• SLIDE 4 (Entrega — Thumbnail de aplicação — FOTO REAL OBRIGATÓRIA; referência típica: "alunos_robotica" ou "alunos_apoio"): MESMA RECEITA DO SLIDE 1 — composição profissional sobre a foto de referência (camada de fundo intacta) + texto curto de 3-8 palavras compondo sobre a foto. O prompt_en DEVE conter a cláusula FRASE_FOTO_REAL.
• SLIDE 5 (Entrega — Thumbnail de aplicação — FOTO REAL OBRIGATÓRIA; referência típica: "aluno_programacao" ou a cena da disciplina do tema): MESMA RECEITA DO SLIDE 1 — composição profissional sobre a foto de referência (camada de fundo intacta) + texto curto de 3-8 palavras compondo sobre a foto. O prompt_en DEVE conter a cláusula FRASE_FOTO_REAL.
• SLIDE 6 (Ponte; referência típica: "alunos_robotica", "alunos_apoio", "equipe" ou "laboratorio"): Grid com fotos reais dos alunos em molduras arredondadas (16px) e sombras suaves + texto sobre metodologia individualizada (#1E293B).
• SLIDE 7 (Prova / Escola Real; referência obrigatória: "fachada", podendo somar "equipe"): Composição profissional SOBRE a foto da fachada da Rua Coelho Lisboa, 783. A foto entra como camada de fundo full-bleed, intacta — proibido redesenhar, reestilizar, recolorir ou regenerar. Sobre ela: cartão de depoimento/prova social com bordas arredondadas + legenda. O prompt_en DEVE conter a cláusula FRASE_FACHADA.
• SLIDE 8 (CTA; referência típica: "logo"): Fundo suave, botão pill em Verde Ação (#58B947) oferecendo SEMPRE uma aula experimental gratuita (em posts de tecnologia: Robótica ou Programação) ou avaliação pedagógica gratuita (em posts de apoio escolar: Português ou Matemática) e pedindo para entrar em contato via WhatsApp oficial (11) 94475-0009, ícones minimalistas de salvar + compartilhar DM.

─── REGRAS DO PROMPT ───
1. prompt_en em INGLÊS, text_overlay em PORTUGUÊS DO BRASIL.
2. ⛔ SLIDES 1, 4 e 5 — COMPOSIÇÃO SOBRE FOTO REAL (REGRA PRIORITÁRIA, leia antes de qualquer outra):
   Esses 3 slides são composições profissionais SOBRE a foto de referência da unidade (estilo Photoshop/editing). A foto real entra como camada de fundo full-bleed, intacta e photorealistic — NÃO é regenerada, recriada, reestilizada nem substituída pela IA. O prompt_en desses slides DEVE OBRIGATORIAMENTE:
   (a) CONTER a cláusula FRASE_FOTO_REAL que instrui o modelo a usar a foto como camada fixa e compor elementos por cima;
   (b) Descrever a composição: o que vai SOBRE a foto (texto, badge do logo, elementos gráficos mínimos);
   (c) Incluir o texto curto (3-8 palavras) como overlay tipográfico SOBRE a foto;
   (d) Marcar "usa_foto_real": true e "tipo_foto" com UMA cena fotográfica do catálogo (ex.: "recepcao_unidade", "alunos_robotica", "aluno_programacao", "alunos_apoio") no JSON.
   ⛔ PROIBIDO nos slides 1, 4 e 5: "Authentic school photo of..." (a IA recria a cena), "soft off-white background", "floating white card", "soft background", fundo liso genérico ou cena 100% gerada por IA. Esses elementos são exclusivos dos slides 2, 3, 6, 7 e 8.
   ✅ CORRETO (slide 1): "Use the provided reference photo exactly as-is as the full-bleed background photograph — do not regenerate, redraw, restyle, or replace the scene. Compose ONLY typographic overlays and minimal graphic elements on top of the photograph, like a professional photo-editor would in Photoshop. The photograph itself must remain untouched and photorealistic. Bold Brand Blue #007799 text overlay in Brazilian Portuguese: 'Seu filho programa o futuro dele.' No cartoon characters."
   ❌ ERRADO (slide 1): "Authentic school photo of students working on robotics at a yellow table..." (a IA gera uma foto nova em vez de compor sobre a referência)
3. ESTÉTICA DOS SLIDES 2, 3, 6, 7 e 8 (NÃO se aplica aos slides 1, 4 e 5 — eles usam foto real, veja regra 2). No prompt_en desses slides: descreva explicitamente a estética (modern friendly geometric sans-serif typography, centered elements respecting a 1:1 square safe zone for Instagram grid preview, floating white cards with 16-24px rounded corners, subtle diffuse shadows, soft off-white background #F7F9FF, Brand Blue #007799 headers, Action Green #58B947 pill buttons for CTAs, vibrant yellow/orange #FFC20E highlights, pastel cards, organic curve transitions, minimalist line icons in colored circles).
4. text_overlay: máximo 15 palavras, fonte bold, legível em celular.
5. No prompt_en, inclua EXATAMENTE UMA vez, copiada sem paráfrase: "text overlay in Brazilian Portuguese: [TEXTO]" — nunca troque o início por "highlight/overlay ... in Brazilian Portuguese" e nunca repita a instrução de texto sobreposto na mesma lâmina (uma única vez, sempre com o mesmo texto de text_overlay).
6. TAG DE NAVEGAÇÃO — GERADA JUNTO COM A IMAGEM: o prompt_en dos slides 1 a 7 DEVE incluir uma frase em inglês instruindo o texto discreto no canto inferior direito, exatamente neste formato: "In the bottom right corner, a small discreet text in Brazilian Portuguese says '{TAG_NAVEGACAO}'." A tag é PT-BR e nunca é traduzida (proibido "Swipe" e "Arraste para o lado"), NUNCA faz parte do text_overlay e NUNCA aparece no slide 8. No campo "tag_navegacao" use exatamente "{TAG_NAVEGACAO}" nos slides 1 a 7 e uma string vazia no slide 8.
7. PERSONAGENS — REGRA DUPLA: PERMITIDO (fotográfico) referenciar o logo oficial "Ensina Mais Turma da Mônica" e o painel real da fachada — use como referência fiel, não os recrie. PROIBIDO (gerado): em todo prompt_en declare "no cartoon characters — generic minimalist line-art icons only" e NUNCA gere nem mencione personagens (Mônica, Cebolinha, Cascão, Magali, Franjinha, Nimbus, Bidu, Chico Bento, Pit Lelé, Anabela, Aurélia ou qualquer outro) — em NENHUM campo, nem em português nem em inglês (prompt_en, prompt_pt, text_overlay, estilo, base_prompt, dicas_gerais): se o tema pedir personagem, descreva alunos genéricos. A marca no nome do logo é permitida; os personagens, nunca.
8. FIDELIDADE AO ROTEIRO: o contexto traz a lista "Slides" com o campo "texto" de cada lâmina aprovada. Cada text_overlay DEVE ser um resumo de até 15 palavras DO TEXTO DO SLIDE CORRESPONDENTE (mesmo gancho e mensagem) — NUNCA invente frases que não estejam no roteiro.
9. BASE_PROMPT PARA CONSISTÊNCIA: gere também o campo "base_prompt" (em inglês) com APENAS o estilo compartilhado das 8 lâminas — fundo, tipografia, paleta com os hexes #007799, #58B947 e #FFC20E, bordas, sombras, ícones e transições. SEM texto sobreposto e SEM elementos de um slide específico: tem que valer igual para todas as lâminas.
10. "dicas_gerais" — ESPECÍFICO DESTE CARROSSEL: registre só o que muda de uma geração para outra: a ordem das 8 lâminas, qual referência de foto usar em cada uma e algum cuidado particular do tema. A receita de coesão (gerar o SLIDE 1 primeiro e usá-lo como imagem de referência/estilo para os slides 2 a 8 no Google Flow) é FIXA e vem do próprio app — não repita aqui.
11. REFERÊNCIA DE IMAGEM POR SLIDE (campo "referencias"): para CADA slide escolha 1 ou 2 chaves do catálogo de fotos acima — é o que o usuário vai anexar como imagem de referência no Google Flow para gerar aquela lâmina. Regras:
   (a) slides 1, 4, 5 e 7: OBRIGATORIAMENTE ≥1 cena fotográfica real da unidade (fachada, recepcao_unidade, equipe, alunos_robotica, aluno_programacao, alunos_apoio, laboratorio) — nunca só "logo";
   (b) slide 7: deve incluir "fachada";
   (c) a cena deve traduzir o CONTEÚDO do slide (robótica → "alunos_robotica"; programação → "aluno_programacao"; apoio/reforço → "alunos_apoio"; identidade/prova → "fachada");
   (d) use EXATAMENTE as chaves do catálogo, em minúsculas — qualquer valor fora da lista é inválido.
12. FACHADA INTOCÁVEL: quando "fachada" estiver nas "referencias" de um slide (sempre no 7), o prompt_en DEVE conter exatamente esta cláusula: "{FRASE_FACHADA}" — a foto de referência NUNCA é modificada, só recebe legenda/cartão por cima.
13. SLIDE 8 (CTA FINAL): O Slide final (text_overlay e prompt_en) DEVE SEMPRE oferecer uma aula experimental gratuita (em posts de tecnologia: Robótica ou Programação) ou avaliação pedagógica gratuita (em posts de apoio escolar: Português ou Matemática) e pedir para entrar em contato via WhatsApp da unidade (11) 94475-0009.

─── DIRETRIZES DE PROMPT CRAFT — GOOGLE FLOW / IMAGEFX / IMAGEN ───
14. Todo prompt_en é lido por um modelo de imagem do ecossistema Google. Construa cada prompt_en como UMA descrição em inglês, direta e coesa, cobrindo os cinco eixos abaixo (vírgulas ou frases curtas, sem prosa vaga):
   (a) SUBJECT — sujeito principal com características físicas, vestuário, expressão e ação concretos; nos slides 1, 4, 5 e 7 o "sujeito" é a própria foto de referência, intocada (ver regra 2);
   (b) ENVIRONMENT / SETTING — cenário, atmosfera, elementos contextuais e profundidade de campo;
   (c) ART STYLE & MEDIUM — meio e óptica concretos: fotografia (ex.: "35mm lens, f/1.8"), render 3D (ex.: "Unreal Engine 5 render, Octane render") ou arte gráfica; sempre coerente com o padrão visual da marca;
   (d) LIGHTING & COLOR — tipo de luz (ex.: "golden hour light", "soft diffused daylight", "volumetric lighting") e paleta dominante com os hexes da marca;
   (e) COMPOSITION — enquadramento (ex.: "wide shot", "close-up", "rule of thirds", "low angle", "1:1 safe zone centered").
15. ⛔ BUZZWORDS GENÉRICAS (filtro de qualidade): não use "photorealistic", "4K", "hyperrealistic", "ultra detailed", "high quality", "masterpiece" nem advérbios vazios como atalho de estilo — no lugar, descreva textura, iluminação e óptica concretas. Exceção única: as cláusulas FRASE_FOTO_REAL e FRASE_FACHADA, transcritas literalmente, mantêm o termo "photorealistic" porque ali ele significa "foto intocada", não estilo.
16. Se o estilo não vier definido pelo padrão visual, adote o que melhor valoriza o conceito: fotografia para cenas reais da unidade e arte gráfica/editorial para diagramas e cards — nunca uma estética genérica de banco de imagens."""
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
      "usa_foto_real": true,
      "tipo_foto": "fachada",
      "referencias": ["fachada", "logo"],
      "tag_navegacao": "Mova para o próximo ➔"
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


# ─── Exportação da série para o Google Flow ─────────────────────────────────
DICAS_SERIE_FLOW = """Como gerar as 8 lâminas no Google Flow:
1. Gere primeiro o SLIDE 1: cole o prompt dele e anexe as fotos de referência indicadas. O Flow vai compor os elementos de design SOBRE a foto — a foto entra como camada fixa.
2. Nos slides 2 a 8, anexe também a imagem gerada do slide 1 junto com as referências daquela lâmina — é ela que mantém estilo, tipografia e paleta coesos no carrossel.
3. Use só as fotos do catálogo (refs/) como referência — nada de banco de imagens.
4. Confira o canto inferior direito: a tag "Mova para o próximo ➔" aparece nos slides 1 a 7 e fica fora do slide 8.
5. O app não gera imagem: baixe cada lâmina em 1080x1350 px (4:5) e monte o carrossel na ordem 1→8.
6. slides 1, 4 e 5: a foto de referência é a camada de fundo — o Flow compõe tipografia e elementos gráficos por cima, como um editor profissional faria."""


def formatar_txt_prompts(dados: dict) -> str:
    """Export .txt: SOMENTE os 8 prompts, um bloco por lâmina separado por
    linha em branco — é o formato que a extensão de automação carrega.

    Sem título, base prompt, dicas, cabeçalhos "## SLIDE", referências ou
    linhas "Text overlay (PT-BR)": apenas o prompt_en de cada lâmina.
    """
    if not isinstance(dados, dict):
        return ""
    blocos = [
        (s.get("prompt_en") or "").strip()
        for s in dados.get("slides") or []
        if isinstance(s, dict) and (s.get("prompt_en") or "").strip()
    ]
    if not blocos:
        return ""
    return "\n\n".join(blocos) + "\n"


# ─── Legendas com Copywriting Estruturado ────────────────────────────────────
PROMPT_LEGENDAS = """Com base no carrossel abaixo, escreva 3 OPÇÕES DE LEGENDA DE ALTO IMPACTO para o Instagram.

─── ⚠️ REGRA CRÍTICA DE COERÊNCIA TEMÁTICA (FIDELIDADE ABSOLUTA AO CARROSSEL) ───
• A legenda DEVE tratar EXCLUSIVAMENTE do curso, tema e conteúdo das lâminas do carrossel fornecido.
• Se o carrossel for de Matemática/Apoio Escolar, aborde exclusivamente dificuldades de matemática, raciocínio lógico, interpretação de enunciados e provas escolares. É TERMINANTEMENTE PROIBIDO falar de robótica, programação ou tempo de telas se o carrossel for de apoio escolar.
• Se o carrossel for de Língua Portuguesa/Apoio Escolar, aborde interpretação de texto, gramática, ortografia ou redação escolar.
• Se o carrossel for de Tecnologia (Robótica/Programação), aborde raciocínio computacional, robótica e habilidades do futuro.
• Use OBRIGATORIAMENTE a palavra-chave de CTA especificada no campo "cta" do carrossel (ex.: se o CTA for "MEDIDAS", comente "MEDIDAS"; se for "DESAFIO", comente "DESAFIO"). NUNCA substitua por outra palavra como "FUTURO".
• O gancho de abertura e a agitação da dor DEVEM derivar diretamente da mensagem central da Capa e dos slides do roteiro.

─── AS 3 TÉCNICAS (UMA POR OPÇÃO) ───
• OPÇÃO 1 — PAS (Problem → Agitation → Solution): Abre com a dor nua da rotina familiar ligada ao tema específico do carrossel. Agita mostrando o custo de não resolver no colégio. Fecha com a solução da Ensina Mais Tatuapé.
• OPÇÃO 2 — STORYTELLING (Antes → Virada → Resultado): Cena vívida cotidiana no Tatuapé/Anália Franco conectada ao tema do carrossel. Conflito com empatia real. Transformação quando a escola assume o papel técnico.
• OPÇÃO 3 — CURIOSITY GAP (Dado Inesperado → Método → Ação): Afirmação surpreendente ou contraintuitiva sobre a disciplina e notas do carrossel. Valor imediato. Convite para diagnóstico.

─── FORMATO ───
1. Gancho (primeiras 2 linhas): Máximo 125 caracteres antes do corte do '... mais' no feed mobile. NUNCA comece com saudações mornas ('Olá pais', 'Mães do Tatuapé') nem com 'Você sabia que...'. A abertura DEVE ser uma quebra de padrão ou micro-cena sensorial complementar à capa que instiga o clique em 'ver mais' (ex: "Você já viu seu filho apagar a mesma conta até furar a folha de prova?").
2. Escaneabilidade mobile: Parágrafos curtos de 1 a 2 frases com linhas em branco entre eles para leitura ágil no celular
3. Emojis com parcimônia apenas como marcadores visuais funcionais (📌 💡 🎯 🚀)
4. SEO local: mencionar 'Tatuapé', 'Jardim Anália Franco' ou 'apoio escolar' de forma 100% orgânica
5. CTA DUPLO OBRIGATÓRIO:
   • Conversão: palavra-chave EXATA do carrossel nos comentários + chamada para entrar em contato via WhatsApp (11) 94475-0009 oferecendo aula experimental gratuita (em posts de tecnologia) ou avaliação pedagógica gratuita (em posts de apoio escolar)
   • Alavanca Orgânica: incentivo a compartilhar por Direct ('Envie para quem divide a rotina de estudos com você') ou salvar para consultar nas provas
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
2. STEERING PROMPT (o texto de foco, em PT-BR, que o usuário cola no campo de customização): instrua o vídeo a (a) apresentar o tema central em ~60s, (b) seguir a MESMA sequência lógica dos slides do roteiro, (c) abrir com o hook da capa, (d) terminar com o CTA (palavra-chave + contato via WhatsApp (11) 94475-0009 oferecendo aula experimental para tecnologia ou avaliação pedagógica para apoio escolar), (e) usar tom empático "de mãe pra mãe", sem jargão.
3. NARRATIVA (resumo do que o Short deve contar): 4-6 frases conectando o hook → desenvolvimento → ponte para a unidade → CTA, FIÉIS ao roteiro.

─── REGRAS INVIOLÁVEIS ───
• Fidelidade: o tema e a mensagem DEVEM refletir o roteiro dos slides, sem adicionar afirmações que não estejam nele.
• CTA final SEMPRE oferecendo aula experimental (em posts de tecnologia) ou avaliação pedagógica (em posts de apoio escolar) e contato via WhatsApp (11) 94475-0009.
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
