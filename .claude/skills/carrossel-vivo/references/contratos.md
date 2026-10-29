# Contratos de dados

Formatos que o motor de carrosséis vivo consome. São JSON porque atravessam três
frentes: o que o Gemini gera, o que o Streamlit mostra e o que o renderer de
animação executa. JSON validável é o que permite testar sem abrir a interface.

Todos os campos são snake_case em português, coerente com `prompts.py`,
`templates.py` e `persistence.py`. Não introduza inglês no payload.

---

## brief

O brief é o que separa nível 1 de nível 2+. É a resposta às lacunas que o
modelo deixaria em aberto: para quem, com que objetivo, em que voz, com que
aparência.

Salvo em `data/brief.json` (um por carrossel, sobrescrito).

```json
{
  "tema": "Leitura apressada em prova de matemática",
  "eixo": "Didático",
  "publico_alvo": "Pais de 4º ano no Tatuapé que veem o filho errar por distração",
  "persona_alvo": "Vigilante",
  "tipo_hook": "dado_chocante",
  "tom": "didatico",
  "objetivo": "maximizar salvamentos",
  "kpi_alvo": "Salvamentos ≥ 4%",
  "cta": {"palavra_chave": "DESAFIO", "canal": "whatsapp", "telefone": "(11) 94475-0009"},
  "num_slides": 8,
  "referencias": ["fachada", "alunos_apoio"],
  "fidelidade": "media",
  "modo": "vivo",
  "trilha": {"mood": "didatico_energetico", "curva": "ease_out_cubic", "intensidade": "media"},
  "restricoes": [
    "não usar a Turma da Mônica",
    "não citar concorrente pelo nome"
  ]
}
```

Regras:

- `eixo` ∈ {`Didático`, `Comportamental`, `Diagnóstico`} — é o que decide o
  template (`templates.eixo_para_template`) e o KPI alvo (`config.EIXOS`).
- `cta.palavra_chave` não se inventa: leia de
  `templates.TEMPLATES[eixo]["cta_padrao"]`. Hoje são `DESAFIO` (Didático),
  `FOCO` (Comportamental) e `AULA` (Diagnóstico). Se um carrossel já gerado
  usar outra palavra, quem está errado é o carrossel — o template vence, e vale
  corrigir a origem, porque divergência aqui aparece como lead que não chega.
- `referencias` só aceita chaves de `refs_catalog.chaves_cenas()`. O validador
  já rejeita chave fora do catálogo, mas falha tarde e com custo de chamada —
  valide antes.
- `fidelidade` ∈ {`baixa`, `media`, `alta`}. Ver tabela abaixo.
- `modo` ∈ {`png`, `vivo`}. `png` é o padrão e não pode quebrar.
- `tom` — ver seção seguinte.

### Fidelidade

| Nível | O que copia da referência | Como pedir |
|---|---|---|
| `baixa` | paleta e clima geral | "use apenas a paleta e a atmosfera da referência" |
| `media` | paleta, tipografia, grid e hierarquia | "respeite paleta, tipografia e grid da referência" |
| `alta` | composição, ângulo e enquadramento | "reproduza a composição e o enquadramento da referência; só troque o texto" |

`alta` só faz sentido com imagem de referência anexável (`FLOW_FOTOS=true` e
`refs_catalog.anexos_gemini()`). Sem imagem anexada, degrade para `media` e
avise o usuário em vez de fingir que a alta fidelidade foi aplicada.

---

## tom

O "ghostwriter" é a voz. A persona CAROL continua sendo a base
(`prompts.py:SYSTEM_INSTRUCTION_PERSONA`); o tom ajusta o registro dela.

`automatico` escolhe pelo eixo: `Didático → didatico`,
`Comportamental → storyteller`, `Diagnóstico → especialista`.

| tom | Registro | Frases | Avoid |
|---|---|---|---|
| `natural` | mãe conversando com mãe no grupo do bairro | 8–14 palavras, curtas, zero jargão pedagógico | "olha, pessoal", "quer saber", "gente" |
| `didatico` | professor explica o passo, sem tom de palestra | 12–20 palavras, imperativo, numerado quando couber | "vamos aprender", "é importante lembrar" |
| `storyteller` | começa numa cena concreta e vira insight | uma imagem sensorial na primeira frase, 2–3 frases por slide | "imagina", "era uma vez", clichê motivacional |
| `especialista` | voz de quem conhece o tema e o mercado | 12–18 palavras, dados e critérios, zero exagero | "milagre", "revolucionário", "o melhor" |
| `viral` | gancho agressivo e entrega rápida | gancho ≤ 12 palavras, valor primeiro, CTA final | clickbait que não entrega,Caps Lock, emoji em excesso |

O tom muda **o texto**, não as regras de segurança do motor. Um carrossel `viral`
continua sem personagem da Mônica, continua com WhatsApp oficial e continua
proibido de prometer resultado.

---

## storyboard

Um objeto por slide. Para modo `png`, só `slide`, `tipo`, `texto` e `texto_overlay`
importam. Para modo `vivo`, o resto entra.

