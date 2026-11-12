# Identidade visual — Missner

De onde isto saiu: o **catálogo de produtos 2026/01** (o flip-book) e o site
`missner.com.br`. As cores não foram escolhidas por semelhança: foram medidas
pixel a pixel nas páginas do catálogo, com um script, e estão abaixo com o
nome da página de onde cada uma veio.

Uma versão anterior deste documento foi escrita a partir dos mock-ups do
agente de vendas e estava **errada**. O que ela dizia e o que é:

| a versão de mock-up dizia | o catálogo mostra |
|---|---|
| azul `#0A5BA8` | navy `#191961` |
| Space Grotesk nos títulos | serifada itálica (Playfair Display) |
| marca escrita em fonte | wordmark cursivo próprio, arquivo real |
| dark mode | não existe; a marca é navy sobre claro |

---

## Cor

Medidas com `PIL`, amostrando a cor dominante de cada página.

| token | valor | de onde |
|---|---|---|
| `--navy` | `#191961` | capa e lombadas do catálogo |
| `--navy-deep` | `#0e0e45` | derivado, para o estado pressionado |
| `--navy-ink` | `#081d5e` | o navy do próprio wordmark |
| `--peri` | `#4f5daa` | página "Um mix completo de produtos" |
| `--mint` | `#a4d9d0` | página "É no gesto de quem cuida" |
| `--mint-pale` | `#dcefe9` | derivado, fundo de aviso |
| `--salmao` | `#ffc9b8` | o display sobre o peri |

Superfícies e texto, derivados para uma ferramenta de trabalho — o catálogo é
peça impressa e não tem tabela nem formulário:

```
--ice        #f2f4fa     fundo de tela
--ice-deep   #e6eaf4     fundo recuado
--superficie #ffffff
--tinta      #15173a     texto principal
--cinza      #5a5f80     texto secundário
--borda      #e2e6f0     linha de 1px
--ok      #1f6b5a sobre --ok-bg      #dcefe9
--atencao #8a5a14 sobre --atencao-bg #f7e9d3
--erro    #b3261e sobre --erro-bg    #fbe3e1
--foco    #4f5daa
```

**Contraste medido, não julgado:** 23 pares de texto sobre fundo, nenhum
reprovado. Os mais apertados são `atenção/atenção-bg` em 4,94 e `ok/ok-bg` em
5,31, contra o mínimo de 4,5 que a WCAG pede para texto pequeno.

**Não há tema escuro.** A marca é navy sobre claro, e o catálogo inteiro é
assim. Inventar um tema escuro seria inventar identidade.

## A marca

O wordmark é o **arquivo de verdade da Missner**, não uma fonte parecida.
Ele entra como máscara PNG (`web/marca.png`, 14 KB) e a cor vem de
`currentColor`:

```css
.marca {
  background-color: currentColor;
  -webkit-mask: var(--marca) center / contain no-repeat;
          mask: var(--marca) center / contain no-repeat;
}
```

Um arquivo só serve nos dois usos — navy sobre claro, branco sobre navy.
Nenhuma fonte cursiva do Google chega perto o suficiente para valer a troca.

Tagline, do catálogo: **"Um toque de cuidado"**.

## Tipografia

| papel | família | de onde vem |
|---|---|---|
| display (h1) | **Playfair Display**, itálico 500 | a voz editorial do catálogo |
| interface, corpo | **Montserrat** 400/500/600/700 | é a fonte do site da Missner, lida do CSS dele |
| marca | o wordmark, imagem | arquivo da Missner |

Montserrat e não Poppins porque é a que a Missner já usa na web — medido em
`missner.com.br/css/custom.css`, não escolhido por gosto. Playfair Display em
itálico só nos títulos de tela: é o que dá ao catálogo o tom de cuidado, e em
texto corrido cansaria.

Números em `tabular-nums`. CNPJ e contagem desalinhados em coluna é o que faz
uma planilha parecer amadora.

## Acabamento

| propriedade | valor |
|---|---|
| raio de superfície | 14px |
| raio de controle | 8px |
| pílula | 999px |
| borda | 1px `--borda` |
| sombra de superfície | `0 1px 3px rgba(14,14,69,.08)` |
| respiro | `clamp(18px, 2.6vw, 28px)` |

Dois raios, não cinco. Dois raios parecidos na mesma tela é sujeira que
ninguém sabe nomear e todo mundo sente.

## Movimento e foco

Transição de `.15s` só em cor, fundo, borda e sombra; `translateY(1px)` no
toque. `prefers-reduced-motion` zera tudo.

O anel de foco de 2px em `--foco` **não sai**. É o único jeito de usar a
ferramenta sem mouse, e some de todo projeto porque alguém acha feio.

## Onde isto vive

```
prospeccao/web/estilo.css   tokens e base
prospeccao/web/marca.png    o wordmark, em máscara
prospeccao/web/app.html     a interface
prospeccao/web/montar.py    junta os três numa página só
```
