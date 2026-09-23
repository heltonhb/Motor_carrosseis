# ROADMAP DE MELHORIAS — Motor de Carrosséis

Avaliação completa feita em 17/09/2026. Este arquivo é o registro do plano
de melhorias e do progresso. Atualizar a cada bloco concluído.

---

## ✅ CONCLUÍDO — Bloco 1 (2026-09-17, commit 93d04a0)

**P1 + P2 + M1 — Qualidade do que você publica**

- **P1. Fim do truncamento silencioso.** `image_utils.py` — novo
  `fit_slide_text()` com escada de fontes (60→54→48→42→36→30px): reduz a
  fonte até o texto caber na área útil (y 260–1070, largura 920px); só
  trunca (com "…") se nem no menor tamanho couber, e sinaliza no retorno
  (`truncated: True`, `dropped: N`). `create_slide_from_template`
  aceita `return_info=True`.
- **P2. Overlay com quebra de linha.** `add_text_overlay` agora usa
  `_wrap_text_pixels` (já existia, não era usado); fundo semi-
  transparente atrás do bloco inteiro; `multiline_text` centralizado.
- **M1. Revisão antes de gerar.** Aba 🖼️ Gerador de Imagens, Modo 3:
  expander "✏️ Revisar textos dos slides antes de gerar" com text_area
  por slide; o render usa os textos EDITADOS. Painel "⚠️ Avisos de
  ajuste" após gerar (fonte reduzida / texto cortado). Modo 2 idem.
- `generate_all_slides` → tupla `(nº slide, bytes, info)`; Lote (tab 7)
  ajustado.
- Testes: `test_image_fix.py` (passando) — fonte auto-reduzida, corte
  sinalizado, overlay quebrado em linhas, 3 slides do fluxo real.

## ✅ CONCLUÍDO — Bloco 2 (2026-09-17, commit XXX)

**P3 + P4 — Evitar perda de dados e avisos claros**

- **P3. Prompts e legendas não sobrescrevem mais.** Agora todas as
  gerações individuais (tab 3/4) e pipeline (tab 8) armazenam resultados
  em `session_state["prompts_lote"]` e `session_state["legendas_lote"]`
  (listas com índice), igual ao Lote já fazia com `results[f"prompts_{idx}"]`.
- **P4. Aviso de fallback quando ideias são fabricadas.** Quando o NLM
  não parseia JSON e o app usa o fallback (divide parágrafos), agora
  exibe `⚠️ Fallback: ideias genéricas criadas a partir do texto (não foram extraídas diretamente do NotebookLM).`

## ✅ CONCLUÍDO — Bloco 3 (2026-09-17, commit XXX)

**P5 + P6 — Confiabilidade técnica**

- **P5. Parser JSON unificado.** Criação de `parser_nlm.py` com `extract_json()` e `extract_json_list()`, centralizando toda lógica de parsing. Atualizadas as importações em `app.py` e `gemini.py`.
- **P6. Cache no Tab NotebookLM.** Adicionado `@st.cache_data(ttl=300)` a `list_notebooks()` (cache de 5 minutos).

---

## ✅ CONCLUÍDO — Bloco 4 (2026-09-17, commit pendente)

**E2 — Orquestrador único para Lote e Pipeline**

- Criado `batch_engine.py` com as funções compartilhadas:
  `gerar_prompts_ideia()`, `gerar_legendas_ideia()`, `gerar_cronograma()`,
  `gerar_slides_ideia()` e `processar_lote()` (com callback de progresso).
- Tab 7 (Lote): loop inline substituído por `processar_lote()`.
- Tab 8 (Pipeline): etapas 3/4/5 agora chamam `gerar_prompts_ideia()`,
  `gerar_legendas_ideia()` e `gerar_cronograma()`.
- Tabs 3 (Prompts) e 5 (Legendas) também usam as funções do engine.
- Imports órfãos limpos (PROMPT_LEGENDAS, PROMPT_PROMPTS_IMAGEM,
  generate_all_slides fora do app.py).