```json
{
  "modo": "vivo",
  "fps": 30,
  "slides": [
    {
      "slide": 1,
      "tipo": "Capa",
      "papel": "interromper o scroll",
      "texto": "Enunciado de problema típico cobrado no 4º ano",
      "texto_overlay": "Seu filho acerta e ainda perde a prova",
      "imagem": {"origem": "refs:alunos_apoio", "fidelidade": "media"},
      "animacao": {
        "duracao_s": 3.0,
        "entrada": {"tipo": "fade_subida", "duracao_ms": 450},
        "movimento": {"tipo": "ken_burns", "intensidade": 0.08},
        "saida": {"tipo": "corte_seco"}
      },
      "audio": {"cue": "impacto", "tempo_s": 0.0, "intensidade": 1.0}
    }
  ]
}
```

Regras do storyboard:

- `slide` sequencial a partir de 1; `tipo` vem de
  `templates.SlideEstrutura.tipo`.
- `duracao_s * fps` precisa ser inteiro. Arredonde ao construir o storyboard,
  não na hora de renderizar — é aqui que a dessincronia nasce.
- `tipo` é o papel estrutural do slide no funil e vem de
  `templates.SlideEstrutura.tipo` (`Capa`, `Segunda Capa`, `Entrega`, `Ponte`,
  `Prova`, `CTA`). `papel` é a função narrativa dentro deste carrossel — pode
  repetir entre slides, e é ele que justifica o movimento. Slide de leitura
  pede movimento contido; slide de interrupção (`Capa`) pede entrada forte.
- `texto_overlay` respeita o limite de palavras do slide (ver SKILL.md).
- `audio.cue.tempo_s` é absoluto no vídeo, não relativo ao slide. Isso é o que
  permite Several slides tocarem o mesmo beat.

Catálogo completo de `entrada`, `movimento`, `saida`, `cue` e as regras de
mistura está em `motion.md`.

---

## acervo

O acervo é o nível 7: o conjunto do que o usuário aprovou, destilado em DNA
reaproveitável. Um arquivo por carrossel aprovado, em `data/acervo/<slug>.json`.

```json
{
  "slug": "prova-matematica-4ano-desconstrucao",
  "titulo": "Por que a leitura apressada perde 3 pontos na prova",
  "eixo": "Didático",
  "tom": "didatico",
  "template": "desconstrucao_didatica",
  "criado_em": "2026-10-14",
  "aprovado_em": "2026-10-14",
  "fonte_pngs": "carrossel_14_10_2026/",
  "dna": {
    "paleta": ["#007799", "#58B947", "#FFC20E"],
    "tipografia": "geometric sans bold, titulo com marca-texto amarelada",
    "ritmo": {"entrada_ms": 400, "movimento": "ken_burns_sutil", "duracao_media_s": 3.2},
    "estrutura": ["gancho_numero", "erro_comum", "passo_a_passo", "prova", "cta_whatsapp"],
    "recursos": ["foto_real_unidade", "badge_verde_acao"]
  },
  "metricas": {
    "alcance": 4820,
    "taxa_salvamentos": 5.1,
    "taxa_envios": 1.2,
    "leads_whatsapp": 9
  }
}
```

Regras:

- **Só entra com aprovação explícita do usuário.** Isso vale para o registro
  inteiro: nem layout, nem tom, nem estrutura entram por semelhança ou boa
  intenção — só entra o que a pessoa aprovou de fato. Um rascunho esquecido no acervo
  envenena todos os briefings futuros — é pior não ter acervo nenhum.
- `dna` é descrição, não cópia. Guarde a lista de recursos e o ritmo, não o
  texto dos slides: o acervo existe para reaproveitar estrutura e linguagem
  visual, não para recarregar conteúdo velho.
- `metricas` é opcional e só entra depois que o post foi publicado e medido.
  Com `persistence.load_metricas()` você consegue o cruzamento por `titulo`.
- Na leitura, o motor injeta uma síntese dos 3 a 5 itens mais recentes no brief
  como `dna_referencia`. Não injete o acervo inteiro: contexto grande demais faz o
  modelo diluir as regras da marca.

---

## guia de estilo

Onde as regras visuais vivem. Hoje a fonte única é `padraesVisuais.txt`
(injetado em `prompts.PADRAO_VISUAL`) mais `config.CORES` e `config.FONTES`.

Se o guia virar estruturado, o formato é:

```json
{
  "versao": 1,
  "tokens": {
    "cores": {"primaria": "#007799", "acao": "#58B947", "destaque": "#FFC20E"},
    "tipografia": {"familia": "geometric sans", "peso_titulo": "bold"},
    "raio": {"card_px": 20, "badge": "pill"},
    "motion": {"entrada_padrao": "fade_subida", "duracao_entrada_ms": 400, "curva": "ease_out_cubic"}
  }
}
```

Regra dura: **uma fonte de verdade só.** Token duplicado em `config.py`,
`padraesVisuais.txt` e no guia estruturado diverge com o tempo, e a divergência
aparece como carrossel com a cor errada. Enquanto o guia estruturado não
existir, `config.py` e `padraesVisuais.txt` continuam sendo a fonte; o guia
precisa nascer como projeção deles, nunca como terceira lista independente.