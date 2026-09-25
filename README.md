# Motor de Carrosséis — Ensina Mais Tatuapé

Gerador inteligente de carrosséis para Instagram com análise de tendências,
ideias estratégicas, prompts para o Google Flow, geração de imagens
com texto sobreposto e cronograma de postagens.

---

## Estrutura do projeto

```
Motor_carrosseis/
├── app.py              # Aplicativo Streamlit principal
├── main.py             # Entry point alternativo (python main.py)
├── config.py           # Constantes globais: unidade, KPIs, cores, fontes
├── prompts.py          # Todos os prompts do sistema para o Gemini
├── templates.py        # Templates de carrossel e dataclasses
├── gemini.py           # Cliente Gemini com retry, fallback e cache
├── image_utils.py      # Geração de imagens / texto sobreposto (Pillow)
├── persistence.py      # Leitura/escrita de dados em JSON local
├── pyproject.toml      # Dependências (uv)
├── .env.example        # Modelo de variáveis de ambiente
├── .streamlit/
│   └── secrets.toml    # Secrets para Streamlit Cloud (não commitar preenchido)
├── fonts/              # Fontes TrueType da marca (Montserrat-Bold.ttf, etc.)
├── templates_base/     # PNGs de base para os slides (opcional)
├── data/               # Dados persistidos localmente (criado automaticamente)
│   ├── metricas.json
│   └── historico_geracoes.json
└── 08-09-2026/         # Fotos reais da unidade (fachada, laboratório, alunos)
```

---

## Instalação e execução

### Pré-requisitos

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) instalado

```bash
# Instalar uv (se necessário)
pip install uv
```

### 1. Clonar / acessar o projeto

```bash
cd /home/helton/EM_material/Motor_carrosseis
```

### 2. Configurar a chave de API Gemini

**Opção A — variável de ambiente (recomendado para dev local):**

```bash
cp .env.example .env
# Edite .env e preencha GEMINI_API_KEY=sua_chave_aqui
```

O app carrega automaticamente o arquivo `.env` ao iniciar.

Para uma instalação compartilhada, defina `AUTH_REQUIRED=true` e configure um
provedor OIDC na seção `[auth]` de `.streamlit/secrets.toml`. O Streamlit usa
`st.login`, `st.user` e `st.logout`; o arquivo de secrets nunca deve ser
versionado.

Exemplo mínimo para desenvolvimento local com Google:

```toml
[auth]
redirect_uri = "http://localhost:8501/oauth2callback"
cookie_secret = "gere-um-segredo-longo-e-aleatorio"
client_id = "seu-client-id"
client_secret = "seu-client-secret"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

O armazenamento local usa JSON por padrão. Para ativar a migração gradual para
SQLite, defina `STORAGE_BACKEND=sqlite` no `.env`. O banco será criado em
`data/motor_carrosseis.sqlite3` e cada coleção existente será importada na
primeira leitura.

**Opção B — Streamlit Cloud / produção:**

Edite `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "sua_chave_aqui"
```

**Opção C — diretamente na UI:**

Cole a chave no campo da barra lateral ao abrir o app.
A chave fica apenas na memória da sessão; não é gravada em disco.

> ⚠️ Nunca commite `.env` ou `.streamlit/secrets.toml` com a chave preenchida.
> Ambos estão no `.gitignore`.

### 3. Rodar o app

```bash
uv run streamlit run app.py
```

Ou via entry point alternativo:

```bash
uv run python main.py
```

O app abre em **http://localhost:8501**

---

## Fluxo de trabalho

O app guia o usuário por um pipeline principal, indicado na barra de
progresso no topo:

```
📈 Tendências → 💡 Ideias → ✅ Seleção → 🎨 Prompts → 📝 Legendas → 📅 Cronograma
```

1. **Tendências** — Gemini organiza o que está funcionando no Instagram educacional
   para o público do Tatuapé. Resultado salvo em `data/historico_geracoes.json`.
2. **Ideias** — Gera 6 ideias estratégicas nos eixos Didático / Comportamental /
   Diagnóstico, com roteiro slide a slide.
3. **Seleção** — Marque quais ideias usar nas etapas seguintes.
4. **Prompts Google Flow** — Prompts em inglês para o Google Flow, com paleta
   de cores, referências de fotos (catálogo `refs/catalogo.json`), tag de
   navegação gerada junto com a imagem e texto sobreposto em PT-BR. Botão de
   copiar via clipboard; export `.txt` com a receita de série (gerar o slide 1
   primeiro e usá-lo como referência nos demais). Opcional: `FLOW_FOTOS=true`
   no `.env` anexa as fotos reais da unidade ao Gemini na geração.
5. **Gerador de Imagens** — Gera slides 1080×1350 px localmente com Pillow
   (upload de imagem, template único ou carrossel completo + ZIP).
6. **Legendas** — 3 opções de legenda com gancho, CTA, hashtags e contagem
   de caracteres (limite Instagram: 2.200).
7. **Cronograma & Métricas** — Grade semanal com datas reais, protocolo das
   primeiras 4h, registro de métricas e histórico persistido em disco.
8. **Lote** — Processa todas as ideias selecionadas de uma vez (prompts +
   slides + cronograma) e exporta ZIP.
9. **NotebookLM** — Consulta fontes do notebook, executa o pipeline completo e
   envia contexto para as demais etapas.
10. **Vídeo e histórico** — Monta requisições de vídeo, restaura gerações e
    permite exportar/importar um backup dos dados locais.

---

## KPIs Alvo

| Indicador                | Meta          |
|--------------------------|---------------|
| Salvamentos / Alcance    | ≥ 4,0%        |
| Envios DM / Alcance      | ≥ 2,5%        |
| Alcance Não Seguidores   | ≥ 20%         |
| Leads WhatsApp / semana  | 15 – 25       |

---

## Modelos Gemini utilizados (fallback automático)

| Prioridade | Modelo               |
|------------|----------------------|
| 1          | gemini-3.5-flash     |
| 2          | gemini-3.5-flash-lite|
| 3          | gemini-3.1-flash-lite|
| 4          | gemini-flash-latest  |

Em caso de rate limit (429) ou erro de servidor (5xx), o app faz retry
automático com backoff exponencial antes de tentar o próximo modelo.
Respostas idênticas são cacheadas na sessão para evitar cobranças duplas.

---

## Personalizações

| O que mudar           | Onde                          |
|-----------------------|-------------------------------|
| Dados da unidade      | `config.py` → `UNIDADE`       |
| KPIs alvo             | `config.py` → `KPIS`          |
| Cores / fontes        | `config.py` → `CORES`, `FONTES` |
| Adicionar template    | `templates.py` → `TEMPLATES`  |
| Editar prompts        | `prompts.py`                  |
| Fontes TrueType       | Adicione em `fonts/`          |
| Slides de base (PNGs) | Adicione em `templates_base/` |

---

## Dependências principais

| Pacote           | Uso                                    |
|------------------|----------------------------------------|
| streamlit        | Interface web                          |
| google-genai     | SDK Gemini                             |
| pillow           | Geração e composição de imagens        |
| pandas           | Tabela de histórico de métricas        |

Gerenciadas via `pyproject.toml` + `uv.lock`.
