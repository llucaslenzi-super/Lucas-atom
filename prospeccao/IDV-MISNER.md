# IDV — identidade visual Missner

Extraída do **agente de vendas Missner que está no ar**, na instância da Atom:
Data Table `missner_ui_html`, 64 KB de HTML servidos em `/missner-app`.

Esta é a fonte. O que vier de maquete e divergir daqui está errado.

---

## Uma correção, registrada de propósito

A primeira versão deste documento foi escrita a partir de duas maquetes em
HTML e errou o essencial:

| eu havia escrito | o que o produto usa de verdade |
|---|---|
| navy `#1c2169` como cor da marca | **azul `#0A5BA8`** |
| `#0a5ba8` é "do Sebrae" e não entra em lugar nenhum | é **a** cor da Missner |
| Fraunces nos títulos | **Space Grotesk** |
| Cookie cursiva na marca | **Space Grotesk 700**, sem cursiva |
| raio único de 14px | **quatro** raios: 10, 14, 20 e 26 |
| paleta com tema escuro completo | o produto **não tem** tema escuro |

Maquete não é produto. Ficou registrado para ninguém reabrir a discussão com
o arquivo errado na mão.

---

## 1. Cor

```
--azul          #0A5BA8     a cor da marca
--azul-escuro   #003A6B     texto sobre claro, descritor da marca
--azul-claro    #EAF2FB     fundo de realce
--azul-linha    #CFE0F2     linha e texto secundário sobre azul
--superficie    #F4F7FB     fundo de tela
--branco        #fff        superfície de cartão
--borda         #E4E9F0     borda de 1px
--preto         #0F1720     texto principal
--cinza         #5A6676     texto secundário
--sucesso       #16794D     positivo
--erro          #B42318     negativo
--erro-bg       #FEF3F2     fundo do negativo
```

Apoios que aparecem no HTML: `#E7F4EE` e `#BFE3D0` (sucesso claro), `#FFF4E5`
e `#B54708` (atenção), `#FDCFCB` (erro claro).

**Não há tema escuro.** O produto no ar não implementa
`prefers-color-scheme`. Se um dia for feito, é decisão nova, não resgate.

---

## 2. Tipografia

Duas famílias, uma folha do Google Fonts:

```
fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700
                          &family=Space+Grotesk:wght@500;600;700
```

| papel | família |
|---|---|
| marca e títulos | **Space Grotesk** 500 · 600 · 700 |
| corpo e interface | **Inter** 400 · 500 · 600 · 700 |
| código, número cru | `ui-monospace` |

Escala observada, em ordem de uso: **13px** domina a interface, depois 14, 15 e
16; títulos em 22, 23, 28 e 30; marca em 52 na tela de entrada. Peso **600 é o
padrão** da interface — 18 ocorrências contra 6 de 700 e 4 de 500.

### A marca

Um bloco de duas linhas, sempre junto:

```
Missner            Space Grotesk 700 · line-height 1
AGENTE DE VENDA    caixa alta · 600 · espaçamento largo
```

| contexto | linha 1 | linha 2 |
|---|---|---|
| tela de entrada | 52px, `--azul`, `letter-spacing: -1.5px` | 15px, `--azul-escuro`, `letter-spacing: 7px` |
| barra do topo | 23px, branco, `letter-spacing: -.5px` | 10px, `#CFE0F2`, `letter-spacing: 3.5px` |

O contraste entre as duas linhas é o que faz a marca: a primeira é **apertada**
(tracking negativo), a segunda é **espalhada** (até 7px). Uma sem a outra perde
a assinatura.

No nosso produto a segunda linha muda de texto — **AGENTE DE PROSPECÇÃO** — e
mantém exatamente o mesmo tratamento.

Grafia: **Missner**, com dois esses, como está no título e no bloco da marca.
A infraestrutura usa `misner` e isso fica como está; o que o cliente lê é
Missner.

---

## 3. Acabamento

```
--r-sm   10px     controle: botão, campo
--r      14px     elemento médio
--r-lg   20px     cartão
--r-xl   26px     superfície grande
--sh     0 1px 2px rgba(16,23,32,.04), 0 8px 24px rgba(16,23,32,.06)
--sh-lg  0 16px 48px rgba(16,23,32,.16)
```

Quatro raios, não um. A escala é deliberada e vem do produto: controle 10,
médio 14, cartão 20, superfície 26.

Padrões medidos no HTML:

- **cartão** — fundo branco, borda 1px `--borda`, raio `--r-lg`, sombra `--sh`,
  respiro de 28px, 22px de distância entre cartões
- **pílula** — `border-radius: 999px`, 4px por 11px, 11,5px, peso 600,
  `letter-spacing: .2px`
- **botão sobre azul** — `rgba(255,255,255,.14)` com borda
  `rgba(255,255,255,.3)`, raio 10px, 8px por 14px, 13px, peso 600
- **caixa de marcação** — 17px por 17px, `accent-color: var(--azul)`
- **texto de apoio** — 16px, `--cinza`, com 14px acima e 30px abaixo

---

## 4. No PDF

O dossiê usa a mesma cor, em milímetros:

- faixa de cabeçalho em `--azul`, faixa fina em `--azul-escuro` abaixo
- texto da faixa em branco, linha secundária em `--azul-linha`
- título de seção com pílula, fundo `--azul-claro`, número em `--azul-escuro`
- linha chave/valor com hairline `--borda`
- rodapé em `--cinza`, marca à direita em `--azul-escuro`

---

## 5. Onde isto é aplicado

A interface do Agente de Prospecção é servida pelo n8n, no mesmo padrão do
agente de vendas: HTML guardado em Data Table e devolvido por webhook. Então a
identidade não é "inspirada" na do agente de vendas — é **a mesma**, servida do
mesmo jeito, na mesma instância.

O que muda é só o descritor da marca e o conteúdo das telas.
