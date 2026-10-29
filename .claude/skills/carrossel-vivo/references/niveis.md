# Os sete níveis — diagnóstico e ordem de construção

Referência rápida para responder "onde o motor está e o que falta". Use quando
alguém perguntar por que o resultado parece genérico, ou quando for planejar a
próxima melhoria.

---

## Nível 1 — prompt solto

Uma frase, sem instrução, sem referência. Resultado: SLOP. Cores padrão do
modelo, layout genérico, texto que could ser sobre qualquer assunto.

Nunca ficamos aqui. O `batch_engine` sempre injeta pelo menos persona, padrão
visual e catálogo de referências.

## Nível 2 — instruções fixas do projeto

O "CLAUDE.md" do motor. Em `prompts.py:SYSTEM_INSTRUCTION_PERSONA`
(persona CAROL, 4 personas de pai, 8 regras invioláveis, KPIs, formato) e
`prompts.PADRAO_VISUAL` (o conteúdo de `padroesVisuais.txt`).

O que resolve: a marca deixa de ser opcional e o modelo para de escolher cores
por conta própria. O que não resolve: todo carrossel nasce com a mesma cara.

## Nível 3 — prompt grande + referência visual

Referência é o que impede o modelo de cair no default. Já temos `refs/` com a
fachada, recepção, equipe, laboratório e alunos, indexados por
`refs/catalogo.json` e expostos por `refs_catalog.py` — e `FLOW_FOTOS=true`
anexa essas fotos ao Gemini.

**Lacuna:** fidelidade é implícita. O usuário não diz "copie só a paleta" ou
"reproduza a composição", e o motor não tem como oferecer a escolha. É o
parâmetro `fidelidade` de `contratos.md`.

## Nível 4 — skill que corrige o prompt do usuário

`batch_engine._enforce_foto_real` reescreve o output do modelo para garantir
foto real nos slides 1/4/5/7, tag de navegação, cláusula de texto sobreposto e
remoção de padrões proibidos. `prompts.validate_prompts` audita e devolve lista
de avisos. É o que segura o nível 4 mesmo com prompt ruim na entrada.

**Lacuna:** a persona é fixa. O nível 4 garante que o prompt esteja *correto*,
não que ele soe *diferente* — dois carrosséis do mesmo eixo saem com a mesma
voz. O ghostwriter selecionável (item 6a abaixo) fecha essa lacuna.

## Nível 5 — imagem complexa de ferramenta paga

Geração de imagem dentro do app (Imagen/Veo, Higgsfield e afins) resolve foto
realista de produto e cena complexa. Custo de créditos por imagem.

Decisão de projeto: **manter opcional e fora do caminho obrigatório**. Nenhum
fluxo pode depender de serviço pago para publicar. Se existir, é um seletor
ligado/desligado, como `config.FLOW_FOTOS` já faz hoje.

## Nível 6 — sistema de design

É o nível que esta skill constrói, e o maior salto de qualidade. Quatro
componentes independentes — dá para implementar em qualquer ordem:

### 6a. Ghostwriter (tom) — fecha a lacuna do nível 4 ✅ CONCLUÍDO (Bloco 20)

`prompts.TOMES` como dict, injetado em `SYSTEM_INSTRUCTION_PERSONA` ou como
bloco adicional no prompt de ideias/legendas. Seletor em `config.TONS`, com
`automatico` resolvido pelo eixo na entrada.

Impacto: alto. Custo: baixo (é prompt). **Comece por aqui.**

Entregue: `config.TONES`/`TONES_POR_EIXO`, `prompts.TONES` + `resolver_tom` +
`bloco_tom`, `get_prompt_ideias(tom)` / `get_prompt_legendas(tom, eixo)`,
`tabs/_ui.seletor_tom()` ligado nas abas de Ideias e Legendas, e `test_tom.py`.
Detalhe que só apareceu na implementação: o bloco de tom precisa repetir as
regras do motor (Mônica, número sem fonte, promessa), senão o tom vira uma
porta de entrada para asexatamente coisas que a persona proíbe.

### 6b. Fidelidade à referência ✅ CONCLUÍDO (Bloco 21)

Instrução derivada de `fidelidade` (`baixa`/`media`/`alta`) adicionada ao
`PROMPT_PROMPTS_IMAGEM`, com degrade automático de `alta` para `media` quando
não há imagem anexável.

Impacto: alto. Custo: baixo.

