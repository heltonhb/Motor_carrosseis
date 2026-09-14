"""
config.py — Constantes globais, dados da unidade e KPIs.
Centraliza toda configuração do app para facilitar manutenção.
"""

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

# ─── Paleta de Cores Institucional ──────────────────────────────────────────
CORES = {
    "primaria": "#6C8CFF",        # Azul brilhante — cor principal
    "secundaria": "#34D399",      # Verde suave — apenas estados positivos
    "destaque": "#818CF8",        # Índigo — acentos e links
    "perigo": "#F87171",          # Vermelho — erros e avisos
    "aviso": "#FBBF24",           # Âmbar — avisos leves
    "fundo": "#0A0A0F",           # Fundo escuro profundo
    "fundo_sec": "#111118",       # Fundo secundário
    "texto": "#E8E8ED",           # Texto principal — branco suave
    "texto_sec": "#8B8B9E",       # Texto secundário — cinza médio
    "borda": "#2A2A3C",           # Bordas discretas
    "card_bg": "#141420",         # Cards
    # UI do app (tema dark)
    "app_bg": "#0A0A0F",
    "app_card": "#141420",
    "app_card2": "#1A1A2E",
    "app_borda": "#2A2A3C",
    "app_texto_muted": "#8B8B9E",
    "app_sombra": "0 2px 8px rgba(0,0,0,0.4), 0 1px 3px rgba(0,0,0,0.3)",
    "app_sombra_hover": "0 8px 24px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3)",
    # Radiação / glows para o hero e estados premium
    "glow_primaria": "rgba(108, 140, 255, 0.25)",
    "glow_secundaria": "rgba(52, 211, 153, 0.20)",
    "gradiente_hero": "radial-gradient(1200px 400px at 20% -10%, rgba(108,140,255,0.22), transparent 60%), radial-gradient(900px 300px at 90% 0%, rgba(129,140,248,0.16), transparent 55%)",
    "gradiente_texto": "linear-gradient(100deg, #8AA4FF 0%, #6C8CFF 45%, #818CF8 100%)",
    "raio_card": "16px",
    "raio_controle": "10px",
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
    "fonts/Montserrat-Bold.ttf",
    "fonts/Poppins-Bold.ttf",
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

# ─── Diretório de dados persistidos ─────────────────────────────────────────
DATA_DIR = "data"
METRICAS_FILE = f"{DATA_DIR}/metricas.json"
HISTORICO_FILE = f"{DATA_DIR}/historico_geracoes.json"

# ─── Configurações do NotebookLM ─────────────────────────────────────────────
NOTEBOOK_ID_PADRAO = "7f415de3-0f02-4eb9-b5f1-3d104a00354a"
NOTEBOOK_TITULO_PADRAO = "Estratégia de Engajamento e Crescimento: Ensina Mais Tatuapé"

