"""
config.py — Constantes globais, dados da unidade e KPIs.
Centraliza toda configuração do app para facilitar manutenção.
"""

import os
from pathlib import Path

# ─── Dados da Unidade ────────────────────────────────────────────────────────
UNIDADE = {
    "nome": "Ensina Mais Tatuapé",
    "instagram": "@ensinamais.tatuape",
    "endereco": "Rua Coelho Lisboa, 783 – Tatuapé, São Paulo",
    "whatsapp": "(11) 94475-0009",
    "colégios_vizinhos": ["Mendel", "Santo Antônio de Lisboa", "Espírito Santo"],
    "publico": "Pais de classes A/B do Tatuapé, filhos no Ensino Fundamental",
    "bairro": "Tatuapé",
    "cidade": "São Paulo",
    "zona": "Zona Leste",
}

# ─── KPIs Alvo ───────────────────────────────────────────────────────────────
KPIS = {
    "salvamentos_pct": 4.0,          # ≥ 4,0%
    "envios_dm_pct": 2.5,            # ≥ 2,5%
    "nao_seguidores_pct": 20.0,      # ≥ 20%
    "leads_semana_min": 15,
    "leads_semana_max": 25,
}

# ─── Formato do Carrossel ────────────────────────────────────────────────────
FORMATO = {
    "largura": 1080,
    "altura": 1350,
    "proporcao": "4:5",
    "slides_min": 7,
    "slides_max": 9,
    "palavras_por_slide_min": 30,
    "palavras_por_slide_max": 50,
    "max_carrosseis_semana": 2,
    "dias_feed": ["Terça", "Sexta"],
    "janela_horas_entre_posts": 72,
    "horarios_otimos": ["11:30", "12:30", "18:30", "19:30"],
}

TAG_NAVEGACAO = "Mova para o próximo ➔"

# ─── Fotos anexadas ao Gemini (opcional) ─────────────────────────────────────
# O app PRINCIPAL produz prompts e sugere quais fotos anexar no Google Flow.
# Anexar as fotos REAIS ao Gemini é opcional: com FLOW_FOTOS=true o Gemini
# recebe as cenas do catálogo (refs/) junto com o prompt de imagem; com
# false (padrão) a geração é só texto — mais barata e igualmente válida.
FLOW_FOTOS = os.environ.get("FLOW_FOTOS", "false").strip().lower() in {"1", "true", "yes", "on"}

# ─── Paleta de Cores Institucional (Alinhada com Google Stitch MCP) ───────────
CORES = {
    "primaria": "#2463eb",        # Azul Royal — destaque e ação principal (Google Stitch)
    "secundaria": "#76BC21",      # Verde Ação — conversão, CTA WhatsApp e aprovação
    "destaque": "#007799",        # Turquesa/Ciano Institucional Ensina Mais
    "perigo": "#F87171",          # Vermelho suave — erros e avisos
    "aviso": "#FBBF24",           # Âmbar — avisos leves e revisão
    "fundo": "#09090b",           # Fundo escuro profundo (Dark Zinc 950)
    "fundo_sec": "#121217",       # Fundo secundário
    "texto": "#F8FAFC",           # Texto principal — branco suave
    "texto_sec": "#94A3B8",       # Texto secundário — slate 400
    "borda": "rgba(255, 255, 255, 0.08)", # Bordas sutis glass
    "borda_forte": "#272732",     # Bordas de separação
    "card_bg": "rgba(24, 24, 31, 0.75)", # Cards com glassmorphism
    # UI do app (tema dark zinc)
    "app_bg": "#09090b",
    "app_card": "rgba(24, 24, 31, 0.75)",
    "app_card2": "#18181f",
    "app_borda": "rgba(255, 255, 255, 0.08)",
    "app_texto_muted": "#94A3B8",
    "app_sombra": "0 4px 14px -2px rgba(0, 0, 0, 0.5), 0 2px 6px -1px rgba(0, 0, 0, 0.3)",
    "app_sombra_hover": "0 10px 25px -3px rgba(36, 99, 235, 0.25), 0 4px 10px -2px rgba(0, 0, 0, 0.4)",
    # Radiação / glows para o hero e estados premium
    "glow_primaria": "rgba(36, 99, 235, 0.35)",
    "glow_secundaria": "rgba(118, 188, 33, 0.30)",
    "glow_destaque": "rgba(0, 119, 153, 0.30)",
    "gradiente_hero": "radial-gradient(1200px 400px at 20% -10%, rgba(36, 99, 235, 0.22), transparent 60%), radial-gradient(900px 300px at 90% 0%, rgba(0, 119, 153, 0.18), transparent 55%)",
    "gradiente_texto": "linear-gradient(100deg, #60A5FA 0%, #2463eb 50%, #007799 100%)",
    "raio_card": "16px",
    "raio_controle": "12px",
}

