# Motor de Carrosséis — Ensina Mais Tatuapé

Gerador inteligente de carrosséis para Instagram com análise de tendências,
ideias estratégicas, prompts para Google Flow (ImageFX) e cronograma de postagens.

## Como rodar

```bash
cd /home/helton/EM_material/Motor_carrosseis
uv run streamlit run app.py
```

O app abre em http://localhost:8501

## Funcionalidades

### 1. Análise de Tendências
- Pesquisa automatizada via Gemini sobre tendências do setor educacional
- Dores dos pais no Tatuapé
- Sazonalidade escolar (provas, fechamento de notas)
- Oportunidades vs. concorrência

### 2. Ideias de Carrossel
- Gera 6 ideias estratégicas por execução
- 3 eixos: Didático (salvamentos), Comportamental (envios DM), Diagnóstico (leads)
- Filtragem por eixo temático
- Roteiro slide a slide incluído

### 3. Prompts Google Flow (ImageFX)
- Prompts em inglês para cada slide
- Paleta de cores consistente
- Texto sobreposto sugerido
- Botão de copiar prompt individual
- Exportação em JSON

### 4. Cronograma & Acompanhamento
- Grade semanal automática (2 carrosséis/semana)
- Respeita janela de 72h entre publicações
- Protocolo das primeiras 4 horas
- Formulário de métricas reais (salvamentos, envios, leads)
- Cálculo automático de taxas vs. metas
- Histórico de desempenho

## Configuração

1. Obtenha uma chave API em https://aistudio.google.com
2. Insira a chave na barra lateral do app
3. Pronto para usar!

## KPIs Alvo

| Indicador | Meta |
|-----------|------|
| Salvamentos/Alcance | ≥ 4,0% |
| Envios DM/Alcance | ≥ 2,5% |
| Alcance Não Seguidores | ≥ 20% |
| Leads WhatsApp/semana | 15-25 |

## Estrutura

```
Motor_carrosseis/
├── app.py              # Aplicativo principal
├── pyproject.toml      # Dependências
├── README.md           # Este arquivo
└── .venv/              # Ambiente virtual
```
