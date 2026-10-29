---
name: carrossel-vivo
description: Use esta skill sempre que o pedido envolver carrossel do Motor de Carrosséis (Ensina Mais Tatuapé) e querendo mais do que PNG estático — carrossel animado/vivo em MP4, motion graphics, "quebrar" um slide, sincronizar efeito com música/batida, escolher tom de texto (ghostwriter), fidelidade a uma referência visual, style guide, storyboard, brief, criar um "modelo/layout" reutilizável ou salvar um carrossel no acervo/inspirações para o motor aprender com o que você gostou. Acione também quando o usuário reclamar que o carrossel parece "genérico", "cara de slop", "igual a todo mundo" ou pedir para "parar de rolar o feed", e quando for planejar melhoria do motor (novo módulo, tab_*.py, contrato de dados). É a ponte entre o motor atual (prompts de imagem + templates estáticos) e um carrossel vivo renderizado com Pillow + ffmpeg.
---

# Carrossel Vivo

## O princípio que sustenta tudo

O modelo de linguagem **não é um modelo de vídeo**. Ele escreve texto ou código — nunca pixels.

Isso é uma boa notícia para nós: quando o movimento é calculado por código em vez de gerado por um modelo de vídeo, o resultado é determinístico. O loop fecha, o texto fica nítido (é rasterizado uma vez e reaproveitado), e o efeito cai exatamente no segundo certo, todas as vezes.

Consequência prática, e ela é a regra mais importante desta skill:

> **Tudo que é visual-textual fica no prompt do Gemini (Fluxo/Google Flow). Tudo que é movimento, tempo, trilha e sincronia fica em código Python determinístico.**

Se você notar um slide se mexendo porque o modelo "deveria" ter animado, o desenho está errado: animação é trabalho do renderer, não do prompt de imagem.

## As sete escadas de maturidade

Este é o mapa que o usuário precisa enxergar para entender onde o motor está e o que falta. Quando alguém perguntar "por que meu carrossel parece genérico", responda com a escada, não com uma ferramenta cara — a diferença entre nível 1 e nível 7 é o que entra **junto** com o prompt (brief, storyboard, guia de estilo, referências, acervo).

| Nível | O que entra | Onde estamos | Lacuna |
|---|---|---|---|
| 1 | Prompt solto, uma frase | ❌ nunca ficamos aqui | — |
| 2 | Instruções fixas do projeto (o "CLAUDE.md" do motor) | ✅ `prompts.py`: `SYSTEM_INSTRUCTION_PERSONA`, `PADRAO_VISUAL` | — |
| 3 | Prompt grande + referência visual | ✅ `refs_catalog.py`, `refs/catalogo.json`, `padroesVisuais.txt` | fidelidade controlável (baixa/média/alta) |
| 4 | Skill que corrige e expande o prompt do usuário | ✅ `batch_engine.py`, `prompts.py:validate_prompts` | tom **selecionável** (o tom fixo da persona é o que falta aqui; a entrega do tom vem no nível 6a) |
| 5 | Imagem complexa de ferramenta paga | ⚠️ opcional (Flow/Imagen pago) | fora do escopo — mantenha opcional e nunca bloqueie por isso |
| 6 | Sistema de design: acervo, ghostwriter, fidelidade, "botão animar", trilha | ⬜ **PLANEJADO, não implementado** — ver Bloco 19 do `MELHORIAS.md` | ver `references/niveis.md` |
| 7 | O processo aprende com o que o usuário aprovou | 🟡 parcial — feedback loop existe para ideias (`build_ideas_prompt_with_feedback`), não para carrosséis aprovados | acervo |

Níveis 5 e 6 são os que separam "post genérico" de "post que segura o dedo". O nível 7 é o que impede o motor de voltar ao nível 1 em seis meses.

Detalhes do diagnóstico por nível e o que exatamente falta em cada um: leia `references/niveis.md`.

## Antes de falar em processo: ache o defeito concreto