- Testado com mock (results keys + progresso corretos) e app no ar (HTTP 200).
- E1 (quebrar app.py em tab_*.py) fica para uma janela sem uso do app.

---

## ✅ CONCLUÍDO — Bloco 5 (2026-09-17, commit pendente)

**E3 + E4 — Testes e lint no fluxo**

- **E3.** 21 testes pytest passando:
  - `test_parser_nlm.py` (15): JSON limpo, bloco markdown, ruído antes/
    depois, vírgula extra, truncado (não crasha), sem JSON, aninhado,
    prefixo "Answer:" do NLM, listas.
  - `test_batch_engine.py` (6): lote completo, sem cronograma, multi-ideias,
    callback de progresso, API None não quebra o lote.
  - pytest + pytest.ini no pyproject (testpaths).
- **E4.** ruff configurado (E,F,W,I,UP,B; ignora E501 legado e B008 do
  Streamlit). De 100 erros → 0:
  - `import re` inline no app.py movido pro topo
  - `except Exception` em prompts.py:221 → `(ImportError, OSError, json.JSONDecodeError)`
  - variáveis `l` → `ln`/`leg` (E741), `key` → `_key` nos loops não usados (B007)
  - `zip(..., strict=True)` no image_utils (B905), whitespace, imports
- Comando: `uv tool run ruff check .` — rodar antes de todo commit.

---

## ✅ CONCLUÍDO — Bloco 6 (2026-09-17, commit pendente)

**M3 + M4 + M6 — UX de copiar, cache e histórico**

- **M4. Copiar de verdade.** `clipboard_button` agora usa
  `navigator.clipboard.writeText` via `components.html` (localhost é
  contexto seguro), com fallback `execCommand` para HTTP não seguro.
  Feedback "✅ Copiado!" e mantém o texto visível.
- **M6. Cache invalidado no clique.** "Gerar Ideias" chama
  `invalidate_cache(get_prompt_ideias())` sempre — cada clique gera lote
  novo. Adicionado botão "🔄 Forçar novas" (mesmo padrão da tab
  Tendências) para limpar as ideias atuais e recomeçar.
- **M3. Histórico navegável.** Nova tab "🗂️ Histórico": últimas 50
  gerações de data/historico_geracoes.json com filtro por tipo, resumo
  amigável (nº de ideias/slides/legendas/posts), JSON expandível e
  botão "↩️ Restaurar" que devolve a geração para o session_state
  correto (mapeia prompts/legendas para as listas _lote do P3).

---

## ✅ CONCLUÍDO — Bloco 7 (2026-09-17, commit pendente)

**M2 + M5 + P7 + P8 — Gráfico, calendário, modelos e XSS**

- **M2. Gráfico de KPIs ao longo do tempo.** Tab Cronograma & Métricas:
  line_chart (pandas) das taxas de salvamentos/envios/não-seguidores
  por data de publicação, com caption das metas.
- **M5. Export .ics.** Novo `ics_export.py`: cronograma → eventos
  VCALENDAR com fuso SP fixo (-03:00), parse de datas ISO/pt-BR,
  horários "19:30"/"18h"/"às 12h30", dia-de-semana isolado, escape e
  fold de linha (RFC 5545), lembrete 30min. Botão de download na tab 6.
  10 testes no test_ics_export.py.
- **P7. Modelos validados contra a chave real.** `_modelos_disponiveis()`
  no gemini.py: `@st.cache_data(ttl=3600)` filtra GEMINI_MODELS contra
  `client.models.list()`; os dois loops de fallback usam a lista
  validada. Offline/falha → lista estática como fallback.
- **P8. XSS fechado.** Helper `_esc()` (html.escape) aplicado em TODOS
  os pontos onde saída do LLM entra em st.markdown(unsafe_allow_html):
  render_idea_card (título, tema, badges, público, KPI, CTA, score)
  e render_schedule_day (dia, data, horário, canal, resumo, CTA).

---

