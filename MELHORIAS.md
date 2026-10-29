# ROADMAP DE MELHORIAS — Motor de Carrosséis

Avaliação completa feita em 17/09/2026. Este arquivo é o registro do plano
de melhorias e do progresso. Atualizar a cada bloco concluído.

---

## ✅ CONCLUÍDO — Bloco 16 (2026-09-24)

**Base para operação compartilhada e crescimento do armazenamento**

- Login OIDC opcional com `st.login`, `st.user` e `st.logout`; o modo local
  continua aberto quando `AUTH_REQUIRED=false`.
- Backend SQLite compatível com os mesmos documentos usados pelo JSON atual.
- Migração gradual: `STORAGE_BACKEND=sqlite` cria o banco e importa as coleções
  existentes na primeira leitura, sem alterar as funções públicas de persistência.
- `WAL` e transações SQLite ativados para melhorar a convivência entre sessões.
- Documentação e `.env.example` atualizados com as configurações de produção.

---

## ✅ CONCLUÍDO — Bloco 17 (2026-09-24)

**Navegação visual dos carrosséis**

- Nova regra nos prompts de imagem: exibir `Mova para o próximo ➔` nos slides
  1 a 7 e remover a tag do último slide.
- O campo `tag_navegacao` foi incluído no formato esperado da resposta.
- A geração local por templates passou a usar a mesma tag, mantendo o padrão
  entre imagens geradas e imagens renderizadas pelo app.

---

## ✅ CONCLUÍDO — Bloco 18 (2026-09-24)

**Thumbnails com presença real da unidade**

- Slides 1, 4 e 5 passaram a exigir composição de thumbnail com texto curto e
  foto real anexada pelo usuário, da recepção do Tatuapé ou de alunos em atividade.
- O prompt proíbe substituir essas fotos por banco de imagens, ilustrações ou
  alunos genéricos gerados por IA.
- O formato de saída declara `usa_foto_real` e `tipo_foto` para esses slides.
- A identidade visual foi alinhada à nova regra de navegação dos carrosséis.

---

## ✅ CONCLUÍDO — Bloco 14 (2026-09-24)

**Melhorias de curto prazo — confiabilidade do fluxo**

- Carregamento real do `.env` com `python-dotenv`; removido código que estava
  acidentalmente dentro do HTML de estilo.
- Substituição de `use_container_width` e `components.v1` por APIs atuais do
  Streamlit.
- IDs determinísticos adicionados às ideias para preservar o ciclo de vida.
- Barra de progresso e restauração alinhadas às chaves `prompts_lote` e
  `legendas_lote` usadas pela interface.
- Pipeline NotebookLM ampliado para gerar prompts e legendas para todas as
  ideias produzidas, com aviso por falha individual.
- Integração do backup ZIP na aba Histórico.
- Saídas do LLM escapadas nos cards HTML de tendências.
- Integração do Instagram corrigida para usar alcance, guardar impressões e
  buscar páginas adicionais de mídias.
- Script de inicialização corrigido para detectar a instalação do Streamlit.

## ✅ CONCLUÍDO — Bloco 15 (2026-09-24)

**Estado por sessão, caminhos portáveis e ciclo de publicação**

- Arquivos de dados, fontes e templates passaram a usar o diretório do projeto,
  independentemente do diretório de onde o app é iniciado.
- Cache de modelos Gemini, autenticação e notebooks do NotebookLM passou a ser
  por sessão, evitando compartilhar dados de contas diferentes.
- O cache de respostas Gemini passou a considerar uma impressão digital da
  chave atual; trocar a chave não reaproveita respostas de outra conta.
- Ciclo de vida das ideias agora possui ações na interface: aprovar, agendar,
  registrar publicação e reabrir como agendada.
- A publicação pode registrar data e legenda realmente usada.
- O cliente Gemini agora rejeita respostas JSON que não sejam objetos, evitando
  que arrays ou payloads inválidos quebrem as abas consumidoras.

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

---

## ✅ CONCLUÍDO — Bloco 20 (2026-10-14): V5 Ghostwriter (tons de voz)