Entregue: `prompts.FIDELIDADES` + `resolver_fidelidade` + `bloco_fidelidade`,
`batch_engine.gerar_prompts_ideia(..., fidelidade=)`, `tabs/_ui.seletor_fidelidade()`
e `test_fidelidade.py`. Duas lições que só apareceram implementando: o
`invalidate_cache` precisa receber o prompt *composto* (com o bloco de
fidelidade), e o downgrade de `alta` para `media` tem de aparecer na lista de
avisos do usuário, não só no log.

### 6c. Storyboard + brief ✅ CONCLUÍDO (Bloco 23)

`data/brief.json` e storyboard como contrato entre a ideia e a imagem. O Gemini
passa a devolver timing e papel por slide, o que também serve à animação.

Impacto: médio. Custo: médio.

Entregue: `brief.py` (`montar_brief`, `validar_brief`, `montar_storyboard`,
`validar_storyboard`) + `persistence.salvar/carregar_brief` +
`test_brief.py`. O tempo é fechado no storyboard, não no renderer — foi o que
permitiu testar as invariantes antes de o renderer existir.

**Próximo passo real: 6d animação.**

### 6d. Botão "animar carrossel" ✅ CONCLUÍDO (Bloco 24)

Tab nova (`tabs/tab_animacao.py`) que pega os PNGs do carrossel aprovado e
renderiza o MP4. Movimento mínimo viável: fade na entrada + ken_burns + corte
seco + trilha opcional. É o ponto onde o carrossel deixa de ser "slides que
passam" e vira peça de motion.

Impacto: alto. Custo: alto. **Quarto passo — feito.**

Entregue: `carrossel_vivo.py` + `tabs/tab_animacao.py` + aba nova no `app.py` +
`test_carrossel_vivo.py`. Três armadilhas que o vídeo não fala e o código sim:
(a) pré-computar o fundo por slide, senão o render leva minutos; (b) nunca
aplicar a opacidade de entrada **in-place** na camada de texto cacheada — o
vídeo inteiro fica sem texto; (c) escolher a cor do overlay pela luminância do
fundo, porque o slide da marca é claro e texto branco some nele.

## Nível 7 — o processo aprende

Hoje o feedback loop existe para ideias: `prompts.build_ideas_prompt_with_feedback`
lê `data/metricas.json` e informa o modelo o que funcionou. Falta o mesmo para o
**carrossel aprovado**.

`data/acervo/*.json` guarda o que o usuário aprovou, destilado em DNA (paleta,
ritmo, estrutura, recursos). O prompt de imagem recebe uma síntese dos itens
mais recentes. ✅ CONCLUÍDO (Bloco 22) — `acervo.py` + `persistence.load/save_acervo`.

Isso exige função de leitura no motor: `persistence.load_acervo()` e
`persistence.save_acervo(registro)`, seguindo o padrão de `load_metricas`/`save_metrica`
(escrita atômica em `.tmp` + `os.replace`, e respeitando `STORAGE_BACKEND`).
Sem elas, o passo de injetar `dna_referencia` nos briefs não tem onde ler.

Duas condições para isso não virar lixo:

1. **Promoção explícita.** Nunca salve automaticamente. Um acervo com rascunhos
   ruins é pior que acervo vazio, porque o motor vai copiar o erro com
   confiança.
2. **Síntese, não despejo.** Injete os 3 a 5 itens mais recentes, em forma de
   tags. Contexto grande demais faz o modelo diluir as regras da marca.

Métrica que fecha o ciclo: o `data/acervo` pode ser cruzado com
`persistence.load_metricas()` para responder "qual tom gera mais salvamentos" —
e isso vira a próxima evidência do nível 7.

---

## Ordem recomendada

1. ~~**6a ghostwriter**~~ — ✅ feito (Bloco 20). **Próximo passo real: 6b fidelidade.**
2. ~~**6b fidelidade**~~ — ✅ feito (Bloco 21). **Próximo passo real: 7 acervo.**
3. ~~**7 acervo**~~ — ✅ feito (Bloco 22), com promoção por mérito (publicado +
   métrica no alvo). **Próximo passo real: 8 brief/storyboard.**
4. ~~**6c storyboard/brief**~~ — ✅ feito (Bloco 23). **Próximo: 6d animação.**
5. ~~**6d animação**~~ — ✅ feito (Bloco 24).
6. **Nível 5** — só se o cliente pedir e se o custo de créditos compensar.

Os itens 1 a 3 são prompt engineering puro. Faça os três antes de tocar em
renderer, porque o renderer anima o que o prompt já produziu — animar um
carrossel slop só faz o slop se mexer mais rápido.