## ✅ CONCLUÍDO — Bloco 8 (2026-09-17, commit pendente)

**E5 — Conflito .gitignore resolvido**

- `prompts_automaticacao.txt` estava trackeado E no .gitignore (o ignore
  não tem efeito sobre arquivo já trackeado). O arquivo é conteúdo
  legítimo (prompts reais de carrossel gerado) — decisão: remover do
  .gitignore e manter trackeado. Verificado: `git check-ignore` limpo.

---

## ✅ CONCLUÍDO — Bloco 9 (2026-09-17, commit pendente)

**V3 — Ciclo de vida da ideia + link legenda**

- **V3.1. Tracking de status por ideia.** Nova tabela `data/ideias_estado.json` com status 
  (rascunho → aprovado → agendado → publicado), legenda associada e data de publicação.
- **V3.2. UI com badge de status.** Cada card de ideia mostra badge colorido com emoji indicando 
  o status atual (📝/✅/📅/🚀).
- **V3.3. Botões rápidos de transição.** 
  - rascunho → ✅ Aprovar
  - aprovado → 📅 Agendar
  - agendado → 🚀 Publicar (salva data)
  - agendado/publicado → ⬅️ Reverter
  - ✅ Copiar legenda para clipboard
- **V3.4. Persistência.** Status e legenda salvos no disco por ideia (via persistence.py).
- Testes: existentes (backup, parser, engine) + UI testável manualmente.

---

## ✅ CONCLUÍDO — Bloco 10 (2026-09-17, commit pendente)

**V1 — Métricas automáticas via Instagram Graph API**

- **V1.1. Módulo `instagram_service.py`.** 
  - `fetch_post_metrics(token, account_id, post_ids)` retorna lista de métricas
  - Busca: impressões, salvamentos, shares (envios), comments
  - Calcula taxas automaticamente (salvamentos/alcance, envios/alcance)
- **V1.2. UI na Tab 6 (Métricas).**
  - Expander "⚙️ Configurar API do Instagram" com inputs para token e account_id
  - Botão "⬇️ Buscar Métricas do Instagram" → importa todas as métricas disponíveis
  - Salva automaticamente em `metricas.json` via `save_metrica()`
- **V1.3. Pré-requisitos.** Token de longa duração (90 dias) + Instagram Business Account ID
  - Criado em https://developers.facebook.com/tools/explorer/
  - Scopes: instagram_basic, pages_show_list, pages_read_engagement
- **V1.4. Mapeamento.** Converte o schema do Instagram → schema interno do app.

---

## ✅ CONCLUÍDO — Bloco 11 (2026-09-22)

**Sessão de Prompts — correções de comportamento (itens 1-4 da avaliação de 22/09)**

- **Segredo protegido.** `token_de_acesso_meta.txt` adicionado ao
  `.gitignore` (estava fora do ignore — um `git add .` commitaria o token).
- **Cache invalidado em toda geração (M6 estendido).** `batch_engine.py`
  ganhou `forcar=False` em `gerar_prompts_ideia`/`gerar_legendas_ideia`/
  `gerar_cronograma`/`processar_lote` → `invalidate_cache` com o mesmo
  prompt+ctx. Botões das abas Prompts/Legendas/Cronograma, Lote e Pipeline
  usam `forcar=True`: 2º clique gera lote novo em vez de devolver cache
  silencioso.
- **Seletor de gerações nas abas Prompts e Legendas.** Selectbox quando há
  >1 geração (nada fica escondido "só no último") + botão 🗑️ para remover.
- **Formato unificado de `prompts_lote`.** O Pipeline gravava o payload cru
  (sem `{titulo, prompts}`) e quebrava a exibição da aba 3; agora grava o
  mesmo formato da aba 3, com a ideia de origem junto. Entradas legadas do
  histórico são toleradas na leitura.