**Uma voz fixada era a causa mais barata de "cara de template".** Dois
carrosséis do mesmo eixo saíam com o mesmo registro, porque a persona CAROL é
uma só. Dar ao operador a escolha do registro foi a mudança de melhor
custo-benefício do backlog: é prompt puro, sem custo de API além do mesmo.

- `config.TONES` com os 6 tons (`automatico`, `natural`, `didatico`,
  `storyteller`, `especialista`, `viral`), `TONES_PADRAO` e `TONES_POR_EIXO`
  (`automatico` resolve pelo eixo: Didático→didatico, Comportamental→storyteller,
  Diagnóstico→especialista; sem eixo, natural).
- `prompts.TONES` com a instrução de registro de cada tom (tamanho de frase,
  o que fazer, o que é proibido naquele registro) + `resolver_tom`, `tom_eh_valido`
  e `bloco_tom`.
- O bloco de tom entra em `get_prompt_ideias(tom)` e `get_prompt_legendas(tom, eixo)`
  — no prompt, não na temperatura: registro é instrução, não criatividade.
- `variacao=True/False` em `bloco_tom`: no lote de ideias, "automático" manda
  **variar** o registro conforme o eixo de cada uma; numa peça única (legenda),
  resolve pelo eixo da peça, porque não existe mistura dentro de um texto só.
- Âncora de segurança em todo tom (inclusive no automático): nenhum personagem
  da Turma da Mônica, nenhum número sem fonte, nenhuma promessa de resultado.
  `test_tom.py` falha se essa âncora sumir.
- UI: `tabs/_ui.seletor_tom()` reutilizável, ligado nas abas de Ideias e de
  Legendas com chaves de session_state distintas.
- `batch_engine.gerar_legendas_ideia(ideia, forcar, tom)` repassa o tom.
- `test_tom.py` (21 testes) + 2 testes de `test_metricas_feedback.py` ajustados
  para o novo contrato (o prompt de ideias não é mais idêntico à base isolada).

---

## ✅ CONCLUÍDO — Bloco 21 (2026-10-14): V6 Fidelidade à referência

**A referência já existia; o que faltava era dizer ao modelo o que fazer com
ela.** Sem isso, o prompt citava a cena do catálogo e o modelo caía no visual
padrão dele — a "cara de slop" que nenhuma ferramenta cara resolve.

- `prompts.FIDELIDADES` com os três níveis (`baixa` = só clima e paleta,
  `media` = paleta/tipografia/grid, `alta` = composição e enquadramento),
  `FIDELIDADE_PADRAO = "media"`, `fidelidade_eh_valida`, `resolver_fidelidade`
  e `bloco_fidelidade`.
- Alta fidelidade **degrada sozinha para média** quando não há imagem anexada
  (`FLOW_FOTOS=false`), com aviso entregue ao usuário na lista de avisos e no
  log. Degrade silencioso é o tipo de coisa que só se descobre olhando o
  resultado e achando que o motor "ignorou" o pedido.
- O bloco sempre repete que a foto real dos slides 1, 4, 5 e 7 é camada
  intocável: fidelidade alta não pode virar permissão para redesenhar aluno ou
  fachada.
- `batch_engine.gerar_prompts_ideia(..., fidelidade=)` e `processar_lote(...,
  fidelidade=)`; o `invalidate_cache` passou a usar o prompt composto, senão a
  troca de fidelidade devolveria a geração cacheada e o usuário não veria
  mudança nenhuma.
- UI: `tabs/_ui.seletor_fidelidade()` ligado nas abas de Prompts (lote e
  individual) e Lote, com aviso visível quando `FLOW_FOTOS` está desligado.
- `test_fidelidade.py` (19 testes), incluindo o teste do cache e o do repasse
  pelo `processar_lote`.

---

## ✅ CONCLUÍDO — Bloco 22 (2026-10-14): V7 Acervo (o motor aprende com o aprovado)