Se o usuário reclamou de um resultado ("ficou genérico", "sem graça", "não é
a minha cara"), **abra o carrossel que ele viu** antes de explicar qualquer
teoria. A resposta genérica "o motor está no nível X da escada" é verdadeira e
inútil; a resposta útil aponta o slide 1 com um número inventado, ou o hex fora
da paleta, ou o layout repetido nas 8 lâminas.

Os artefatos estão em `data/historico_geracoes.json` (últimas 50 gerações,
com os prompts de cada slide) e nas pastas datadas da raiz
(`carrossel_14_10_2026/`). Se não houver nenhum, pergunte qual carrossel é —
mas pergunte em uma linha, não com um interrogatório.

Só depois do diagnóstico concreto é que a escada de níveis entra, como
explicação do **porquê** e plano de correção. Nessa ordem.

## Fluxo de trabalho

Quando o usuário pedir um carrossel (estático ou animado), siga esta ordem. Pular etapas é a forma mais rápida de voltar ao nível 1.

### 1. Enquadrar (brief)

Monte `brief.json`. Sem brief, o modelo adivinha — e adivinhando ele produz slop.

Campos e regras: leia `references/contratos.md`, seção "brief".

Perguntas que valem a pena fazer ao usuário (só as que mudam o resultado): tema/público, eixo estratégico, tom desejado, se existe referência visual, e se a peça final é PNG ou MP4.

Pedido de uma linha ("cria um carrossel sobre X") não é pedido de entrevista.
Escolha o padrão, declare a escolha em uma linha e entregue — o usuário corrige
o que quiser depois. Bloquear a entrega esperando resposta para tudo é o
caminho mais curto para o usuário desistir.

### 2. Escolher tom (ghostwriter)

O motor já tem uma persona (CAROL, em `prompts.py:build_ideas_prompt_with_feedback`), mas ela não é selecionável. O ghostwriter é o tom que a persona assume para este carrossel.

Tons disponíveis: `automatico`, `natural`, `didatico`, `storyteller`, `especialista`, `viral`.

Cada tom tem regras concretas (que palavras usar, que clichê evitar, tamanho de frase, chamada). Mapeamento completo em `references/contratos.md`, seção "tom". `automatico` = o eixo do carrossel decide (Didático→`didatico`, Comportamental→`storyteller`, Diagnóstico→`especialista`).

### 3. Definir fidelidade à referência

`baixa` (só paleta e clima), `média` (paleta + tipografia + grid), `alta` (composição e ângulo quase idênticos à referência).

A referência entra no prompt como `referencias[]` com chaves do catálogo (`refs_catalog.chaves_cenas()`) e como instrução de fidelidade. Sem referência, diga isso ao usuário: é a causa nº 1 de resultado sem graça.

### 4. Storyboard

Um objeto por slide com o papel (`Capa`, `Segunda Capa`, `Entrega`, `Ponte`, `Prova`, `CTA`), o texto, o prompt de imagem e — só para o modo vivo — entrada, movimento, duração e cue de áudio.

O papel do slide importa para a animação: `Capa` e `CTA` pedem movimento de entrada forte; `Entrega` pede movimento contido para não competir com a leitura. Contrato em `references/contratos.md`, seção "storyboard".

### 5. Imagens

Geração de imagem segue o caminho de sempre do motor (`batch_engine.gerar_prompts_ideia` → prompts para o Flow). O renderer de animação **reaproveita os PNGs prontos** — ele não inventa imagem nova.

Se o PNG ainda não existe e o usuário só quer ver o movimento, `image_utils.create_slide_from_template` já produz um rascunho fiel o suficiente para testar a animação. Diga ao usuário que está vendo um rascunho, não o arte final.

### 6. Animar (só quando o usuário pedir "vivo"/"animado"/"MP4")

Renderização em Pillow + ffmpeg do sistema. Receita completa, matemática de tempo, comandos ffmpeg e moods de trilha: `references/motion.md`.

Três regras que evitam a maior parte dos bugs:

- **Tempo em frames inteiros.** fps fixo, sem decimação. `tempo_s * fps` tem que dar inteiro, senão o áudio dessincroniza no meio do vídeo.
- **Texto rasterizado uma vez por slide**, reaproveitado frame a frame com matriz de transformação. Recompor o texto a cada frame é lento e produz serrilhado.
- **Nada de modelo no caminho do render.** Se o resultado está estranho, o bug está no spec ou no renderer, não no prompt.

### 7. Guardar no acervo

Só salvar no acervo o que o usuário aprovou explicitamente. Acervo não é histórico de rascunhos — ele é o DNA que vai ser injetado nos próximos briefings.

Ao promover um carrossel a acervo, extraia os tags de DNA (paleta, tipografia, ritmo de leitura, estrutura, tom) e amarre às métricas quando existirem. Contrato em `references/contratos.md`, seção "acervo".

## Regras que o renderer nunca pode quebrar

O motor tem validações duras (`prompts.py:validate_prompts`, `batch_engine._enforce_foto_real`). Animação é uma camada nova por cima, não uma escotilha para escapular delas.

- `4:5`, 1080×1350 (`config.FORMATO`). Nada de 9:16 — carrossel é quadrado vertical.
- CTA com o WhatsApp oficial `(11) 94475-0009` e a palavra-chave do eixo (`DESAFIO`, `FOCO`, `AULA`).
- `Mova para o próximo ➔` nos slides 1–7, nunca no 8.
- Slide 7 sempre com foto real da fachada; slides 1, 4 e 5 exigem foto real da unidade.
- Personagens da Turma da Mônica nunca são gerados — nem como imagem, nem como layer de animação.
- Texto do overlay: até 15 palavras por slide (3–8 nos slides 1, 4 e 5).
- Tudo dentro da área segura: entre `y=260` e `y=1070`, largura máxima 920px. Animation que desloca texto para fora da área segura quebra o feed.
- Fonte só do `fonts/` e do fallback do `config.FONTES`.
- **Qual paleta vale:** hoje existem duas e elas divergem. `padroesVisuais.txt`
  (`#007799` / `#58B947` / `#FFC20E`) é a paleta **da peça** — é a que
  `PROMPT_PROMPTS_IMAGEM` exige e a que `validate_prompts` checa (prompts.py:507).
  `config.CORES` (`#2463eb` / `#76BC21`) é o tema **do app**. Nunca cite `config.CORES`
  para o Gemini e nunca mande o modelo "seguir o padrão visual" sem dizer qual
  dos dois é. Se aparecer roxo, magenta ou qualquer hex fora de `padraesVisuais.txt`,
  é bug de paleta — não é escolha de estilo.

Se você mexeu em prompt, validador ou renderer, rode `uv run pytest -q` e `uv tool run ruff check .` antes de entregar. É barato e pega regressão de validação — o `validate_prompts` é a rede de segurança do motor inteiro, e uma mudança de tom ou de fidelidade pode, silenciosamente, quebrar uma regra de CTA ou de personagem.

Ao criar um `test_*.py` novo, lembre que `pyproject.toml` tem `testpaths` explícito: sem adicionar o arquivo lá, `uv run pytest -q` não roda o teste novo.

## Ambiente

- `ffmpeg` e `ffprobe` estão instalados no sistema (`/usr/bin/ffmpeg`). Não são dependência Python e não precisam entrar no `pyproject.toml`.
- Se `ffmpeg` não estiver presente, o modo PNG precisa continuar funcionando sozinho. Nunca torne a animação obrigatória para publicar.
- Dependências Python: só Pillow (já declarado). A trilha sintetizada usa `numpy`, que está instalado via pandas mas **não** está declarado em `pyproject.toml` — se você for usar numpy direto, acrescente-o ao `dependencies`, senão o app quebra em ambiente limpo.

## Referências

- `references/contratos.md` — formato exato de `brief.json`, tom, storyboard, acervo e style guide, com exemplos.
- `references/motion.md` — pipeline de render, matemática de tempo, comandos ffmpeg, moods de trilha, validação.
- `references/niveis.md` — diagnóstico por nível: o que já existe no motor, o que falta, e em qual ordem construir.

## Quando o pedido for planejar o motor

Se o usuário pedir para melhorar o motor em vez de gerar um carrossel, não escreva código imediatamente. Levante em qual nível ele quer chegar, use `references/niveis.md` para dizer o que isso custa, e registre a decisão em `MELHORIAS.md` seguindo o formato dos blocos existentes. O arquivo é o registro do plano do projeto — implementação fora dele se perde.