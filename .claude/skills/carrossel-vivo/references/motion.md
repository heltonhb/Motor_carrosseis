# Motion — carrossel vivo com Pillow + ffmpeg

Pipeline completo: dos PNGs prontos até o MP4. Sem dependência Python nova,
sem modelo de vídeo, sem custo.

---

## Por que este caminho

O ffmpeg já está instalado no sistema. Pillow e numpy já são dependência do
projeto. Então a animação é um programa que roda no seu servidor, não um
serviço que você paga por chamado.

O tradeoff honesto: vídeo gerado por modelo acerta a cena viva e nunca acerta
o tempo; código acerta o tempo ao milissegundo e erra a cena viva. Para
carrossel de Instagram — 8 slides de 3 segundos, texto por cima, loop curto —
tempo é o que mais importa. Para cenas com personagem em ação, modelo ainda
ganha (nível 5 da escada).

---

## Matemática de tempo

Três invariantes. Se uma quebrar, a saída está errada:

1. **fps fixo, sem decimação.** `FPS = 30`. Todo tempo em segundos vira
   `frames = round(tempo_s * FPS)` e o frame count precisa ser inteiro.
2. **Beat inteiro em frames.** Um beat de `bpm` dura `1800 / bpm` frames.
   Se esse número não for inteiro, o beat não existe na grade e nada pode ser
   sincronizado com ele. Escolha o BPM **depois** de escolher a duração do
   slide, nunca antes.
3. **Duração por slide entre 2,5 s e 4,0 s.** Abaixo de 2,5 s o texto não
   termina de entrar; acima de 4 s o dedo cansa e a taxa de retenção cai. Um
   carrossel de 8 slides fica entre 20 s e 32 s.

### A combinação que fecha

`frames_do_slide % frames_do_beat` tem que dar zero. Estas quatro foram
verificadas com `FPS = 30`:

| mood | bpm | frames/beat | duração do slide | frames/slide | beats |
|---|---|---|---|---|---|
| `didatico_energetico` | 120 | 15 | 3,0 s | 90 | 6 |
| `urbano` | 100 | 18 | 3,0 s | 90 | 5 |
| `intimista` | 60 | 30 | 4,0 s | 120 | 4 |
| `frio` | 120 | 15 | 2,5 s | 75 | 5 |

BPM não é o que define o mood — curva, intensidade e paleta definem. O BPM só
precisa fechar a grade. Se você quiser outra duração, ajuste em passos de 1
frame até `frames_do_slide % frames_do_beat == 0`; quase sempre fecha em menos
de 10 frames de diferença.

Cues seguem a mesma regra: `tempo_do_cue = k * frames_do_beat / FPS`, com `k`
inteiro. É isso que faz o efeito cair no segundo certo todas as vezes. O cue
não precisa ficar exatamente na virada entre slides — se a grade e a virada não
coincidirem, ganhe o slide em até meio beat, que o olho não percebe.

Sanity check: a soma das durações precisa fechar com a duração real do vídeo
renderizado. Divergência aqui é arredondamento acumulado — corrija no storyboard,
não no ffmpeg.

---

## Camadas

Quatro camadas compostas frame a frame. Manter isso separado é o que dá o
"texto nítido":

| Camada | Fonte | Transformação por frame |
|---|---|---|
| fundo | PNG do slide (Flow ou `image_utils`) | pan/zoom lento (ken_burns) |
| overlay de foto | recorte do PNG, se `usa_foto_real` | parallax (o fundo anda mais rápido) |
| texto | RGBA rasterizado **uma vez** por slide | entrada + pulsação sutil |
| áudio | WAV separado | mixado no final |

Texto rasterizado uma vez e reusado é a diferença entre 3 s de render e 3 min,
além de eliminar serrilhado: escalar um RGBA com `resample=BICUBIC` é
visualmente superior a redesenhar glifos a cada frame.

---

## Vocabulário de movimento

Nomeie os efeitos por nome e mantenha o catálogo pequeno. Cada token é uma
função pura `(t, duracao, intensidade) -> parametro de desenho`.

### Entrada (primeiros 300–600 ms do slide)

| token | efeito |
|---|---|
| `fade` | opacidade 0→1 |
| `fade_subida` | opacidade + deslocamento vertical de 40 px para cima (padrão) |
| `slide_esquerda` | entra da esquerda, 60 px |
| `zoom_saia` | escala 1,06→1 com fade |

`fade_subida` é o padrão porque não compete com a leitura: o olho já está
procurando texto na horizontal, então movimento vertical é lido como
"chegando", não como "saindo".

### Movimento (durante o slide inteiro)

| token | efeito |
|---|---|
| `ken_burns` | zoom 1,00→1,08 distribuído no slide (padrão) |
| `parallax` | fundo a 1,00×, overlay a 1,12×, mesmo deslocamento |
| `pulso` | escala oscilando ±1,5% em seno, 2 ciclos |
| `estatico` | nada |

`estatico` é uma escolha legítima para slide muito denso de texto: movimento
atrás de texto longo derruba a legibilidade.

### Saída (últimos 120–200 ms)