**Nível 7.** O feedback loop já existia para ideias; agora o carrossel
**publicado e com métrica no alvo** alimenta as gerações seguintes.

- `persistence.load_acervo` / `save_acervo` / `remover_acervo` /
  `get_acervo`, com o mesmo padrão de escrita atômica e respeitando
  `STORAGE_BACKEND` (um arquivo por registro no JSON, um documento no SQLite).
  Arquivo corrompido é ignorado em vez de derrubar a leitura do acervo todo.
- `acervo.py` novo: `slugify`, `alvo_do_eixo`, `extrair_dna`, `avaliar_promocao`,
  `promover_para_acervo`, `bloco_dna`, `resumo_acervo`.
- **Promoção por mérito, não por sorte:** exige status `publicado` **e** taxa de
  salvamento no alvo do eixo (alvo lido da mesma string de `config.EIXOS` que o
  prompt usa — os dois precisam concordar). O motivo da recusa sempre volta ao
  usuário. `forcar=True` existe para quem sabe mais que o motor.
- `extrair_dna` é determinístico (sem ida extra à API): estrutura, recursos
  (`foto_real_slide_N`, `referencias`), paleta — **só hexes de marca**, um roxo
  no prompt é bug, não padrão a aprender — e tipografia. **Nunca guarda o texto
  dos slides:** acervo que guarda conteúdo envelhece e vira ruído.
- `bloco_dna()` injeta os 5 registros mais recentes em forma de tags no prompt
  de imagem. Acervo inteiro no contexto faria o modelo diluir as regras da marca.
- UI: painel "Acervo" na aba de Prompts, com contagem, média de salvamentos,
  botão de promoção e o motivo da elegibilidade sempre visível.
- **Bug encontrado pelos testes:** `save_acervo` falhava em silêncio na primeira
  promoção porque `data/acervo/` não existia (`ensure_data_dir` só cria `data/`).
- `test_acervo.py` (25 testes) isolando o acervo em diretório temporário — teste
  nenhum toca `data/acervo/`.

---

## ✅ CONCLUÍDO — Bloco 23 (2026-10-14): V8 Brief e storyboard

**O contrato que a animação vai consumir.** O storyboard já é validado por
teste: as invariantes de tempo aparecem como asserção agora, e não como MP4
dessincronizado depois.

- `brief.py` novo: `montar_brief`, `validar_brief`, `montar_storyboard`,
  `validar_storyboard`, `resumo_storyboard`.
- Brief montado de forma determinística a partir da ideia, do template do eixo e
  da config — sem chamar o Gemini. Ele organiza o que o motor já sabe; uma ida
  à API aqui seria custo sem informação nova.
- O brief carrega os invariantes sozinho (palavra-chave do CTA do eixo,
  WhatsApp oficial, formato 4:5, referências mínimas do template, tom e
  fidelidade resolvidos). O usuário não precisa preenchê-los e não pode quebrá-los.
- Storyboard por slide: papel, texto, overlay cortado no limite de palavras
  (3–8 nos slides 1/4/5), imagem, entrada, movimento, saída e cue de áudio.
- **Tempo fechado aqui, não no renderer:** a duração de cada slide é ajustada em
  passos de 1 frame até `frames % frames_do_beat == 0`, e todo ajuste aparece
  como aviso. Os quatro moods da tabela foram conferidos (120/100/60 bpm com
  3,0/3,0/4,0 s) — e um teste falha se alguém mexer no BPM sem recalcular.
- Movimento por papel: slide de leitura (`Entrega`, `Prova`) é estático, porque
  ninguém lê por baixo de uma cena se mexendo; capa e CTA ganham entrada forte.
- Cues caem na grade de beats (beat mais próximo do início do slide).
- `persistence.salvar/carregar_brief` e `salvar/carregar_storyboard`
  (`data/brief.json`, `data/storyboard.json`), com `BRIEF_FILE`/`STORYBOARD_FILE`
  na config.
- UI: painel "Brief e storyboard" na aba de Prompts, com geração, métricas de
  duração e download do `storyboard.json` — o arquivo que o V9 vai renderizar.
