# IDV — Agente de Prospeccao Misner

Registro da identidade visual da interface. Extraido de dois HTML que o usuario
enviou (11/11/2026). **Dali sai design, nao fluxo.** O fluxo e o que esta em
`PADRAO-N8N.md` e no backend `servico/`.

Nota de nome: o HTML escreve a marca com dois esses — **Missner**. O slug de
infraestrutura ja esta no ar como `misner` (VM, systemd, pasta no n8n) e fica
assim; na tela, a marca aparece como estiver no material do cliente. Confirmar
a grafia antes de imprimir em PDF para o cliente final.

---

## 1. Paleta (vem do HTML "Agente de Prospeccao")

Tokens em `:root`, com redefinicao para tema escuro. Sao as cores do cliente —
o azul do outro arquivo (Sebrae, `#0a5ba8`) **nao entra**.

### Claro

| token | valor | uso |
|---|---|---|
| `--navy` | `#1c2169` | hero, sidebar, logo, cabecalho de tabela |
| `--navy-deep` | `#141847` | contraste profundo, toast |
| `--navy-soft` | `#2a3086` | hover e estado ativo |
| `--ice` | `#eaf1f6` | fundo de tela |
| `--ice-deep` | `#dbe6ef` | divisorias sobre o fundo, trilha das abas |
| `--surface` | `#ffffff` | cards e paineis |
| `--steel` | `#8b93c9` | acento frio secundario, eyebrow, avatar |
| `--ink` | `#1a1e3c` | texto principal |
| `--muted` | `#5a6180` | texto secundario |
| `--hair` | `#e3e9f0` | hairlines e bordas |
| `--ok` / `--ok-bg` | `#2e7d6b` / `#e4f1ec` | ativa, concluido, sucesso |
| `--warn` / `--warn-bg` | `#b06a1f` / `#f6ecdd` | em execucao, atencao |
| `--focus` | `#3a42a8` | anel de foco |

### Escuro

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

Troca de tema por duas vias, nunca so uma: `@media (prefers-color-scheme: dark)`
sob `:root:not([data-theme="light"])`, e `:root[data-theme="dark"]` para o botao
manual. `body` sempre com fundo explicito.

---

## 2. Tipografia

| papel | familia | uso |
|---|---|---|
| texto | **Inter** 400/500/600/700 | tudo que e corpo, label, tabela |
| titulo | **Fraunces** 400/500, italico no tagline | h1, h2, titulo de painel |
| logo | **Cookie** (cursiva) | so a palavra da marca |

Tagline da marca: *"Um toque de cuidado"* — Fraunces italico, 15px, opacidade .82.
Eyebrow: 11–12px, `letter-spacing: .14em`, caixa alta, cor `--steel`, peso 600.
Numeros em tabela e CNPJ: `font-variant-numeric: tabular-nums`.

Google Fonts e a unica folha externa:
`Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,500;1,9..144,400;1,9..144,500`
+ `Inter:wght@400;500;600;700` + `Cookie`.

---

## 3. Estrutura (o que pegar de cada arquivo)

### Do "Agente de Prospeccao" — a casca do app

- **Login partido** em duas colunas (`1.05fr 1fr`): arte navy a esquerda com
  curva SVG em stroke branco a 55% de opacidade, formulario em superficie branca
  a direita. Marca em cima, pitch embaixo.
- **Sidebar navy fixa de 236px**: logo cursivo, unidade em caixa alta, nav com
  raio 8px (ativo = `rgba(255,255,255,.12)`), espacador, bloco de usuario com
  avatar circular `--steel`.
- **Abas de origem** em trilha `--ice-deep`, pilula branca na ativa com sombra
  de 1px. Sao as duas portas de entrada: filtro e planilha.
- **Painel** `--surface`, borda `--hair`, raio **14px**, padding fluido
  `clamp(18px, 2.6vw, 28px)`.
- **Grupos de filtro** com titulo eyebrow sublinhado e grid
  `repeat(auto-fit, minmax(190px, 1fr))`.
- **Zona de upload**: tracejado 1.5px `--steel`, raio 12px, vira `--ok-bg` no
  arrastar.
- **Tabela de dados**: cabecalho navy *sticky*, zebra em `color-mix`, hover
  `--ok-bg`, rolagem horizontal dentro de um container de raio 14px.
- **Toast** `--navy-deep`, canto inferior central, 2,6s.

### Do "Setup" — o andamento em etapas

- **Stepper de bolinhas** no topo: 28px, borda 2px, anel de foco de 4px na
  etapa ativa, linha de 2px que pinta ao concluir.
- **Espelho na sidebar**: a mesma lista de etapas, com o numero virando "check"
  quando passa.
- **Cartoes de bloco** com pilula numerada no titulo (raio 16px no original;
  padronizar em **14px**, que e o raio do resto do app).
- **Rodape fixo** com acao primaria a direita e "Voltar" discreto a esquerda,
  sobre gradiente que dissolve no fundo.
- **Tela final de confirmacao**: circulo com check, cartao de resumo
  chave/valor, botoes de exportar.
- **Layout do PDF** (jsPDF no original; aqui e reportlab no backend): faixa de
  cabecalho colorida de 30mm com marca a esquerda e tipo do documento a direita,
  faixa de 1,6mm mais escura logo abaixo, secoes numeradas com pilula, linhas
  chave/valor com hairline, rodape com data e marca.

**O que nao vem:** o azul do Sebrae, a marca Sebrae, o fluxo de 4 etapas de
setup de WhatsApp, o envio por Gmail e o roteiro de venda. Nada disso e deste
produto.

---

## 4. O que nao reaproveitar do HTML do agente

O arquivo e maquete: alguns campos contradizem o que ficou decidido.

- **Colunas de decisor** (`Decisor (QSA)`, `Cargo`) — o usuario cortou. A ordem
  valendo esta em `cnpj/colunas.py`.
- **Telefone e WhatsApp separados** — viram uma coluna so, `contatos`, porque
  nao se sabe de antemao qual numero tem WhatsApp.
- **Etapa "ReceitaWS"** no pipeline desenhado — nao existe: a base da Receita e
  carregada localmente e o enriquecimento e EmpresAqui + Apify.
- **Um CNAE principal + um secundario** — o teto real e **2 CNAEs por pesquisa**,
  e so no caminho do filtro. Pela planilha nao ha teto, porque ali CNAE e
  resultado, nao criterio.
- **"ate 10.000 linhas" no upload** — nao ha teto de linhas; a entrega e
  fatiada de 100 em 100.
- Login com credencial de demonstracao, estimativa de contagem chumbada e
  dados de exemplo sao enfeite de maquete.

---

## 5. Regras de implementacao

- Mobile a partir de 460px e 860px; a sidebar vira barra horizontal e o stepper
  perde os rotulos.
- `@media (prefers-reduced-motion: reduce)` zera transicoes.
- `:focus-visible` com anel de 2px `--focus` e offset de 2px — nunca remover.
- Multivalor na tela: uma linha por item dentro da mesma celula; no arquivo,
  `;` em CSV/XLSX e ` - ` no PDF, como ja esta em `cnpj/colunas.py`.