# ─── Design tokens do hero / stats (usados no cabeçalho premium) ─────────────
HERO = {
    "titulo": "Motor de Carrosséis",
    "subtitulo": "Conteúdo de Instagram com estratégia, do briefing ao cronograma.",
    "badge": "Ensina Mais Tatuapé",
}

# ─── Estados vazios centralizados (ícone + título + descrição) ───────────────
EMPTY_STATES = {
    "tendencias": {
        "icon": "📈",
        "titulo": "Nenhuma análise ainda",
        "desc": "Rode uma análise de tendências para descobrir o que está funcionando no Instagram educacional do Tatuapé.",
    },
    "ideias": {
        "icon": "💡",
        "titulo": "Nenhuma ideia gerada",
        "desc": "Gere ideias estratégicas (ou use as do NotebookLM) para começar a montar seus carrosséis.",
    },
    "selecao": {
        "icon": "✅",
        "titulo": "Nenhuma ideia selecionada",
        "desc": "Marque ideias na aba \"Ideias\" para usá-las em prompts, legendas e cronograma.",
    },
    "prompts": {
        "icon": "🎨",
        "titulo": "Nenhum prompt gerado",
        "desc": "Selecione uma ideia e gere os prompts de imagem em inglês para o Google Flow.",
    },
    "legendas": {
        "icon": "📝",
        "titulo": "Nenhuma legenda gerada",
        "desc": "Gere legendas de alta conversão conectadas ao tema do seu carrossel.",
    },
    "cronograma": {
        "icon": "📅",
        "titulo": "Nenhum cronograma ainda",
        "desc": "Gere um cronograma de postagens de 2 semanas com datas reais e protocolo das primeiras horas.",
    },
}

# ─── Fontes ──────────────────────────────────────────────────────────────────
FONTES = [
    str(Path(__file__).resolve().parent / "fonts" / "Montserrat-Bold.ttf"),
    str(Path(__file__).resolve().parent / "fonts" / "Poppins-Bold.ttf"),
    "/usr/share/fonts/noto/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]

# ─── Eixos Estratégicos ──────────────────────────────────────────────────────
EIXOS = {
    "Didático": {
        "cor": "#818CF8",
        "kpi": "Salvamentos ≥ 4%",
        "meta": "salvamentos",
        "descricao": "Resolução de problemas, técnicas de estudo, desconstrução de pegadinhas",
    },
    "Comportamental": {
        "cor": "#A78BFA",
        "kpi": "Envios DM ≥ 2,5%",
        "meta": "envios",
        "descricao": "Alívio de pressão acadêmica, ansiedade, rotina de estudos",
    },
    "Diagnóstico": {
        "cor": "#F87171",
        "kpi": "Leads WhatsApp 15-25/semana",
        "meta": "leads",
        "descricao": "Telas vs. robótica, autoavaliação, aula experimental",
    },
}

# ─── Tons de voz (ghostwriter) ─────────────────────────────────────────────────
# A persona CAROL define QUEM fala; o tom define COMO ela fala neste carrossel.
# Dois carrosséis do mesmo eixo escritos com o mesmo tom soam iguais — variar o
# tom é o jeito mais barato de o feed não ficar com cara de template.
TONES = {
    "automatico": "Automático (o eixo do carrossel decide)",
    "natural": "Natural — mãe falando com mãe",
    "didatico": "Didático — o professor explica o passo",
    "storyteller": "Storyteller — cena concreta que vira insight",
    "especialista": "Especialista — voz de quem domina o tema",
    "viral": "Viral — gancho forte e entrega rápida",
}
TONES_PADRAO = "automatico"

# Fallback do tom "automatico": cada eixo puxa o registro que melhor converte
# nele. Mesma lógica do KPI alvo em EIXOS.
TONES_POR_EIXO = {
    "Didático": "didatico",
    "Comportamental": "storyteller",
    "Diagnóstico": "especialista",
}

# ─── Diretório de dados persistidos ─────────────────────────────────────────
PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = str(PROJECT_DIR / "data")
METRICAS_FILE = str(PROJECT_DIR / "data" / "metricas.json")
HISTORICO_FILE = str(PROJECT_DIR / "data" / "historico_geracoes.json")
IDEIAS_ESTADO_FILE = str(PROJECT_DIR / "data" / "ideias_estado.json")
SQLITE_FILE = str(PROJECT_DIR / "data" / "motor_carrosseis.sqlite3")
BRIEF_FILE = str(PROJECT_DIR / "data" / "brief.json")
STORYBOARD_FILE = str(PROJECT_DIR / "data" / "storyboard.json")

# ─── Configurações do NotebookLM ─────────────────────────────────────────────
NOTEBOOK_ID_PADRAO = "7f415de3-0f02-4eb9-b5f1-3d104a00354a"
NOTEBOOK_TITULO_PADRAO = "Estratégia de Engajamento e Crescimento: Ensina Mais Tatuapé"