- `test_brief.py` (24 testes).

---

## ✅ CONCLUÍDO — Bloco 24 (2026-10-14): V9 Carrossel vivo (o botão "Animar")

**Nível 6d.** O motor agora produz MP4 4:5 com entrada de texto, movimento de
câmera e trilha sincronizada no beat — por código, sem serviço pago.

- `carrossel_vivo.py` novo: `preparar_fundo`/`quadro_fundo` (movimento de
  fundo), `_camada_texto` (overlay rasterizado uma vez por slide),
  `_cor_de_contraste`, `_compor_frame`, `sintetizar_trilha`, `renderizar`,
  `renderizar_carrossel_vivo`, `pngs_do_carrossel`, `descrever`,
  `ffmpeg_disponivel`, `ffmpeg_versao`.
- Frames vão por pipe rawvideo direto para o ffmpeg — sem PNGs intermediários,
  sem nome de frame para embolar a ordem. MP4 sempre em `yuv420p` e
  `+faststart`: sem o primeiro o player do Instagram recusa o arquivo.
- Trilha sintetizada em numpy (pad harmônico no grid de beats + blip por cue +
  ducking) quando não há áudio local — serve para validar sincronia e para
  ter áudio onde antes não havia.
- `tabs/tab_animacao.py`: nova aba "🎬 Animar Carrossel" no `app.py`, com
  seletor de fidelidade, métricas (slides, duração, BPM, movimentos), botão de
  render, player do vídeo e download do MP4. Aborta com aviso claro se o ffmpeg
  não estiver no PATH — o modo PNG continua funcionando sozinho.
- **Três bugs reais encontrados na implementação:**
  1. Redimensionar o fundo a cada frame levava minutos por vídeo. Agora o fundo
     é pré-computado uma vez por slide e cada frame é só um recorte.
  2. A camada de texto era compartilhada entre slides e a opacidade de entrada
     era aplicada **in-place**: depois do primeiro frame o alfa ficava em 0 e o
     texto sumia do vídeo inteiro. Havia teste de regressão antes de acontecer
     em produção.
  3. Overlay branco sobre slide claro (sumia) e colado no topo, colidindo com o
     cabeçalho do slide. Agora a cor sai da luminância do fundo e o texto
     encosta na base da área segura (y=1070), nunca acima de 260.
- `test_carrossel_vivo.py` (18 testes): camadas, contraste, alfa em cache,
  easing, trilha e o MP4 final conferido com `ffprobe` (1080x1350, `yuv420p`,
  faixa de áudio, duração). Testes de render são `skipif` sem ffmpeg.
- Medido: 960 frames / 32 s renderizam em ~60 s.

---

## ✅ CONCLUÍDO — Bloco 25 (2026-10-15): demos do V9 — repetição de instrução e número sem fonte

**Achado gerando um carrossel de verdade** (`15-10-2026_exemplo/`), não em
teste sintético. As duas falhas saíram do mesmo payload real.

- **Instrução duplicada no prompt_en.** A regra 12 anexa a cláusula canônica da
  foto intocável, mas a checagem é por substring: quando o Gemini devolve a mesma
  instrução *parafraseada*, a cláusula entra por cima e o slide 7 saía com o
  parágrafo inteiro repetido duas vezes.
  - `batch_engine._dedup_frases` (e `_proteger_blocos`) removem frases quase
    iguais comparando sequências de tokens, com as palavras funcionais fora.
  - **As cláusulas do motor têm prioridade**: onde houver paráfrase do modelo
    fazendo o mesmo trabalho, sobrevive a do motor — é a que o validador exige na
    íntegra. Blocos de várias frases (a cláusula da fachada são três) são
    protegidos por marcador antes da comparação.
  - Duas passadas: uma no início (evita repetir trabalho) e outra depois de
    todas as regras automáticas, que é onde a paráfrase colide com a cláusula
    recém-anexada.
  - Regressão coberta: sem a distinção "cláusula presente × ausente", a dedup
    apagava a instrução dos slides que não tinham a cláusula do motor e o slide
    ficava sem regra nenhuma.