| token | efeito |
|---|---|
| `corte_seco` | corta direto (padrão) |
| `fade_out` | some no preto |
| `desliza` | sai pela lateral, na direção da próxima entrada |

Prefira `corte_seco`. Transição elaborada entre slides de carrossel parece
publicidade, e publicidade é o que o usuário está tentando não parecer.

### Cues de áudio

`impacto`, `whoosh`, `click`, `pad`, `nenhum`.

O cue é posicionado em **tempo absoluto** no vídeo (contrato em `contratos.md`,
seção storyboard) e sempre encaixado na grade de beats. Na prática ele cai no
limiar entre dois slides, um instante antes da entrada do próximo. `impacto`
combina com capa e CTA; `pad` com desconstrução; `click` só em passos
numerados.

---

## Trilha

Trilha é mood, não arquivo solto. O mood define curva de entrada e intensidade
de movimento; o BPM é consequência da duração do slide (ver a tabela verificada
em "A combinação que fecha"), não o contrário.

| mood | curva de entrada | intensidade | uso |
|---|---|---|---|
| `didatico_energetico` | ease_out_cubic | alta | eixo Didático |
| `intimista` | ease_in_out_quad | baixa | eixo Comportamental |
| `urbano` | ease_out_quart | alta | Diagnóstico, oferta com prazo |
| `frio` | linear | baixa | conteúdo técnico, demonstração |

Três caminhos, em ordem de custo:

1. **Sem trilha.** MP4 mudo. Funciona no feed (o Instagram toca o áudio do
   vídeo, mas muitos users scrollam em mute). Entrega o básico sem risco.
2. **Áudio local** em `assets/trilhas/<mood>.wav`. Usuário traz um loop livre
   de direitos. 44,1 kHz, estéreo, duração ≥ a do vídeo em loop.
3. **Sintetizado** com numpy — pad harmônico mais arpejo no grid de beats,
   poucos segundos de código, zero arquivo. Serve para teste e para validar
   sincronia antes de gastar tempo com trilha real.

Regra de mixagem: trilha a −18 LUFS, cue a −10 LUFS,ducking de −6 dB da trilha
na janela do cue. Sem isso o cue é engolido e o vídeo parece sem som nenhum,
que é pior que sem efeito.

---

## Receita de render

Pseudocamada do pipeline (a implementação deve viver num `carrossel_vivo.py`,
fora desta skill):

```python
frames = total_frames(duracoes, FPS)
with open(tmp_png_dir / "frame_%06d.png", "wb") as sink:
    for i in range(frames):
        slide, local_t = locate_slide(i)
        base   = aplicar_fundo(png_slide, slide.animacao.movimento, local_t)
        over   = aplicar_overlay(base, slide.imagem, local_t)
        img    = aplicar_texto(over, rgba_texto[slide.slide], slide.animacao.entrada, local_t)
        img.save(sink)
```

Depois, mux com ffmpeg:

```bash
ffmpeg -y -framerate 30 -i frame_%06d.png \
  -i trilha.wav -c:a aac -b:a 192k \
  -c:v libx264 -pix_fmt yuv420p -crf 18 -preset slow \
  -movflags +faststart carrossel.mp4
```

`-pix_fmt yuv420p` não é opcional: sem ele o player do Instagram pode recusar o
arquivo. `-movflags +faststart` move o índice para o início, o que faz o vídeo
começar a tocar antes de baixar inteiro.

Se houver trilha e nenhum arquivo local, rode sem `-i trilha.wav` e sem
`-c:a`.

Confira a saída com `ffprobe` antes de mostrar ao usuário — duração real,
resolução e presença de faixa de áudio. Duração divergente da soma dos slides é
bug de arredondamento, não ajuste de container.

---

## Validação

Antes de entregar, `uv run pytest -q` com um teste novo (`test_carrossel_vivo.py`)
que:

1. valida o storyboard (papéis válidos, durações em faixa, `duracao_s * fps`
   inteiro);
2. marca o teste de renderização com `skipif` quando `ffmpeg` não existe no PATH,
   para o projeto continuar testável em máquina sem ffmpeg;
3. confirma via `ffprobe` que o MP4 gerado tem a duração esperada e 1080×1350.

Duração total fora de [20 s, 32 s] para 8 slides deve falhar o teste, não passar
silenciosamente. É o erro mais comum e o mais fácil de não perceber.

---

## Armadilhas

- **Texto saindo da área segura.** Animation que move o overlay além de
  `y=1070` ou da largura 920 px quebra o enquadramento no feed.
- **Zoom em imagem de baixo resolução.** PNG de 1080 px com ken_burns de 1,08
  passa da resolução nativa e borra. Se a fonte do slide tiver menos de 1080 px
  de largura, reduza a intensidade para 0,04 ou reencode maior.
- **Concatenar com `-f concat` de PNGs nomeados errado.** Zero-pad no nome do
  frame (`%06d`), senão a ordem embaralha.
- **GIF como saída.** Loop de 8 slides em GIF é pesado e o Instagram não
  suporta bem. MP4 é o alvo; GIF só para preview interno rápido.
- **Cache do Gemini.** Animation não passa pelo Gemini; não invalide cache por
  causa disso. O que invalida cache é mudança de prompt.