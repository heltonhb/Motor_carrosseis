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

## 🔜 PRÓXIMO — Bloco 5: E3 + E4

- **E3. Testes com pytest.** Começar por `extract_json` (parser_nlm.py) com
  saídas reais do NLM — parte mais frágil do sistema. Mock de `processar_lote`
  já existe como base.
- **E4. ruff no fluxo.** Pegou `import re` inline e `except` genérico em
  prompts.py:221. Adicionar ao pyproject e rodar antes do commit.

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
- **V1.** Métricas automáticas via Instagram Graph API (conta é
  business; alimenta o `build_ideas_prompt_with_feedback` já existente).
- **V2.** Geração de imagem DENTRO do app (Imagen via mesma chave
  Gemini) em vez de copiar pro Flow.
- **V3.** Ciclo de vida por ideia (rascunho→aprovado→agendado→publicado)
  + registrar qual legenda foi usada → A/B real.
- **V4.** Backup dos dados (metricas.json + histórico) — export/import.

---

## Como retomar

1. `cd /home/helton/EM_material/Motor_carrosseis && git pull`
2. Ler este arquivo (MELHORIAS.md) para o estado do plano.
3. Próximo bloco: **P3+P4** (ver acima).
4. Fluxo de trabalho estabelecido: editar → testar (`test_image_fix.py`
   como modelo) → commit → push → atualizar este arquivo.

Histórico da avaliação original: sessão de 17/09/2026 (busca por
"sugestões de melhoria" no histórico de sessões do Hermes).