- **Regra 3b — dado sem fonte.** A persona proibia inventar *depoimento*, não
  estatística; o modelo respondeu "Irritação na lição de casa caiu 80% após 30
  dias" sem fonte nenhuma.
  - Regra nova no system instruction da persona: nenhum número, %, "3x", "2 mil"
    ou "milhares" sem citar fonte real (IBGE, INEP, PISA, SAEB, dados da
    unidade) ou sem estar marcado como observação da unidade.
  - `prompts.numeros_sem_fonte` no validador, com lista de fontes e de marcas de
    observação própria. Números que são conteúdo ("errou 5 questões", "turma do
    4º ano B") não disparam.
  - O validador **avisa**, não corrige: reescrever um dado inventado exige saber
    o fato, e isso é decisão humana.
- 10 testes novos (dedup, prioridade da cláusula do motor, números sem fonte).

---

## ✅ CONCLUÍDO — Bloco 26 (2026-10-15): regra 4 — o motor encurta o overlay

**O validador avisava; agora o motor corrige.** Texto que não cabe no celular
não é lido, e texto ilegível custa mais que texto curto.

- `batch_engine._cortar_overlay` + `_limite_overlay`: 15 palavras no roteiro
  curto, 8 nas thumbnails (slides 1, 4 e 5) — os mesmos limites do
  `padroesVisuais.txt`.
- Ordem do corte, do mais fiel ao texto ao menos fiel:
  1. frase completa (melhor caso);
  2. recuo até a última vírgula/ponto-e-vírgula dentro do limite — sem isso
     saía "a criança associa o erro a…", que lê como erro de escrita;
  3. corte por palavra com reticências, último recurso.
- O corte acontece **antes** da unificação da cláusula (regra 8), então
  `prompt_en` e `text_overlay` saem com o mesmo texto curto.
- Todo corte aparece na lista de correções com a contagem antes/depois: mudar
  palavra escrita é decisão visível, nunca silenciosa.
- Corrige-se um bug da própria dedup (Bloco 25): `CLAUSULA_SEM_PERSONAGENS`
  ("no cartoon characters") é fragmento curto, e protegê-lo como bloco a
  desmontava — a regra 7 sumia do prompt. Blocos só são protegidos quando são
  frases completas.
- 9 testes novos; suíte com 278 testes verdes. Geração real do dia fecha com
  **zero avisos** de validação.

## 🔌 PLANEJADO — Bloco 19 (2026-10-14): Carrossel Vivo

Origem: escada de 7 níveis de criação de carrossel do vídeo
"TZg-PgSxm3M" (Felipe Borges) adaptada ao Motor de Carrosséis. A skill que
detalha o plano está em `.claude/skills/carrossel-vivo/`
(SKILL.md + references/contratos.md, references/motion.md,
references/niveis.md).

Diagnóstico do motor hoje: **nível 4** (instruções fixas em `prompts.py`,
referências em `refs_catalog.py`, correção automática em `batch_engine.py`).
Alvo: **nível 6** (sistema de design) e **nível 7** (processo que aprende).

Status: **V5 a V9 concluídos** (Blocos 20–24). Restam o V10 (imagem
paga, opcional) e o backlog antigo (E1, V3, M3…).

Ordem deliberada — os três primeiros itens são prompt engineering puro, sem
custo e sem risco, e o renderer só faz sentido depois que o texto e a imagem já
estão bons:

- **V5 (6a).** Ghostwriter: `prompts.TOMES` + `config.TONS` com
  `automatico`, `natural`, `didatico`, `storyteller`, `especialista`, `viral`;
  seletor nas abas de ideias/legendas. Impacto alto, custo baixo.
- **V10 (5).** Geração de imagem paga dentro do app. Mantida **opcional** e
  fora de qualquer caminho obrigatório de publicação.

Contratos de dados, catálogo de movimento, matemática de tempo e armadilhas do
renderer: `.claude/skills/carrossel-vivo/references/`.

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