- **`validate_prompts()`** novo em `prompts.py` (+ `test_prompts_validate.py`,
  17 testes): 8 slides, prompt_en e paleta preenchidos, cláusula "text overlay
  in Brazilian Portuguese", overlay ≤15 palavras, sem "Arraste para o
  lado"/"Swipe" dentro do overlay, sem personagens da Turma da Mônica (a
  marca do logo é permitida), WhatsApp no slide final, e fidelidade do
  overlay ao texto aprovado do slide (overlap de tokens ≥40%). Exibida na
  aba Prompts (expander de avisos) e resumida no clique de gerar.
- **Regra 8 no `PROMPT_PROMPTS_IMAGEM`:** fidelidade ao roteiro — cada
  `text_overlay` deve ser resumo de ≤15 palavras do campo `texto` do slide
  correspondente; nunca inventar frases fora do roteiro.
- **Bug pré-existente corrigido:** `app.py` chamava
  `fetch_post_metrics(token, account_id)` com `account_id` indefinido
  (NameError no botão "Buscar Métricas") → `page_id`.
- `test_prompts_validate.py` adicionado ao `testpaths` do pyproject.
- Verificação: 47 testes passando, `ruff check .` zerado, app sobe
  (HTTP 200 + health ok) e o script completo executa sem traceback.

---

## ✅ CONCLUÍDO — Bloco 12 (2026-09-23)

**Avaliação de 22/09 — blocos 4-6 (sessão de prompts)**

- **Bloco 4 — identidade visual em fonte única.** `padroesVisuais.txt` virou a
  única fonte da spec (paleta/tipografia/formas/iconografia): `prompts.py`
  carrega o arquivo em `PADRAO_VISUAL` (fallback embutido se faltar) e o injeta
  no `PROMPT_PROMPTS_IMAGEM` — os blocos de identidade duplicados dentro do
  prompt e da persona foram removidos (a persona guarda só um resumo de 4
  linhas, para as tarefas de texto). Pastéis reatribuídos aos 4 cursos
  oficiais: azul claro → Matemática, coral → Português (era "Inglês", fora do
  portfólio), laranja → Programação, lima → Robótica; JSON de exemplo
  renomeado (`pastel_matematica`/`pastel_portugues`). Regra Turma da Mônica
  virou REGRA DUPLA (logo/fachada permitidos como referência fotográfica;
  gerar personagens proibido, com "no cartoon characters" obrigatório no
  prompt_en) na persona, no prompt de imagem (regra 7) e no prompt de vídeo.
- **Bloco 5 — swatch seguro, contagem local, contexto enxuto.** O swatch da
  paleta só pinta valores hex validados por `cor_eh_valida()` e escapa
  nome/valor com `html.escape` (fecha o XSS restante do P8 na aba Prompts);
  `char_count` das legendas passa a ser calculado localmente (`len()`, com
  fallback só se o texto não veio); `batch_engine._ctx_ideia()` serializa uma
  única vez só os campos relevantes — sem score/justificativa, sem duplicar
  `slides_sugeridos` — para prompts e legendas.
- **Bloco 6 — consistência entre as 8 lâminas.** Regra 9 (`base_prompt` em
  inglês com os hexes da marca, sem elementos de um slide) + regra 10 (gerar o
  slide 1 primeiro e usá-lo como referência/seed nos demais) no
  `PROMPT_PROMPTS_IMAGEM`; o app exibe o `base_prompt` com botão de copiar;
  `validate_prompts` cobra `base_prompt` presente com #007799/#58B947/#FFC20E.
- **Testes:** `test_prompts_validate.py` 17 → 25 testes (base_prompt
  ausente/sem hexes, paleta fora de hex, `cor_eh_valida`, injeção da fonte
  única, zero "Inglês" nas 3 fontes, regra dupla, regras 9/10).
- ⚠️ `padroesVisuais.txt` está **untracked** e virou dependência de runtime —
  `git add padroesVisuais.txt` antes do próximo commit (sem ele o app cai no
  fallback embutido).
- Verificação: 55 testes passando, `ruff check .` zerado, script completo
  executa sem traceback (exit=0), bloco do swatch testado contra XSS com
  entradas maliciosas.

---

