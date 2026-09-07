"""
Motor de Carrosséis — Ensina Mais Tatuapé
Gerador inteligente de carrosséis para Instagram com análise de tendências,
ideias, prompts para Google Flow, geração de imagens com texto sobreposto
e cronograma de postagens.
"""
import streamlit as st
from google import genai
import requests
import json
import re
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Optional
import os
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ─── Configuração ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Motor de Carrosséis — Ensina Mais Tatuapé",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS customizado ─────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0f0f0f; }
    .main .block-container { padding-top: 2rem; max-width: 1200px; }
    h1, h2, h3 { color: #f0f0f0 !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] {
        background-color: #1a1a2e;
        color: #a0a0a0;
        border-radius: 8px 8px 0 0;
        padding: 10px 24px;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e63946 !important;
        color: white !important;
    }
    .idea-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #333;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 16px;
    }
    .idea-card h3 { color: #e63946 !important; margin-top: 0; }
    .metric-box {
        background: #1a1a2e;
        border-left: 4px solid #e63946;
        padding: 12px 16px;
        border-radius: 0 8px 8px 0;
        margin-bottom: 8px;
    }
    .trend-tag {
        display: inline-block;
        background: #e63946;
        color: white;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 0.85em;
        margin: 4px;
    }
    .prompt-box {
        background: #1a1a2e;
        border: 1px solid #444;
        border-radius: 8px;
        padding: 16px;
        font-family: 'Courier New', monospace;
        font-size: 0.9em;
        color: #ccc;
        white-space: pre-wrap;
    }
    .schedule-day {
        background: #16213e;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
    }
    div[data-testid="stExpander"] { background-color: #1a1a2e; border-radius: 8px; }
    .template-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #444;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
        cursor: pointer;
    }
    .template-card:hover { border-color: #e63946; }
    .template-card h4 { color: #4ECDC4 !important; margin-top: 0; }
    .timeline-item {
        background: #1a1a2e;
        border-left: 4px solid #e63946;
        padding: 12px 16px;
        margin-bottom: 8px;
        border-radius: 0 8px 8px 0;
    }
    .timeline-item.carrossel { border-left-color: #4ECDC4; }
    .timeline-item.stories { border-left-color: #FFD166; }
    .timeline-item.reel { border-left-color: #E63946; }
    .batch-card {
        background: #16213e;
        border: 1px solid #333;
        border-radius: 8px;
        padding: 12px;
        margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)


# ─── Gemini Setup ─────────────────────────────────────────────────────────────
def get_gemini_client():
    """Configura e retorna o cliente Gemini."""
    api_key = st.session_state.get("gemini_key", os.environ.get("GEMINI_API_KEY", ""))
    if not api_key:
        return None
    return genai.Client(api_key=api_key)


# ─── Data Classes ─────────────────────────────────────────────────────────────
@dataclass
class CarouselIdea:
    titulo: str
    eixo: str  # Didático, Comportamental, Diagnóstico
    tema: str
    publico_alvo: str
    palavras_chave_seo: list = field(default_factory=list)
    cta: str = ""
    slides_sugeridos: list = field(default_factory=list)
    kpi_alvo: str = ""
    justificativa: str = ""


# ─── Templates Pré-definidos ─────────────────────────────────────────────────
TEMPLATES = {
    "desconstrucao_didatica": {
        "nome": "Desconstrução Didática",
        "eixo": "Didático",
        "icone": "📚",
        "descricao": "Descomplica um problema típico de prova. Maximiza salvamentos.",
        "kpi_alvo": "Salvamentos ≥ 4%",
        "cta_padrao": "DESAFIO",
        "estrutura": [
            {"slide": 1, "tipo": "Capa", "texto": "Enunciado de problema típico cobrado no Ensino Fundamental", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 2, "tipo": "Segunda Capa", "texto": "Por que a leitura apressada induz ao raciocínio errado", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 3, "tipo": "Entrega", "texto": "Método passo a passo — etapa 1", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 4, "tipo": "Entrega", "texto": "Método passo a passo — etapa 2", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 5, "tipo": "Entrega", "texto": "Método passo a passo — etapa 3", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 6, "tipo": "Ponte", "texto": "Como o ensino individualizado resolve a lacuna", "usa_foto_real": True, "tipo_foto": "alunos"},
            {"slide": 7, "tipo": "Prova", "texto": "Foto real da fachada — Rua Coelho Lisboa, 783", "usa_foto_real": True, "tipo_foto": "fachada"},
            {"slide": 8, "tipo": "CTA", "texto": "Salve + Comente DESAFIO para receber lista no Direct", "usa_foto_real": False, "tipo_foto": None},
        ],
    },
    "alivio_pressao": {
        "nome": "Alívio da Pressão Acadêmica",
        "eixo": "Comportamental",
        "icone": "🧠",
        "descricao": "Alivia a ansiedade dos pais. Maximiza envios por DM.",
        "kpi_alvo": "Envios DM ≥ 2,5%",
        "cta_padrao": "FOCO",
        "estrutura": [
            {"slide": 1, "tipo": "Capa", "texto": "A rotina de cobrança e o peso das notas", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 2, "tipo": "Segunda Capa", "texto": "O que acontece neurologicamente com a ansiedade", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 3, "tipo": "Entrega", "texto": "Atitude prática 1 dos pais em casa", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 4, "tipo": "Entrega", "texto": "Atitude prática 2 dos pais em casa", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 5, "tipo": "Entrega", "texto": "Atitude prática 3 dos pais em casa", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 6, "tipo": "Ponte", "texto": "Diferença entre estudo passivo e ativo", "usa_foto_real": True, "tipo_foto": "alunos"},
            {"slide": 7, "tipo": "Prova", "texto": "Foto real da fachada — portão branco, Turma da Mônica", "usa_foto_real": True, "tipo_foto": "fachada"},
            {"slide": 8, "tipo": "CTA", "texto": "Envie para um pai/mãe do colégio + WhatsApp link bio", "usa_foto_real": False, "tipo_foto": None},
        ],
    },
    "conversao_diagnostica": {
        "nome": "Conversão Diagnóstica (Telas vs. Lógica)",
        "eixo": "Diagnóstico",
        "icone": "💻",
        "descricao": "Converte pais preocupados com telas em leads. Maximiza WhatsApp.",
        "kpi_alvo": "Leads WhatsApp 15-25/semana",
        "cta_padrao": "AULA",
        "estrutura": [
            {"slide": 1, "tipo": "Capa", "texto": "O dilema tempo de tela vs. futuro acadêmico", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 2, "tipo": "Segunda Capa", "texto": "Consumo passivo vs. criação ativa", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 3, "tipo": "Entrega", "texto": "Como programação melhora concentração", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 4, "tipo": "Entrega", "texto": "Benefícios da lógica para raciocínio matemático", "usa_foto_real": False, "tipo_foto": None},
            {"slide": 5, "tipo": "Entrega", "texto": "Atividades práticas do laboratório", "usa_foto_real": True, "tipo_foto": "laboratorio"},
            {"slide": 6, "tipo": "Ponte", "texto": "Depoimento ou registro do laboratório", "usa_foto_real": True, "tipo_foto": "laboratorio"},
            {"slide": 7, "tipo": "Prova", "texto": "Foto real da fachada — Unidade Tatuapé", "usa_foto_real": True, "tipo_foto": "fachada"},
            {"slide": 8, "tipo": "CTA", "texto": "Comente AULA para receber convite no Direct", "usa_foto_real": False, "tipo_foto": None},
        ],
    },
}


# ─── Prompts do Sistema ──────────────────────────────────────────────────────
PROMPT_TENDENCIAS = """Você é um estrategista de marketing digital especializado em educação infantil e reforço escolar no Brasil.

Analise as tendências atuais do setor de educação e reforço escolar para crianças do Ensino Fundamental (6-14 anos) no Brasil, focando em:

1. TENDÊNCIAS DE CONTEÚDO no Instagram para educação (formatos, temas em alta, gatilhos emocionais)
2. DÚVIDAS FREQUENTES de pais de alunos do Ensino Fundamental em São Paulo (especialmente zona leste/Tatuapé)
3. SAZONALIDADE ESCOLAR — o que está acontecendo agora em setembro/outubro no calendário escolar (provas bimestrais, fechamento de notas, provas de ingresso)
4. TENDÊNCIAS DE COMPORTAMENTO de pais nas redes sociais (ansiedade acadêmica, tempo de tela, robótica, inteligência emocional)
5. CONCORRÊNCIA — o que outras escolas/institutos de reforço estão postando no Instagram que está dando certo

Retorne um JSON válido com esta estrutura:
{
  "tendencias_conteudo": [
    {"nome": "...", "descricao": "...", "potencial_engajamento": "alto/médio/baixo"}
  ],
  "dores_pais": [
    {"dor": "...", "frequencia": "...", "como_abordar": "..."}
  ],
  "sazonalidade": [
    {"evento": "...", "periodo": "...", "oportunidade": "..."}
  ],
  "tendencias_comportamento": [
    {"tendencia": "...", "relevancia": "...", "aplicacao": "..."}
  ],
  "oportunidades_concorrencia": [
    {"oportunidade": "...", "diferencial_local": "..."}
  ]
}

Seja específico para o bairro do Tatuapé, São Paulo. Mencione escolas locais quando relevante (Mendel, Santo Antônio de Lisboa, Espírito Santo)."""

PROMPT_IDEIAS = """Você é o estrategista de conteúdo da Ensina Mais Tatuapé (Rua Coelho Lisboa, 783).
WhatsApp: (11) 94475-0009
Público: Pais de classes A/B do Tatuapé, filhos no Ensino Fundamental.

Com base nas tendências fornecidas, gere 6 IDEIAS DE CARROSSEL para o Instagram da unidade.

Cada ideia deve seguir um dos 3 eixos estratégicos:
- DIDÁTICO: Resolução de problemas, técnicas de estudo, desconstrução de pegadinhas (meta: salvamentos ≥4%)
- COMPORTAMENTAL: Alívio de pressão acadêmica, ansiedade, rotina de estudos (meta: envios DM ≥2,5%)
- DIAGNÓSTICO: Telas vs. robótica, autoavaliação, aula experimental (meta: leads WhatsApp)

Retorne um JSON válido:
{
  "ideias": [
    {
      "titulo": "Título chamativo para a capa",
      "eixo": "Didático/Comportamental/Diagnóstico",
      "tema": "Descrição do tema específico",
      "publico_alvo": "Quem vai se identificar",
      "palavras_chave_seo": ["apoio escolar Tatuapé", "..."],
      "cta": "PALAVRA_CHAVE para o comentário",
      "slides_sugeridos": [
        {"slide": 1, "tipo": "Capa", "texto": "..."},
        {"slide": 2, "tipo": "Segunda Capa", "texto": "..."},
        {"slide": 3, "tipo": "Entrega", "texto": "..."},
        {"slide": 4, "tipo": "Entrega", "texto": "..."},
        {"slide": 5, "tipo": "Entrega", "texto": "..."},
        {"slide": 6, "tipo": "Ponte", "texto": "..."},
        {"slide": 7, "tipo": "Prova", "texto": "..."},
        {"slide": 8, "tipo": "CTA", "texto": "..."}
      ],
      "kpi_alvo": "Salvamentos/Envios/Leads",
      "justificativa": "Por que esta ideia vai funcionar"
    }
  ]
}

Formato: 30-50 palavras por slide. Tom empático, didático, autêntico. Inclua referências locais (escolas, bairro).

IMPORTANTE: NÃO use personagens da Turma da Mônica (Mônica, Cebolinha, Cascão, Magali, Franjinha, etc). Eles são RESERVADOS aos posts institucionais da franquia. Fique longe desses personagens nas ideias e nos slides."""

PROMPT_PROMPTS_IMAGEM = """Você é um Diretor de Arte e Designer Especialista em Carrosséis de Alta Retenção e Conversão para o Instagram (@ensinamais.tatuape).

Crie a estrutura visual e os layouts para um carrossel educativo de 8 lâminas, formato vertical (1080 x 1350 px, proporção 4:5), combinando design gráfico limpo, didática prática e fotografias reais da escola.

---

### 1. DIRETRIZES DE IDENTIDADE VISUAL E ATIVOS FORNECIDOS:

- **Logo:** Inserir o logo oficial "Ensina Mais Turma da Mônica" com borda branca destacada no canto superior ou inferior das lâminas institucionais.
- **Cores Predominantes:** Fundo branco/off-white limpo (#FFFFFF ou #F8FAFC), azul royal/marinho institucional para títulos principais (#1E3A8A), com acentos de destaque em amarelo (#FFD166) e verde (#4ECDC4) (alinhados às cores do logo da marca).
- **Tipografia:** Sem serifa, moderna, geométrica e de alto contraste (máximo de 35 a 45 palavras por tela para leitura rápida em celular).
- **Elemento de Continuidade:** Barra de progresso discreta ou setas sutis no rodapé indicando deslizamento para o próximo slide. TEXTO OBRIGATÓRIO EM PORTUGUÊS: "Arraste para o lado ➔" (NUNCA escreva "Swipe" ou "Slide" — SEMPRE em português).
- **Ativos Fotográficos Reais:**
  * Imagem de Fachada: Inserir a foto real da fachada da escola (com o portão branco, balões e painel da Turma da Mônica) na lâmina de apresentação do espaço físico.
  * Imagens de Laboratório: Utilizar as fotos autênticas dos alunos (aluna montando o kit de robótica na mesa amarela e aluno concentrado programando no laptop) nas lâminas de metodologia e metodologia prática.

### 2. ESTRUTURA VISUAL POR TIPO DE SLIDE:

#### SLIDE 1: CAPA (Interrupção de Rolagem)
- **Composição Visual:** Fundo clean, tipografia de grande impacto no terço superior. Ilustração minimalista ou elemento gráfico de destaque. Selo sutil no rodapé com o logo da Ensina Mais Tatuapé.
- **Elementos:** Título impactante + subtítulo contextual + "Arraste para o lado ➔" (em português, nunca em inglês)

#### SLIDE 2: A SEGUNDA CAPA (Reapresentação Algorítmica)
- **Composição Visual:** Caixa de destaque visual azul escuro (#1E3A8A) com texto branco. Deve funcionar como uma segunda capa forte caso o Instagram reapresente este slide no feed.
- **Elementos:** Título de destaque + texto explicativo curto

#### SLIDES 3-5: ENTREGA (Valor Didático)
- **Composição Visual:** Diagramas, esquemas visuais, passo a passo ilustrado. Cores da marca (azul, amarelo, verde).
- **Elementos:** Conteúdo didático visual + dicas práticas + "Arraste para o lado ➔" (em português)

#### SLIDE 6: PONTE (Humanização com Alunos Reais)
- **Composição Visual:** Grid elegante com moldura limpa contendo as fotos reais dos alunos da unidade (foto da aluna montando o robô e foto do aluno no computador programando).
- **Elementos:** Fotos reais + texto sobre metodologia + "Arraste para o lado ➔" (em português)

#### SLIDE 7: A ESCOLA REAL NO BAIRRO (Foto da Fachada)
- **Composição Visual:** Destaque para a fotografia real da Fachada da unidade na Rua Coelho Lisboa (portão branco, comunicação visual da Turma da Mônica e balões comemorativos).
- **Elementos:** Foto da fachada + informações da unidade + "Arraste para o lado ➔" (em português)

#### SLIDE 8: CTA CONVERSIVO DE LEAD
- **Composição Visual:** Fundo com tom suave, ícone de salvar em evidência à esquerda e botão de mensagem à direita. Logo oficial no topo.
- **Elementos:** Chamada para Salvar + Comentar palavra-chave + WhatsApp

### 3. REGRAS OBRIGATÓRIAS (SEM EXCEÇÃO):

1. Os prompts de imagem (prompt_en) devem ser em INGLÊS.
2. TODO texto que aparecer sobreposto na imagem (text_overlay) deve ser em PORTUGUÊS DO BRASIL. Jamais use inglês no texto visível da imagem.
3. O text_overlay deve ser curto: no máximo 15 palavras, em fonte bold, legível em tela de celular.
4. Inclua no prompt_en a instrução: "text overlay in Brazilian Portuguese".
5. Incluir "Ensina Mais Turma da Mônica" logo reference quando apropriado.
6. Usar cores: azul royal (#1E3A8A), amarelo (#FFD166), verde (#4ECDC4), branco/off-white.
7. O elemento de continuidade "Arraste para o lado ➔" deve ser SEMPRE em PORTUGUÊS. NUNCA traduza para inglês. Nos prompts_en, referencie como: "text overlay in Brazilian Portuguese: 'Arraste para o lado' with arrow".
8. Fotos reais devem ser referenciadas como "authentic school photo" no prompt.
9. O campo text_overlay de TODOS os slides (exceto slide 8) deve conter o texto do conteúdo + "Arraste para o lado ➔" ao final, separado por quebra de linha.

### 4. FORMATO DE SAÍDA:

Para cada slide, retorne:
- prompt_en: Prompt em inglês para o gerador de imagens (inclua "text overlay in Brazilian Portuguese" e referência ao logo quando apropriado)
- prompt_pt: Descrição em português do que a imagem deve mostrar
- text_overlay: Texto sobreposto em PORTUGUÊS DO BRASIL (10-15 palavras no máximo, bold, legível)
- estilo: Estilo visual específico (flat design, isometric, illustration, photo composition, etc.)
- usa_foto_real: true/false (indica se o slide deve usar foto real da escola)
- tipo_foto: "fachada" / "laboratorio" / "alunos" / null
- referencias: Lista de imagens de referência necessárias para este slide. Valores possíveis: "logo" (Ensina Mais Turma da Mônica), "fachada" (foto da fachada da escola), "alunos_robótica" (aluna montando robô), "alunos_programação" (aluno programando), "lab_tecnologia" (laboratório de tecnologia), null (apenas ilustração gerada)

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
  "dicas_gerais": "Dicas para usar nos geradores de imagem e composição com fotos reais"
}"""

PROMPT_CRONOGRAMA = """Você é o social media manager da Ensina Mais Tatuapé.

Com base nas ideias de carrossel selecionadas, gere um CRONOGRAMA DE POSTAGENS para as próximas 2 semanas.

Regras:
- Máximo 2 carrosséis por semana (Terça + Sexta)
- Nunca posts em dias consecutivos no feed
- Respeitar janela de 72h entre carrosséis
- Horários: 11h30-13h00 ou 18h30-20h00
- IncluirStories diários (bastidores, reposts da franqueadora)
- Protocolo das primeiras 4 horas para cada carrossel

Retorne JSON:
{
  "semana_1": [
    {
      "dia": "Segunda",
      "data": "DD/MM",
      "canal": "Stories/Feed/Reels",
      "tipo": "Institucional/Carrossel/Reel/Bastidores",
      "horario": "HH:MM",
      "conteudo_resumo": "...",
      "cta": "...",
      "protocolo_4h": "Ações nas primeiras 4 horas"
    }
  ],
  "semana_2": [...],
  "kpis_semanais": {
    "meta_salvamentos": "≥4%",
    "meta_envios": "≥2,5%",
    "meta_leads": "15-25 atendimentos",
    "meta_nao_seguidores": "≥20%"
  },
  "dicas_monitoramento": ["..."]
}"""


PROMPT_LEGENDAS = """Você é o social media manager e copywriter da Ensina Mais Tatuapé (@ensinamais.tatuape).

Com base no carrossel abaixo, gere 3 OPÇÕES DE LEGENDA para o Instagram.

### CONTEXTO DA UNIDADE:
- Endereço: Rua Coelho Lisboa, 783 – Tatuapé, São Paulo
- WhatsApp: (11) 94475-0009
- Público: Pais de classes A/B do Tatuapé, filhos no Ensino Fundamental
- Colégios vizinhos: Mendel, Santo Antônio de Lisboa, Espírito Santo

### REGRAS PARA CADA LEGENDA:

1. **Estrutura obrigatória:**
   - GANCHO (1ª linha): Frase curta e impactante que para o scroll. Pode ser pergunta, dado chocante ou afirmação polêmica.
   - CORPO (2-3 parágrafos curtos): Desenvolvimento do tema com valor prático. Use quebras de linha para facilitar leitura no celular.
   - CTA: Chamada para ação clara (comentar palavra-chave, salvar, enviar DM)
   - HASHTAGS: 5-7 hashtags relevantes (inclua #ApoioEscolarTatuapé #ReforçoEscolarTatuapé #EnsinaMaisTatuapé)

2. **Tom de voz:**
   - Empático com a dor dos pais
   - Didático sem ser infantil
   - Autêntico, não institucional
   - Use linguagem natural, como se estivesse conversando com um pai ou mãe

3. **SEO Local obrigatório:**
   - Mencionar "Tatuapé" pelo menos 1 vez no corpo
   - Mencionar "apoio escolar" ou "reforço escolar"自然mente

4. **Palavra-chave CTA:**
   - Cada legenda deve terminar com a instrução de comentar a palavra-chave do carrossel

5. **Extensão:**
   - Máximo 2.200 caracteres (limite do Instagram)
   - Ideal: 800-1500 caracteres

### FORMATO DE SAÍDA:

Retorne JSON:
{
  "legendas": [
    {
      "opcao": 1,
      "estilo": "Despertar curiosidade / Educativo / Emocional",
      "gancho": "Primeira linha que para o scroll",
      "corpo": "Desenvolvimento do tema com价值实践",
      "cta": "Chamada para ação com palavra-chave",
      "hashtags": "#ApoioEscolarTatuapé #ReforçoEscolarTatuapé ...",
      "legenda_completa": "GANCHO\\n\\nCORPO\\n\\nCTA\\n\\nHASHTAGS",
      "char_count": 1200
    }
  ],
  "dicas_uso": "Dicas de como usar cada opção"
}

IMPORTANTE: NÃO use personagens da Turma da Mônica (Mônica, Cebolinha, Cascão, Magali, Franjinha, etc) nas legendas. Eles são RESERVADOS aos posts institucionais da franquia."""


# ─── Funções auxiliares ──────────────────────────────────────────────────────
import time

def call_gemini(prompt: str, context: str = "", max_retries: int = 3) -> str:
    """Chama o Gemini via REST API com fallback de modelos e retries automáticos."""
    api_key = st.session_state.get("gemini_key", os.environ.get("GEMINI_API_KEY", ""))
    if not api_key:
        return ""

    full_prompt = f"{prompt}\n\n{context}" if context else prompt
    modelos = ["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.1-flash-lite"]

    for model_name in modelos:
        for attempt in range(max_retries):
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                payload = {"contents": [{"parts": [{"text": full_prompt}]}]}
                r = requests.post(url, json=payload, timeout=90)
                if r.status_code == 200:
                    data = r.json()
                    text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    if text:
                        return text
                elif r.status_code == 429:
                    # Rate limit - esperar e retry
                    wait_time = 2 ** attempt * 2
                    st.warning(f"Rate limit atingido. Aguardando {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                elif r.status_code >= 500:
                    # Erro de servidor - retry com backoff
                    wait_time = 2 ** attempt
                    st.warning(f"Erro {r.status_code} no servidor. Retry {attempt+1}/{max_retries} em {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    st.warning(f"Modelo {model_name} retornou {r.status_code}, tentando próximo...")
                    break
            except requests.exceptions.ConnectionError as e:
                # Erro de conexão - retry com backoff
                wait_time = 2 ** attempt
                if attempt < max_retries - 1:
                    st.warning(f"Erro de conexão. Retry {attempt+1}/{max_retries} em {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    st.warning(f"Modelo {model_name} falhou após {max_retries} tentativas.")
                    break
            except requests.exceptions.Timeout:
                # Timeout - retry
                wait_time = 2 ** attempt
                if attempt < max_retries - 1:
                    st.warning(f"Timeout. Retry {attempt+1}/{max_retries} em {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    st.warning(f"Modelo {model_name} timeout após {max_retries} tentativas.")
                    break
            except Exception as e:
                st.warning(f"Modelo {model_name} falhou: {str(e)[:80]}")
                break

    st.error("Todos os modelos Gemini estão temporariamente indisponíveis. Tente novamente em alguns minutos.")
    return ""


def extract_json(text: str) -> dict:
    """Extrai JSON de uma resposta de texto."""
    # Tenta encontrar JSON bloco de código
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Tenta parsear o texto inteiro
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Tenta encontrar o primeiro { ao último }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    return {}


def render_idea_card(idea: dict, idx: int):
    """Renderiza um card de ideia de carrossel."""
    eixo_colors = {"Didático": "#4ECDC4", "Comportamental": "#FFD166", "Diagnóstico": "#E63946"}
    eixo = idea.get("eixo", "Didático")
    color = eixo_colors.get(eixo, "#4ECDC4")

    with st.container():
        st.markdown(f"""
        <div class="idea-card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
                <h3 style="margin:0; font-size:1.2em;">{idea.get('titulo', 'Sem título')}</h3>
                <span style="background:{color}; color:white; padding:4px 12px; border-radius:20px; font-size:0.8em; font-weight:600;">{eixo}</span>
            </div>
            <p style="color:#a0a0a0; margin-bottom:8px;">{idea.get('tema', '')}</p>
            <div style="margin-bottom:8px;">
                <strong style="color:#888;">Público:</strong> <span style="color:#ccc;">{idea.get('publico_alvo', '')}</span>
            </div>
            <div style="margin-bottom:8px;">
                <strong style="color:#888;">KPI Alvo:</strong> <span style="color:{color}; font-weight:600;">{idea.get('kpi_alvo', '')}</span>
            </div>
            <div style="margin-bottom:8px;">
                <strong style="color:#888;">CTA:</strong> <span style="color:#FFD166; font-weight:600;">Comente "{idea.get('cta', '')}"</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Slides preview
        slides = idea.get("slides_sugeridos", [])
        if slides:
            with st.expander(f"📄 Ver Roteiro ({len(slides)} slides)", expanded=False):
                for slide in slides:
                    st.markdown(f"**Slide {slide.get('slide', '?')} — {slide.get('tipo', '')}**")
                    st.markdown(f"_{slide.get('texto', '')}_")
                    st.markdown("---")


def render_schedule_day(day: dict):
    """Renderiza um dia do cronograma."""
    canal_icons = {"Stories": "📱", "Feed": "📸", "Reels": "🎬", "Feed (Carrossel)": "🎠"}
    canal = day.get("canal", "")
    icon = canal_icons.get(canal, "📱")

    st.markdown(f"""
    <div class="schedule-day">
        <div style="display:flex; justify-content:space-between; align-items:center;">
            <div>
                <strong style="color:#E63946;">{icon} {day.get('dia', '')} — {day.get('data', '')}</strong>
                <span style="color:#888; margin-left:8px;">{day.get('horario', '')}</span>
            </div>
            <span style="background:#1a1a2e; color:#4ECDC4; padding:2px 10px; border-radius:12px; font-size:0.8em;">{canal}</span>
        </div>
        <p style="color:#ccc; margin:8px 0 4px 0; font-size:0.95em;">{day.get('conteudo_resumo', '')}</p>
        <p style="color:#888; margin:0; font-size:0.85em;">📌 CTA: {day.get('cta', '—')}</p>
    </div>
    """, unsafe_allow_html=True)


# ─── Gerador de Texto Sobreposto ─────────────────────────────────────────────
def add_text_overlay(image_bytes: bytes, text: str, font_size: int = 48,
                     text_color: str = "#FFFFFF", bg_color: str = "#1B2A4A",
                     position: str = "center") -> bytes:
    """
    Adiciona texto sobreposto em PT-BR numa imagem.
    Retorna bytes da imagem processada em PNG.
    """
    img = Image.open(BytesIO(image_bytes)).convert("RGBA")
    width, height = img.size

    # Criar camada transparente para o texto
    txt_layer = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    # Carregar fonte bold
    font_path = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
    try:
        font = ImageFont.truetype(font_path, font_size)
    except:
        font = ImageFont.load_default()

    # Calcular tamanho do texto
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    # Posição do texto
    padding = 40
    if position == "center":
        x = (width - text_width) // 2
        y = (height - text_height) // 2
    elif position == "bottom":
        x = (width - text_width) // 2
        y = height - text_height - padding * 2
    else:  # top
        x = (width - text_width) // 2
        y = padding

    # Desenhar fundo semi-transparente
    bg_padding = 20
    bg_box = [x - bg_padding, y - bg_padding, x + text_width + bg_padding, y + text_height + bg_padding]
    draw.rounded_rectangle(bg_box, radius=12, fill=(27, 42, 74, 200))

    # Desenhar texto
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))

    # Combinar camadas
    result = Image.alpha_composite(img, txt_layer)

    # Converter para RGB e salvar
    output = BytesIO()
    result.convert("RGB").save(output, format="PNG", quality=95)
    return output.getvalue()


def create_slide_from_template(template_key: str, slide_num: int, texto: str,
                                bg_image_url: Optional[str] = None) -> bytes:
    """
    Cria um slide 1080x1350 a partir de um template pré-definido.
    """
    # Criar imagem 1080x1350 com fundo colorido
    width, height = 1080, 1350
    template = TEMPLATES.get(template_key, TEMPLATES["desconstrucao_didatica"])

    # Cores por eixo
    eixo_colors = {
        "Didático": ((27, 42, 74), (78, 205, 196)),      # azul escuro + teal
        "Comportamental": ((27, 42, 74), (255, 209, 102)), # azul escuro + amarelo
        "Diagnóstico": ((27, 42, 74), (230, 57, 70)),     # azul escuro + vermelho
    }
    bg_color, accent_color = eixo_colors.get(template["eixo"], ((27, 42, 74), (78, 205, 196)))

    # Criar imagem
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Adicionar accent bar no topo
    draw.rectangle([0, 0, width, 8], fill=accent_color)

    # Carregar fontes
    font_path = "/usr/share/fonts/noto/NotoSans-Bold.ttf"
    try:
        font_title = ImageFont.truetype(font_path, 72)
        font_text = ImageFont.truetype(font_path, 48)
        font_small = ImageFont.truetype(font_path, 36)
    except:
        font_title = ImageFont.load_default()
        font_text = font_title
        font_small = font_title

    # Adicionar número do slide
    slide_text = f"Slide {slide_num}"
    draw.text((60, 100), slide_text, font=font_small, fill=(255, 255, 255, 150))

    # Adicionar tipo do slide
    slide_info = template["estrutura"][min(slide_num - 1, len(template["estrutura"]) - 1)]
    tipo_text = slide_info["tipo"]
    draw.text((60, 160), tipo_text, font=font_small, fill=accent_color)

    # Texto principal (com word wrap)
    words = texto.split()
    lines = []
    current_line = []
    max_width = width - 120

    for word in words:
        current_line.append(word)
        test_line = " ".join(current_line)
        bbox = draw.textbbox((0, 0), test_line, font=font_text)
        if bbox[2] - bbox[0] > max_width:
            lines.append(" ".join(current_line[:-1]))
            current_line = [word]
    if current_line:
        lines.append(" ".join(current_line))

    # Desenhar texto
    y_pos = 400
    for line in lines[:10]:  # max 10 lines
        draw.text((60, y_pos), line, font=font_text, fill=(255, 255, 255))
        y_pos += 70

    # Adicionar CTA no rodapé
    cta_text = f"Comente '{template['cta_padrao']}' para receber no Direct"
    draw.text((60, height - 200), cta_text, font=font_small, fill=accent_color)

    # Marca d'água
    draw.text((60, height - 100), "@ensinamais.tatuape", font=font_small, fill=(255, 255, 255, 100))

    # Converter para bytes
    output = BytesIO()
    img.save(output, format="PNG", quality=95)
    return output.getvalue()


# ─── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Configurações")
    api_key = st.text_input(
        "🔑 Chave API Gemini",
        value=st.session_state.get("gemini_key", "CHAVE_GEMINI_REMOVIDA"),
        type="password",
        help="Obtida em aistudio.google.com"
    )
    if api_key:
        st.session_state["gemini_key"] = api_key

    st.markdown("---")
    st.markdown("## 📊 Info da Unidade")
    st.markdown("""
    - **Unidade:** Tatuapé
    - **Endereço:** Rua Coelho Lisboa, 783
    - **WhatsApp:** (11) 94475-0009
    - **Colégios:** Mendel, Santo Antônio, Espírito Santo
    - **Público:** Pais A/B, Ensino Fundamental
    """)

    st.markdown("---")
    st.markdown("## 🎯 KPIs Alvo")
    st.markdown("""
    - Salvamentos: ≥ 4,0%
    - Envios DM: ≥ 2,5%
    - Não seguidores: ≥ 20%
    - Leads/semana: 15-25
    """)

    st.markdown("---")
    st.markdown("## 📐 Formato")
    st.markdown("""
    - 1080 x 1350px (4:5)
    - 7 a 9 lâminas
    - 30-50 palavras/slide
    - Máx 2 carrosséis/semana
    """)


# ─── Título ───────────────────────────────────────────────────────────────────
st.markdown("""
# 🎯 Motor de Carrosséis
### Ensina Mais Tatuapé — Instagram Strategy Engine
""")

# ─── Tabs Principais ─────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📈 Análise de Tendências",
    "💡 Ideias de Carrossel",
    "🎨 Prompts Google Flow",
    "🖼️ Gerador de Imagens",
    "📝 Legendas",
    "📅 Cronograma & Acompanhamento",
    "📦 Processador em Lote"
])


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1: ANÁLISE DE TENDÊNCIAS
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.markdown("## 📈 Análise de Tendências do Setor")
    st.markdown("Pesquisa automatizada sobre o que está funcionando no Instagram educacional.")

    col1, col2 = st.columns([3, 1])
    with col2:
        if st.button("🔍 Analisar Tendências", type="primary", use_container_width=True):
            if not st.session_state.get("gemini_key"):
                st.warning("⚠️ Insira sua chave API Gemini na barra lateral.")
            else:
                with st.spinner("🤖 Pesquisando tendências do setor..."):
                    result = call_gemini(PROMPT_TENDENCIAS)
                    if result:
                        st.session_state["tendencias"] = extract_json(result)
                        st.success("✅ Tendências analisadas!")

    if "tendencias" in st.session_state and st.session_state["tendencias"]:
        data = st.session_state["tendencias"]

        # Tendências de Conteúdo
        st.markdown("### 🎬 Tendências de Conteúdo no Instagram")
        for t in data.get("tendencias_conteudo", []):
            cor = "#4ECDC4" if t.get("potencial_engajamento") == "alto" else "#FFD166" if t.get("potencial_engajamento") == "médio" else "#888"
            st.markdown(f"""
            <div class="metric-box">
                <strong style="color:{cor};">{t.get('nome', '')}</strong>
                <span style="color:#888; font-size:0.85em; margin-left:8px;">[{t.get('potencial_engajamento', '')}]</span>
                <br><span style="color:#ccc; font-size:0.9em;">{t.get('descricao', '')}</span>
            </div>
            """, unsafe_allow_html=True)

        # Dores dos Pais
        st.markdown("### 😰 Dores dos Pais no Tatuapé")
        for d in data.get("dores_pais", []):
            with st.expander(f"💔 {d.get('dor', '')}"):
                st.markdown(f"**Frequência:** {d.get('frequencia', '')}")
                st.markdown(f"**Como abordar:** {d.get('como_abordar', '')}")

        # Sazonalidade
        st.markdown("### 📅 Sazonalidade Escolar")
        for s in data.get("sazonalidade", []):
            st.info(f"**{s.get('evento', '')}** ({s.get('periodo', '')}) → {s.get('oportunidade', '')}")

        # Tendências de Comportamento
        st.markdown("### 🧠 Tendências de Comportamento")
        for t in data.get("tendencias_comportamento", []):
            st.markdown(f"""
            <div class="metric-box">
                <strong style="color:#E63946;">{t.get('tendencia', '')}</strong>
                <br><span style="color:#ccc; font-size:0.9em;">{t.get('aplicacao', '')}</span>
            </div>
            """, unsafe_allow_html=True)

        # Oportunidades
        st.markdown("### 🏆 Oportunidades vs. Concorrência")
        for o in data.get("oportunidades_concorrencia", []):
            st.success(f"**{o.get('oportunidade', '')}** → Diferencial local: {o.get('diferencial_local', '')}")

        # Salvar tendências para usar nas outras tabs
        st.session_state["tendencias_texto"] = json.dumps(data, ensure_ascii=False)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2: IDEIAS DE CARROSSEL
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.markdown("## 💡 Gerador de Ideias de Carrossel")
    st.markdown("Gera 6 ideias estratégicas baseadas nas tendências identificadas.")

    # Seção de Templates
    st.markdown("### 📋 Templates Pré-definidos")
    st.markdown("Escolha um template para usar como base ou gere ideias personalizadas.")

    template_cols = st.columns(3)
    for idx, (key, template) in enumerate(TEMPLATES.items()):
        with template_cols[idx]:
            if st.button(
                f"{template['icone']} {template['nome']}",
                key=f"template_{key}",
                use_container_width=True
            ):
                st.session_state["template_selecionado"] = key
                st.session_state["template_info"] = template

    if "template_info" in st.session_state:
        template = st.session_state["template_info"]
        st.info(f"**Template selecionado:** {template['nome']} — {template['descricao']}")

        # Personalizar template
        custom_tema = st.text_input("Tema específico (ex: frações, ansiedade de provas):", key="custom_tema")
        custom_cta = st.text_input("Palavra-chave CTA:", value=template["cta_padrao"], key="custom_cta")

        if st.button("🎲 Gerar Ideias com Template", type="primary", use_container_width=True):
            if not st.session_state.get("gemini_key"):
                st.warning("⚠️ Insira sua chave API Gemini na barra lateral.")
            else:
                contexto = f"Template: {template['nome']}\nEixo: {template['eixo']}\nTema: {custom_tema}\nCTA: {custom_cta}"
                with st.spinner("🤖 Gerando ideias com template..."):
                    result = call_gemini(PROMPT_IDEIAS, contexto)
                    if result:
                        st.session_state["ideias"] = extract_json(result)
                        st.success("✅ Ideias geradas com template!")

    st.markdown("---")

    # Geração tradicional
    col1, col2 = st.columns([3, 1])
    with col1:
        foco = st.selectbox(
            "Filtrar por eixo:",
            ["Todos", "Didático (Salvamentos)", "Comportamental (Envios DM)", "Diagnóstico (Leads WhatsApp)"]
        )
    with col2:
        if st.button("🎲 Gerar Ideias", type="primary", use_container_width=True):
            if not st.session_state.get("gemini_key"):
                st.warning("⚠️ Insira sua chave API Gemini na barra lateral.")
            else:
                contexto_tendencias = st.session_state.get("tendencias_texto", "Sem dados de tendências. Gere ideias gerais.")
                with st.spinner("🤖 Gerando ideias estratégicas..."):
                    result = call_gemini(PROMPT_IDEIAS, f"Tendências:\n{contexto_tendencias}")
                    if result:
                        st.session_state["ideias"] = extract_json(result)
                        st.success("✅ 6 ideias geradas!")

    if "ideias" in st.session_state and st.session_state["ideias"]:
        ideias = st.session_state["ideias"].get("ideias", [])

        # Filtro
        if foco != "Todos":
            eixo_map = {
                "Didático (Salvamentos)": "Didático",
                "Comportamental (Envios DM)": "Comportamental",
                "Diagnóstico (Leads WhatsApp)": "Diagnóstico"
            }
            ideias = [i for i in ideias if i.get("eixo") == eixo_map[foco]]

        st.markdown(f"### {len(ideias)} ideias encontradas")
        for idx, idea in enumerate(ideias):
            render_idea_card(idea, idx)

        # Botão para selecionar ideias
        st.markdown("---")
        st.markdown("### ✅ Selecionar ideias para Prompts e Cronograma")
        opcoes = {f"{i.get('eixo', '?')} — {i.get('titulo', 'Sem título')}": i for i in ideias}
        selecionadas = st.multiselect(
            "Escolha as ideias para gerar prompts e cronograma:",
            options=list(opcoes.keys()),
            key="selecao_ideias"
        )

        if selecionadas:
            st.session_state["ideias_selecionadas"] = [opcoes[s] for s in selecionadas]
            st.success(f"✅ {len(selecionadas)} ideia(s) selecionada(s). Vá para as abas de Prompts ou Cronograma.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3: PROMPTS GOOGLE FLOW
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.markdown("## 🎨 Prompts para Google Flow (ImageFX)")
    st.markdown("Gera prompts detalhados em inglês para criar cada slide com IA.")

    if "ideias_selecionadas" not in st.session_state or not st.session_state["ideias_selecionadas"]:
        st.info("📌 Selecione ideias na aba 'Ideias de Carrossel' primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]

        # Escolher qual ideia gerar prompts
        opcoes_prompt = {f"{i.get('eixo', '?')} — {i.get('titulo', '')}": i for i in ideias_sel}
        escolha = st.selectbox("Escolha a ideia para gerar prompts:", list(opcoes_prompt.keys()))

        if st.button("🎨 Gerar Prompts de Imagem", type="primary", use_container_width=True):
            if not st.session_state.get("gemini_key"):
                st.warning("⚠️ Insira sua chave API Gemini na barra lateral.")
            else:
                ideia_escolhida = opcoes_prompt[escolha]
                slides_text = json.dumps(ideia_escolhida.get("slides_sugeridos", []), ensure_ascii=False)
                with st.spinner("🤖 Gerando prompts para cada slide..."):
                    result = call_gemini(PROMPT_PROMPTS_IMAGEM, f"Carrossel:\n{json.dumps(ideia_escolhida, ensure_ascii=False)}\n\nSlides:\n{slides_text}")
                    if result:
                        st.session_state["prompts"] = extract_json(result)
                        st.success("✅ Prompts gerados!")

        if "prompts" in st.session_state and st.session_state["prompts"]:
            prompts = st.session_state["prompts"]

            # Paleta de cores
            paleta = prompts.get("paleta_cores", {})
            if paleta:
                st.markdown("### 🎨 Paleta de Cores")
                cols = st.columns(len(paleta))
                for i, (nome, cor) in enumerate(paleta.items()):
                    with cols[i]:
                        st.markdown(f"""
                        <div style="text-align:center;">
                            <div style="width:60px; height:60px; background:{cor}; border-radius:8px; margin:0 auto 4px;"></div>
                            <span style="color:#888; font-size:0.8em;">{nome}<br>{cor}</span>
                        </div>
                        """, unsafe_allow_html=True)

            # Prompts por slide
            st.markdown("### 📸 Prompts por Slide")
            for slide in prompts.get("slides", []):
                with st.expander(f"Slide {slide.get('slide_num', '?')} — {slide.get('estilo', '')}", expanded=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**🇺🇸 Prompt (English):**")
                        st.code(slide.get("prompt_en", ""), language=None)
                    with col2:
                        st.markdown("**🇧🇷 Descrição (Português):**")
                        st.markdown(slide.get("prompt_pt", ""))

                    st.markdown(f"**📝 Texto sobreposto:** `{slide.get('text_overlay', '')}`")

                    # Referências de imagens
                    referencias = slide.get("referencias", [])
                    if referencias:
                        ref_labels = {
                            "logo": "🏷️ Logo Ensina Mais Turma da Mônica",
                            "fachada": "🏢 Foto da Fachada (Rua Coelho Lisboa, 783)",
                            "alunos_robótica": "🤖 Foto: Aluna montando robô na mesa amarela",
                            "alunos_programação": "💻 Foto: Aluno programando no laptop",
                            "lab_tecnologia": "🔬 Foto: Laboratório de Tecnologia"
                        }
                        refs_text = " | ".join([ref_labels.get(r, r) for r in referencias])
                        st.markdown(f"**📎 Referências:** {refs_text}")
                    else:
                        st.markdown("**📎 Referências:** Apenas ilustração gerada (sem foto real)")

                    # Botão de copiar prompt
                    if st.button(f"📋 Copiar prompt Slide {slide.get('slide_num', '?')}", key=f"copy_{slide.get('slide_num', 0)}"):
                        st.code(slide.get("prompt_en", ""), language=None)
                        st.success("Prompt copiado! Cole no Google ImageFX.")

            # Dicas gerais
            dicas = prompts.get("dicas_gerais", "")
            if dicas:
                st.markdown("### 💡 Dicas Gerais")
                st.info(dicas)

            # Botão exportar todos os prompts
            if st.button("📥 Exportar Todos os Prompts (JSON)", use_container_width=True):
                export = json.dumps(prompts, ensure_ascii=False, indent=2)
                st.download_button(
                    label="⬇️ Download JSON",
                    data=export,
                    file_name="prompts_carrossel.json",
                    mime="application/json"
                )

            # Exportar para .txt (apenas prompts, separados por linha em branco)
            if st.button("📄 Exportar Prompts para Automação (.txt)", use_container_width=True):
                txt_content = "\n\n".join(
                    slide.get("prompt_en", "")
                    for slide in prompts.get("slides", [])
                    if slide.get("prompt_en")
                )
                st.download_button(
                    label="⬇️ Download .txt",
                    data=txt_content,
                    file_name="prompts_automaticacao.txt",
                    mime="text/plain"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4: GERADOR DE IMAGENS
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.markdown("## 🖼️ Gerador de Imagens com Texto Sobreposto")
    st.markdown("Gera slides com texto em PT-BR automaticamente. Faça upload de imagens ou use templates.")

    # Modo 1: Upload de imagem
    st.markdown("### 📤 Modo 1: Upload de Imagem")
    uploaded_file = st.file_uploader("Faça upload de uma imagem (JPG, PNG)", type=["jpg", "jpeg", "png"], key="upload_img")

    if uploaded_file:
        image_bytes = uploaded_file.read()
        st.image(image_bytes, caption="Imagem original", use_container_width=True)

        text_overlay = st.text_input("Texto sobreposto (PT-BR, máx 15 palavras):", key="text_overlay_input")
        font_size = st.slider("Tamanho da fonte:", 24, 72, 48)
        position = st.selectbox("Posição:", ["center", "bottom", "top"])

        if st.button("🖼️ Adicionar Texto Sobreposto", type="primary", use_container_width=True):
            if text_overlay:
                with st.spinner("Processando imagem..."):
                    result_bytes = add_text_overlay(image_bytes, text_overlay, font_size=font_size, position=position)
                    st.image(result_bytes, caption="Imagem com texto sobreposto")
                    st.download_button(
                        label="⬇️ Download Slide",
                        data=result_bytes,
                        file_name="slide_com_texto.png",
                        mime="image/png"
                    )
            else:
                st.warning("⚠️ Digite o texto sobreposto.")

    st.markdown("---")

    # Modo 2: Templates
    st.markdown("### 📋 Modo 2: Gerar com Template")
    template_options = {f"{t['icone']} {t['nome']}": k for k, t in TEMPLATES.items()}
    template_choice = st.selectbox("Escolha o template:", list(template_options.keys()), key="template_img_choice")

    if template_choice:
        template_key = template_options[template_choice]
        template = TEMPLATES[template_key]

        slide_num = st.number_input("Número do slide:", min_value=1, max_value=9, value=1)
        slide_text = st.text_area("Texto do slide:", value=template["estrutura"][min(slide_num-1, len(template["estrutura"])-1)]["texto"] or "")

        if st.button("🖼️ Gerar Slide com Template", type="primary", use_container_width=True):
            with st.spinner("Gerando slide..."):
                result_bytes = create_slide_from_template(template_key, slide_num, slide_text or "")
                st.image(result_bytes, caption=f"Slide {slide_num} — {template['nome']}")
                st.download_button(
                    label="⬇️ Download Slide",
                    data=result_bytes,
                    file_name=f"slide_{slide_num}_{template_key}.png",
                    mime="image/png"
                )

    st.markdown("---")

    # Modo 3: Gerar todos os slides de um carrossel
    st.markdown("### 🎠 Modo 3: Gerar Todos os Slides de um Carrossel")
    if "ideias_selecionadas" in st.session_state and st.session_state["ideias_selecionadas"]:
        ideias_sel = st.session_state["ideias_selecionadas"]
        opcoes_carrossel = {f"{i.get('eixo', '?')} — {i.get('titulo', '')}": i for i in ideias_sel}
        escolha_carrossel = st.selectbox("Escolha o carrossel:", list(opcoes_carrossel.keys()), key="carrossel_img_choice")

        if st.button("🎠 Gerar Todos os Slides", type="primary", use_container_width=True):
            ideia = opcoes_carrossel[escolha_carrossel]
            slides = ideia.get("slides_sugeridos", [])

            with st.spinner(f"Gerando {len(slides)} slides..."):
                all_slides = []
                progress_bar = st.progress(0)

                for idx, slide in enumerate(slides):
                    slide_num = slide.get("slide", idx + 1)
                    texto = slide.get("texto", "")

                    # Determinar template baseado no eixo
                    eixo = ideia.get("eixo", "Didático")
                    if eixo == "Didático":
                        template_key = "desconstrucao_didatica"
                    elif eixo == "Comportamental":
                        template_key = "alivio_pressao"
                    else:
                        template_key = "conversao_diagnostica"

                    slide_bytes = create_slide_from_template(template_key, slide_num, texto)
                    all_slides.append((slide_num, slide_bytes))

                    progress_bar.progress((idx + 1) / len(slides))

                # Mostrar todos os slides
                st.success(f"✅ {len(all_slides)} slides gerados!")
                for slide_num, slide_bytes in all_slides:
                    st.image(slide_bytes, caption=f"Slide {slide_num}")

                # Botão para baixar todos como ZIP
                import zipfile
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for slide_num, slide_bytes in all_slides:
                        zip_file.writestr(f"slide_{slide_num}.png", slide_bytes)

                st.download_button(
                    label="⬇️ Download Todos os Slides (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"carrossel_{ideia.get('titulo', ' slides')[:30].replace(' ', '_')}.zip",
                    mime="application/zip"
                )
    else:
        st.info("📌 Selecione ideias na aba 'Ideias de Carrossel' primeiro.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 5: LEGENDAS
# ═══════════════════════════════════════════════════════════════════════════════
with tab5:
    st.markdown("## 📝 Gerador de Legendas")
    st.markdown("Gera 3 opções de legenda conectadas ao tema do carrossel selecionado.")

    if "ideias_selecionadas" not in st.session_state or not st.session_state["ideias_selecionadas"]:
        st.info("📌 Selecione ideias na aba 'Ideias de Carrossel' primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]

        # Escolher qual ideia gerar legenda
        opcoes_legenda = {f"{i.get('eixo', '?')} — {i.get('titulo', '')}": i for i in ideias_sel}
        escolha = st.selectbox("Escolha o carrossel para gerar legendas:", list(opcoes_legenda.keys()), key="escolha_legenda")

        if st.button("📝 Gerar Legendas", type="primary", use_container_width=True):
            if not st.session_state.get("gemini_key"):
                st.warning("⚠️ Insira sua chave API Gemini na barra lateral.")
            else:
                ideia_escolhida = opcoes_legenda[escolha]
                with st.spinner("🤖 Gerando 3 opções de legenda..."):
                    result = call_gemini(PROMPT_LEGENDAS, f"Carrossel:\n{json.dumps(ideia_escolhida, ensure_ascii=False)}")
                    if result:
                        st.session_state["legendas"] = extract_json(result)
                        st.success("✅ 3 legendas geradas!")

        if "legendas" in st.session_state and st.session_state["legendas"]:
            legendas = st.session_state["legendas"]

            # Mostrar as 3 opções
            for leg in legendas.get("legendas", []):
                opcao = leg.get("opcao", "?")
                estilo = leg.get("estilo", "")
                gancho = leg.get("gancho", "")
                corpo = leg.get("corpo", "")
                cta = leg.get("cta", "")
                hashtags = leg.get("hashtags", "")
                legenda_completa = leg.get("legenda_completa", "")
                char_count = leg.get("char_count", 0)

                # Cores por estilo
                estilo_cores = {
                    "Despertar curiosidade": "#E63946",
                    "Educativo": "#4ECDC4",
                    "Emocional": "#FFD166",
                    "Dado chocante": "#E63946",
                    "Pergunta": "#4ECDC4",
                    "Polêmico": "#FFD166",
                }
                cor = estilo_cores.get(estilo, "#4ECDC4")

                with st.expander(f"{'🔴' if opcao == 1 else '🟡' if opcao == 2 else '🟢'} Opção {opcao} — {estilo}", expanded=(opcao == 1)):
                    # Estrutura da legenda
                    st.markdown(f"**🎣 Gancho:**")
                    st.markdown(f"> {gancho}")

                    st.markdown(f"**📖 Corpo:**")
                    st.markdown(f"> {corpo}")

                    st.markdown(f"**📢 CTA:**")
                    st.markdown(f"> {cta}")

                    st.markdown(f"**# Hashtags:**")
                    st.markdown(f"> {hashtags}")

                    st.markdown("---")

                    # Legenda completa (pronta para copiar)
                    st.markdown(f"**📋 Legenda Completa (copie e cole no Instagram):**")
                    st.code(legenda_completa, language=None)

                    # Contagem de caracteres
                    if char_count > 2200:
                        st.error(f"⚠️ {char_count} caracteres — acima do limite do Instagram (2.200)")
                    elif char_count > 1800:
                        st.warning(f"⏳ {char_count} caracteres — próximo do limite")
                    else:
                        st.success(f"✅ {char_count} caracteres — dentro do ideal")

                    # Botão de copiar
                    if st.button(f"📋 Copiar Legenda Opção {opcao}", key=f"copy_leg_{opcao}"):
                        st.code(legenda_completa, language=None)
                        st.success("Legenda copiada! Cole direto no Instagram.")

            # Dicas de uso
            dicas = legendas.get("dicas_uso", "")
            if dicas:
                st.markdown("---")
                st.markdown("### 💡 Dicas de Uso")
                st.info(dicas)

            # Exportar legendas
            st.markdown("---")
            if st.button("📥 Exportar Legendas (JSON)", use_container_width=True):
                export = json.dumps(legendas, ensure_ascii=False, indent=2)
                st.download_button(
                    label="⬇️ Download JSON",
                    data=export,
                    file_name="legendas_carrossel.json",
                    mime="application/json"
                )

            # Exportar apenas as legendas completas em .txt
            if st.button("📄 Exportar Legendas (.txt)", use_container_width=True):
                txt_content = "\n\n---\n\n".join(
                    f"OPÇÃO {leg.get('opcao', '?')} — {leg.get('estilo', '')}\n\n{leg.get('legenda_completa', '')}"
                    for leg in legendas.get("legendas", [])
                )
                st.download_button(
                    label="⬇️ Download .txt",
                    data=txt_content,
                    file_name="legendas_carrossel.txt",
                    mime="text/plain"
                )


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 6: CRONOGRAMA & ACOMPANHAMENTO
# ═══════════════════════════════════════════════════════════════════════════════
with tab6:
    st.markdown("## 📅 Cronograma de Postagens & Acompanhamento")

    if "ideias_selecionadas" not in st.session_state or not st.session_state["ideias_selecionadas"]:
        st.info("📌 Selecione ideias na aba 'Ideias de Carrossel' primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]

        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{len(ideias_sel)} ideia(s) selecionada(s)** para o cronograma.")
        with col2:
            if st.button("📅 Gerar Cronograma", type="primary", use_container_width=True):
                if not st.session_state.get("gemini_key"):
                    st.warning("⚠️ Insira sua chave API Gemini na barra lateral.")
                else:
                    ideias_text = json.dumps(ideias_sel, ensure_ascii=False)
                    with st.spinner("🤖 Montando cronograma otimizado..."):
                        result = call_gemini(PROMPT_CRONOGRAMA, f"Ideias selecionadas:\n{ideias_text}")
                        if result:
                            st.session_state["cronograma"] = extract_json(result)
                            st.success("✅ Cronograma gerado!")

        if "cronograma" in st.session_state and st.session_state["cronograma"]:
            cron = st.session_state["cronograma"]

            # Calendário Visual (Timeline)
            st.markdown("### 📆 Calendário Visual")

            all_days = []
            for day in cron.get("semana_1", []):
                day["semana"] = 1
                all_days.append(day)
            for day in cron.get("semana_2", []):
                day["semana"] = 2
                all_days.append(day)

            # Timeline
            for day in all_days:
                canal = day.get("canal", "")
                tipo = day.get("tipo", "")

                # Determinar classe CSS baseada no tipo
                if "Carrossel" in tipo or "Feed" in canal:
                    item_class = "carrossel"
                elif "Stories" in canal:
                    item_class = "stories"
                elif "Reel" in tipo:
                    item_class = "reel"
                else:
                    item_class = ""

                st.markdown(f"""
                <div class="timeline-item {item_class}">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <strong style="color:#E63946;">Semana {day.get('semana', '?')} — {day.get('dia', '')} — {day.get('data', '')}</strong>
                            <span style="color:#888; margin-left:8px;">{day.get('horario', '')}</span>
                        </div>
                        <span style="background:#1a1a2e; color:#4ECDC4; padding:2px 10px; border-radius:12px; font-size:0.8em;">{canal}</span>
                    </div>
                    <p style="color:#ccc; margin:8px 0 4px 0; font-size:0.95em;">{day.get('conteudo_resumo', '')}</p>
                    <p style="color:#888; margin:0; font-size:0.85em;">📌 CTA: {day.get('cta', '—')}</p>
                </div>
                """, unsafe_allow_html=True)

            # KPIs semanais
            kpis = cron.get("kpis_semanais", {})
            if kpis:
                st.markdown("### 🎯 Metas Semanais")
                kpi_cols = st.columns(4)
                kpi_items = [
                    ("💾 Salvamentos", kpis.get("meta_salvamentos", "≥4%"), "#4ECDC4"),
                    ("📤 Envios DM", kpis.get("meta_envios", "≥2,5%"), "#FFD166"),
                    ("🆕 Não Seguidores", kpis.get("meta_nao_seguidores", "≥20%"), "#E63946"),
                    ("📱 Leads", kpis.get("meta_leads", "15-25"), "#A8DADC"),
                ]
                for i, (label, valor, cor) in enumerate(kpi_items):
                    with kpi_cols[i]:
                        st.markdown(f"""
                        <div class="metric-box">
                            <strong style="color:{cor};">{label}</strong><br>
                            <span style="color:white; font-size:1.3em; font-weight:700;">{valor}</span>
                        </div>
                        """, unsafe_allow_html=True)

            # Dicas de monitoramento
            dicas = cron.get("dicas_monitoramento", [])
            if dicas:
                st.markdown("### 📊 Dicas de Monitoramento")
                for d in dicas:
                    st.markdown(f"- {d}")

            # Exportar cronograma
            st.markdown("---")
            if st.button("📥 Exportar Cronograma Completo", use_container_width=True):
                export = json.dumps(cron, ensure_ascii=False, indent=2)
                st.download_button(
                    label="⬇️ Download Cronograma (JSON)",
                    data=export,
                    file_name="cronograma_carrosseis.json",
                    mime="application/json"
                )

        # ─── Seção de Acompanhamento ───
        st.markdown("---")
        st.markdown("### 📊 Acompanhamento de Métricas")
        st.markdown("Registre os resultados reais após 72h de cada publicação.")

        with st.form("metricas_form"):
            col1, col2 = st.columns(2)
            with col1:
                post_titulo = st.text_input("Título do post")
                alcance = st.number_input("Alcance Total", min_value=0, value=0)
                salvamentos = st.number_input("Salvamentos", min_value=0, value=0)
            with col2:
                envios_dm = st.number_input("Envios via DM", min_value=0, value=0)
                nao_seguidores = st.number_input("Alcance Não Seguidores", min_value=0, value=0)
                comentarios = st.number_input("Comentários", min_value=0, value=0)

            leads_whatsapp = st.number_input("Leads WhatsApp", min_value=0, value=0)
            data_post = st.date_input("Data da publicação")

            submitted = st.form_submit_button("💾 Salvar Métricas", use_container_width=True)

            if submitted and alcance > 0:
                calc_salvos = (salvamentos / alcance * 100) if alcance > 0 else 0
                calc_envios = (envios_dm / alcance * 100) if alcance > 0 else 0
                calc_nao_seg = (nao_seguidores / alcance * 100) if alcance > 0 else 0

                st.markdown("### 📈 Resultados Calculados")
                r1, r2, r3, r4 = st.columns(4)
                with r1:
                    cor = "#4ECDC4" if calc_salvos >= 4 else "#E63946"
                    st.metric("💾 Salvamentos", f"{calc_salvos:.1f}%", delta="✅ Meta" if calc_salvos >= 4 else "❌ Abaixo")
                with r2:
                    cor = "#FFD166" if calc_envios >= 2.5 else "#E63946"
                    st.metric("📤 Envios DM", f"{calc_envios:.1f}%", delta="✅ Meta" if calc_envios >= 2.5 else "❌ Abaixo")
                with r3:
                    cor = "#A8DADC" if calc_nao_seg >= 20 else "#E63946"
                    st.metric("🆕 Não Seguidores", f"{calc_nao_seg:.1f}%", delta="✅ Meta" if calc_nao_seg >= 20 else "❌ Abaixo")
                with r4:
                    cor = "#4ECDC4" if leads_whatsapp >= 15 else "#E63946"
                    st.metric("📱 Leads WhatsApp", f"{leads_whatsapp}", delta="✅ Meta" if leads_whatsapp >= 15 else "❌ Abaixo")

                # Salvar no session state para histórico
                if "historico_metricas" not in st.session_state:
                    st.session_state["historico_metricas"] = []
                st.session_state["historico_metricas"].append({
                    "data": str(data_post),
                    "titulo": post_titulo,
                    "alcance": alcance,
                    "salvamentos": salvamentos,
                    "taxa_salvamentos": round(calc_salvos, 1),
                    "envios_dm": envios_dm,
                    "taxa_envios": round(calc_envios, 1),
                    "nao_seguidores": nao_seguidores,
                    "taxa_nao_seguidores": round(calc_nao_seg, 1),
                    "comentarios": comentarios,
                    "leads_whatsapp": leads_whatsapp
                })
                st.success("✅ Métricas registradas!")

        # Histórico
        if "historico_metricas" in st.session_state and st.session_state["historico_metricas"]:
            st.markdown("### 📋 Histórico de Métricas")
            import pandas as pd
            df = pd.DataFrame(st.session_state["historico_metricas"])
            st.dataframe(df, use_container_width=True)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 7: PROCESSADOR EM LOTE
# ═══════════════════════════════════════════════════════════════════════════════
with tab7:
    st.markdown("## 📦 Processador em Lote")
    st.markdown("Gere múltiplos carrosséis de uma vez. Selecione quantas ideias quiser e gere tudo junto.")

    if "ideias_selecionadas" not in st.session_state or not st.session_state["ideias_selecionadas"]:
        st.info("📌 Selecione ideias na aba 'Ideias de Carrossel' primeiro.")
    else:
        ideias_sel = st.session_state["ideias_selecionadas"]
        st.markdown(f"**{len(ideias_sel)} ideia(s) selecionada(s)** para processamento em lote.")

        # Opções de processamento
        st.markdown("### ⚙️ Opções de Processamento")

        col1, col2, col3 = st.columns(3)
        with col1:
            gerar_prompts = st.checkbox("🎨 Gerar Prompts de Imagem", value=True)
        with col2:
            gerar_slides = st.checkbox("🖼️ Gerar Slides com Templates", value=True)
        with col3:
            gerar_cronograma = st.checkbox("📅 Gerar Cronograma", value=True)

        if st.button("🚀 Processar Tudo em Lote", type="primary", use_container_width=True):
            if not st.session_state.get("gemini_key"):
                st.warning("⚠️ Insira sua chave API Gemini na barra lateral.")
            else:
                results = {}
                progress = st.progress(0)
                status = st.empty()

                # Processar cada ideia
                for idx, ideia in enumerate(ideias_sel):
                    titulo = ideia.get("titulo", f"Ideia {idx+1}")
                    status.text(f"Processando: {titulo}...")

                    # 1. Gerar prompts
                    if gerar_prompts:
                        slides_text = json.dumps(ideia.get("slides_sugeridos", []), ensure_ascii=False)
                        result = call_gemini(PROMPT_PROMPTS_IMAGEM, f"Carrossel:\n{json.dumps(ideia, ensure_ascii=False)}\n\nSlides:\n{slides_text}")
                        if result:
                            prompts = extract_json(result)
                            results[f"prompts_{idx}"] = {
                                "titulo": titulo,
                                "prompts": prompts
                            }

                    # 2. Gerar slides com template
                    if gerar_slides:
                        slides = ideia.get("slides_sugeridos", [])
                        eixo = ideia.get("eixo", "Didático")
                        if eixo == "Didático":
                            template_key = "desconstrucao_didatica"
                        elif eixo == "Comportamental":
                            template_key = "alivio_pressao"
                        else:
                            template_key = "conversao_diagnostica"

                        slide_images = []
                        for slide in slides:
                            slide_num = slide.get("slide", 1)
                            texto = slide.get("texto", "")
                            slide_bytes = create_slide_from_template(template_key, slide_num, texto)
                            slide_images.append((slide_num, slide_bytes))

                        results[f"slides_{idx}"] = {
                            "titulo": titulo,
                            "images": slide_images
                        }

                    progress.progress((idx + 1) / len(ideias_sel))

                # 3. Gerar cronograma único
                if gerar_cronograma:
                    ideias_text = json.dumps(ideias_sel, ensure_ascii=False)
                    result = call_gemini(PROMPT_CRONOGRAMA, f"Ideias selecionadas:\n{ideias_text}")
                    if result:
                        cronograma = extract_json(result)
                        results["cronograma"] = cronograma

                status.text("✅ Processamento concluído!")
                st.session_state["batch_results"] = results
                st.success(f"✅ {len(ideias_sel)} carrosséis processados!")

        # Mostrar resultados do lote
        if "batch_results" in st.session_state and st.session_state["batch_results"]:
            results = st.session_state["batch_results"]

            st.markdown("### 📊 Resultados do Lote")

            # Prompts
            prompts_items = {k: v for k, v in results.items() if k.startswith("prompts_")}
            if prompts_items:
                st.markdown("#### 🎨 Prompts Gerados")
                for key, item in prompts_items.items():
                    with st.expander(f"📋 {item['titulo']}", expanded=False):
                        prompts = item["prompts"]
                        for slide in prompts.get("slides", []):
                            st.markdown(f"**Slide {slide.get('slide_num', '?')}:**")
                            st.code(slide.get("prompt_en", ""), language=None)
                            st.markdown(f"📝 {slide.get('text_overlay', '')}")
                            st.markdown("---")

            # Slides
            slides_items = {k: v for k, v in results.items() if k.startswith("slides_")}
            if slides_items:
                st.markdown("#### 🖼️ Slides Gerados")
                for key, item in slides_items.items():
                    with st.expander(f"🎠 {item['titulo']}", expanded=False):
                        for slide_num, slide_bytes in item["images"]:
                            st.image(slide_bytes, caption=f"Slide {slide_num}")

            # Cronograma
            if "cronograma" in results:
                st.markdown("#### 📅 Cronograma")
                cron = results["cronograma"]
                for day in cron.get("semana_1", []) + cron.get("semana_2", []):
                    render_schedule_day(day)

            # Exportar tudo
            st.markdown("---")
            if st.button("📥 Exportar Tudo do Lote", use_container_width=True):
                # Criar ZIP com tudo
                import zipfile
                zip_buffer = BytesIO()
                with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    # Adicionar prompts
                    for key, item in prompts_items.items():
                        prompts_json = json.dumps(item["prompts"], ensure_ascii=False, indent=2)
                        zip_file.writestr(f"prompts/{item['titulo'][:50].replace(' ', '_')}.json", prompts_json)

                    # Adicionar slides
                    for key, item in slides_items.items():
                        for slide_num, slide_bytes in item["images"]:
                            zip_file.writestr(f"slides/{item['titulo'][:30].replace(' ', '_')}/slide_{slide_num}.png", slide_bytes)

                    # Adicionar cronograma
                    if "cronograma" in results:
                        cron_json = json.dumps(results["cronograma"], ensure_ascii=False, indent=2)
                        zip_file.writestr("cronograma.json", cron_json)

                st.download_button(
                    label="⬇️ Download Lote Completo (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name=f"lote_carrosseis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                    mime="application/zip"
                )
