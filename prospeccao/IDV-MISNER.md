# IDV — Agente de Prospeccao Misner

Linguagem visual da interface: **cor, tipografia e acabamento**. Extraida dos
dois HTML que o cliente enviou (11/11/2026).

Aqui nao tem layout, nao tem componente, nao tem fluxo. Fluxo e tela sao o que
nos definimos; deste documento sai so como a coisa parece.

Grafia da marca: o material escreve **Missner**, com dois esses. O slug de
infraestrutura ja esta no ar como `misner` (VM, systemd, pasta no n8n) e fica
assim. Confirmar a grafia antes de ela aparecer num PDF de cliente.

---

## 1. Cor

As cores sao do cliente. O azul `#0a5ba8` do segundo arquivo e do Sebrae e
**nao entra em lugar nenhum**.

### Tema claro

| token | valor | papel |
|---|---|---|
| `--navy` | `#1c2169` | cor da marca; superficie escura e cabecalho |
| `--navy-deep` | `#141847` | contraste profundo |
| `--navy-soft` | `#2a3086` | estado sobre o navy |
| `--ice` | `#eaf1f6` | fundo de tela |
| `--ice-deep` | `#dbe6ef` | fundo recuado, divisoria sobre o gelo |
| `--surface` | `#ffffff` | superficie clara |
| `--steel` | `#8b93c9` | acento frio secundario |
| `--ink` | `#1a1e3c` | texto principal |
| `--muted` | `#5a6180` | texto secundario |
| `--hair` | `#e3e9f0` | linha de 1px |
| `--ok` | `#2e7d6b` | positivo |
| `--ok-bg` | `#e4f1ec` | fundo do positivo |
| `--warn` | `#b06a1f` | atencao |
| `--warn-bg` | `#f6ecdd` | fundo da atencao |
| `--focus` | `#3a42a8` | anel de foco |

### Tema escuro

| token | valor |
|---|---|
| `--navy` | `#2a3086` |
| `--navy-deep` | `#0f1230` |
| `--navy-soft` | `#3a42a8` |
| `--ice` | `#11142e` |
| `--ice-deep` | `#1a1e42` |
| `--surface` | `#191d3d` |
| `--steel` | `#9aa2d6` |
| `--ink` | `#e8ebff` |
| `--muted` | `#a2a9cf` |
| `--hair` | `#2a2f55` |
| `--ok` / `--ok-bg` | `#5fc7ab` / `#16352c` |
| `--warn` / `--warn-bg` | `#e0a862` / `#3a2c14` |
| `--focus` | `#8b93c9` |

Declaracao: tokens em `:root`; escuro por duas vias, sempre as duas —
`@media (prefers-color-scheme: dark)` sob `:root:not([data-theme="light"])`,
e `:root[data-theme="dark"]` para a escolha manual. `body` com fundo explicito.

---

## 2. Tipografia

| papel | familia | pesos |
|---|---|---|
| corpo | **Inter** | 400 · 500 · 600 · 700 |
| titulo | **Fraunces** | 400 · 500, com italico |
| marca | **Cookie** (cursiva) | 400 |

Uma folha externa, Google Fonts:

```
Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500
Inter:wght@400;500;600;700
Cookie
```

Tratamentos fixos:

- **marca** — Cookie, `letter-spacing: .5px`, `line-height: 1`
- **tagline** *"Um toque de cuidado"* — Fraunces italico, 15px, opacidade .82
- **titulo** — Fraunces peso 500, `letter-spacing: -.5px`, `text-wrap: balance`,
  corpo fluido `clamp(22px, 2.6vw, 30px)`
- **eyebrow** — 11–12px, caixa alta, `letter-spacing: .14em`, peso 600, `--steel`
- **rotulo** — 12,5–13px, peso 600, `--ink`
- **dica** — 11–12px, peso 400, `--muted`
- **numero, CNPJ, telefone** — `font-variant-numeric: tabular-nums`

---

## 3. Acabamento

| propriedade | valor |
|---|---|
| raio de superficie | **14px** |
| raio de controle (campo, botao) | **8px** |
| raio de pilula | `999px` |
| borda | 1px `--hair` |
| contorno tracejado (area de upload) | 1,5px `--steel` |
| sombra de superficie | `0 1px 3px rgba(20,24,71,.08)` |
| sombra de elemento flutuante | `0 8px 28px rgba(20,24,71,.3)` |
| padding de superficie | `clamp(18px, 2.6vw, 28px)` |
| transicao | `.15s` em cor, `.05s` no toque |
| toque do botao | `translateY(1px)` |

Estados:

- **positivo / concluido** — texto `--ok` sobre `--ok-bg`
- **em curso** — texto `--warn` sobre `--warn-bg`
- **hover sobre o navy** — `rgba(255,255,255,.06)`
- **ativo sobre o navy** — `rgba(255,255,255,.12)`
- **texto sobre o navy** — `rgba(255,255,255,.72)`, subindo a `#fff` no ativo
- **zebra** — `color-mix(in srgb, var(--ice) 55%, transparent)`
- **foco** — `:focus-visible` com anel de 2px `--focus` e offset de 2px.
  Nunca remover.

Reducao de movimento: `@media (prefers-reduced-motion: reduce)` zera transicoes.

---

## 4. No PDF

O dossie usa a mesma cor e o mesmo acabamento, em milimetros:

- faixa de cabecalho de 30mm em `--navy`, com faixa de 1,6mm em `--navy-deep`
  logo abaixo
- texto sobre a faixa em branco; linha secundaria em `#deebfa`
- titulo de secao com pilula de 6mm, raio 1,2mm, fundo `--ok-bg`, numero em
  `--navy-deep`
- linha chave/valor com hairline `--hair` de 0,2mm
- rodape acima de uma linha a 285mm, 7,5pt, `--muted`, marca a direita em
  `--navy-deep`