## ✅ CONCLUÍDO — Bloco 13 (2026-09-23)

**Grupo 1 da avaliação de 23/09 — feedback loop real (itens 1-4 + item 7 parcial)**

- **Achado raiz.** `data/metricas.json` tinha **280 entradas de lixo** (título
  vazio, alcance 0, importadas 2× em 17/09). Como o
  `build_ideas_prompt_with_feedback` filtra por `alcance > 0`, o
  **aprendizado com métricas nunca rodou** — toda geração de ideias caía no
  prompt base, em silêncio. Causas: importador de CSV sem validação,
  salvando linha a linha (uma reescrita do arquivo por linha → duplicou no
  2º clique), e nenhum sinal na UI.
- **`importar_metricas()` (persistence.py).** Lote com **uma única escrita**,
  validação por linha (título + alcance > 0), normalização (`envios` →
  `envios_dm`, inteiros, taxas calculadas quando ausentes) e deduplicação
  por `titulo+data+alcance+instagram_post_id` contra o histórico e dentro do
  lote. Retorna resumo `{importadas, invalidas, duplicadas}`.
- **`save_metrica` endurecido.** Mesmo gate (rejeita sem título/alcance 0) e
  duplicata exata não entra mais (form manual não regride com cliques
  repetidos).
- **`limpar_metricas_vazias()`.** Remove em um clique as entradas que não
  alimentam o loop — botão 🧹 na aba Métricas mostra quantas existem.
- **Semáforo do feedback loop (aba Ideias).** 🟢 "ATIVO — N posts com
  métricas reais" vs 🔴 "INATIVO — registre métricas" — o estado antes
  invisível agora é explícito.
- **Selectbox de título no form de métricas.** Títulos de posts conhecidos
  viram dropdown (`accept_new_options=True`; o feedback casa por string de
  título — digitar à mão quebrava o casamento por typo). Fallback de
  digitação livre quando não há títulos ainda.
- **CSV com cabeçalho validado** (colunas obrigatórias checadas antes de
  importar) e session_state espelhado do disco após importar (o gráfico
  agora reflete a importação sem reiniciar o app).
- **`prompts.py`:** `posts_validos` também exige título não vazio (antes só
  checava `alcance > 0`).
- **API do Instagram** migrou para `importar_metricas` (mesmo gate +
  dedup unificado; antes comparava só `instagram_post_id` contra o
  session_state, que podia estar vazio).
- **Testes:** `test_metricas_feedback.py` novo (23 testes: validação,
  normalização, dedup, lote, limpeza, feedback loop vivo/morto/lixo) —
  suite total **78 passando**. `test_backup.py` incluído no `testpaths`
  (estava fora da coleta). Ruff zerado.
- **Integração verificada** com o CSV modelo oficial: 6 importadas →
  reimportação 0/6 duplicadas → loop ativo injetando o bloco de performance
  no prompt de ideias.

---

## 🔜 PRÓXIMO — restante do backlog

- **E1.** Quebrar app.py (~2.500 linhas) em tab_*.py + ui/styles.py
  (só fazer numa janela em que o app não esteja em uso).
- **V2.** Geração de imagem DENTRO do app (Imagen via mesma chave Gemini).
- **V3.** Ciclo de vida por ideia (rascunho→aprovado→agendado→publicado)
  + registrar qual legenda foi usada → A/B real.
- **V4.** Backup dos dados (metricas.json + histórico) — export/import.

## 📋 BACKLOG

### Corretude
- **P5.** Parser duplicado: `extract_json` (gemini.py) vs bloco inline
  no app.py (tab 2). Unificar num único módulo (ex. `parser_nlm.py`).
- **P6.** Tab NotebookLM dispara subprocess NLM a cada rerun — falta
  `@st.cache_data(ttl=...)` em `check_auth()`/`list_notebooks()`.
- **P7.** Verificar modelos Gemini contra `client.models.list()` com a
  chave real (a lista atual pode conter modelos inexistentes → warning
  + latência em toda chamada).
- **P8.** XSS latente: saída do LLM entra em `st.markdown(unsafe_
  allow_html=True)` sem `html.escape()` (render_idea_card,
  render_schedule_day). Prioridade sobe se for para o Streamlit Cloud.

### Estrutura
- **E1.** app.py com 2.300+ linhas → quebrar em `tab_<nome>.py`,
  `ui/styles.py`, `services/parser_nlm.py`.
- **E2.** Lote (tab 7) e Pipeline (tab 8) são o mesmo orquestrador 2×.
- **E3.** Zero testes — começar por pytest sobre `extract_json` com
  saídas reais do NLM (parte mais frágil do sistema).
- **E4.** Adicionar ruff ao fluxo (pegou `import re` inline, except
  genérico em prompts.py:221).
- **E5.** `prompts_automaticacao.txt` trackeado E no .gitignore (o
  ignore não tem efeito sobre arquivo já trackeado; decidir: `git rm
  --cached` ou remover do ignore).

### UX
- **M2.** Gráfico de KPIs ao longo do tempo (pandas já importado).
- **M3.** Histórico navegável: `data/historico_geracoes.json` guarda 50
  gerações e não há lugar para ver/restaurar.
- **M4.** Copiar de verdade: `navigator.clipboard.writeText` no
  `clipboard_button` (localhost é contexto seguro).
- **M5.** Cronograma → export .ics (Google Calendar).
- **M6.** "Gerar Ideias" 2ª vez devolve cache sem avisar — invalidar no
  clique ou avisar como Tendências já faz.

### Evoluções estratégicas (produto)
- **V1.** Métricas via importação CSV (Meta Business Suite) + link automático
  ao `build_ideas_prompt_with_feedback`.
- **V2.** Geração de imagem DENTRO do app (Imagen via mesma chave
  Gemini) em vez de copiar pro Flow.
- **V3.** Ciclo de vida por ideia (rascunho→aprovado→agendado→publicado)
  + registrar qual legenda foi usada → A/B real.
- **V4.** Backup dos dados (metricas.json + histórico) — export/import.

---

## ✅ CONCLUÍDO — Bloco 10 (2026-09-17, commit pendente)

**V1 — Métricas via importação CSV**

- **V1.1. Upload de CSV na Tab 6.** Novo botão "Carregar CSV" com leitor de 
  `data,titulo,alcance,salvamentos,envios,leads_whatsapp`.
- **V1.2. Importação automática.** Cada linha é salva como métrica no `metricas.json`
  com timestamp.
- **V1.3. Amostra.** Arquivo `data/metricas_sample.csv` com 6 linhas de exemplo.
- Testes: existentes (30 passando) + UI testável manualmente.

---

## Como retomar

1. `cd /home/helton/EM_material/Motor_carrosseis && git pull`
2. Ler este arquivo (MELHORIAS.md) para o estado do plano.
3. Próximo: **item 7 restante + item 8 da avaliação de 22/09/2026** (grupo 1
   CONCLUÍDO no Bloco 13 acima):
   - **Item 7 (restante).** Amarrar o ciclo de ponta a ponta: ao marcar uma
     ideia como "publicado", registrar qual legenda foi usada
     (`update_idea_status` já aceita `legenda_texto`) e estender o feedback
     loop para legendas/prompts, não só ideias (A/B real).
   - **Item 8.** README desatualizado (versões 3.5/3.1, "REST API" vs SDK,
     6 abas vs 10, `requests` como dependência) + escopo alcance vs.
     impressões na API do Instagram + limpar bloco duplicado "Bloco 10"
     deste arquivo + P6 (cache NLM) e E1 (quebrar app.py em tab_*.py).
4. Fluxo de trabalho estabelecido: editar → testar (`uv run --with pytest
   pytest -q` + `uv tool run ruff check .`) → commit → push → atualizar
   este arquivo.

Histórico da avaliação original: sessão de 17/09/2026 (busca por
"sugestões de melhoria" no histórico de sessões do Hermes).
