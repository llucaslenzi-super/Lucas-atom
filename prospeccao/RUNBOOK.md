# RUNBOOK — Pipeline de Prospecção

Operação no Mac. Para a visão geral da arquitetura, ver [README.md](README.md).

---

## 1. Instalação no Mac (uma vez)

Requisitos: ~25 GB livres durante a carga, ~16 GB depois.

```bash
python3 --version        # precisa 3.10+. Se for menor: brew install python
```

```bash
git clone -b claude/relaxed-bardeen-lukpvm <url-do-repo>
cd Lucas-atom/prospeccao
```

```bash
python3 -m pip install duckdb
```

### Credenciais

Nunca no código. No `~/.zshrc`:

```bash
export EMPRESAQUI_TOKEN="..."     # empresaqui.com.br/acesso/api
export APIFY_TOKEN="..."          # console.apify.com → Settings → Integrations
```

Depois `source ~/.zshrc`. Gerar token novo no EmpresAqui **invalida o anterior**.

---

## 2. Montar a base (uma vez, ~40 min)

```bash
python3 -m cnpj baixar --completo
```

~4,7 GB em 37 arquivos Parquet. Tem retomada: se cair, rode de novo e ele pula o que já baixou.

```bash
python3 -m cnpj carregar
```

~15 min. Gera `dados/cnpj.duckdb` com ~16 GB e índices nos campos de filtro.

```bash
python3 -m cnpj conferir
```

**Não pule.** Se a ordem das colunas mudar numa edição futura da base, os dados carregam **sem erro nenhum** e ficam silenciosamente trocados. O `conferir` imprime contagem por UF e uma amostra — se SP não for o maior estado, ou se a razão social aparecer no campo errado, pare.

Referência da carga de **outubro/2026**:

| tabela | linhas |
|---|---|
| estabelecimentos | 73.809.379 |
| empresas | 70.517.438 |
| simples | 50.806.102 |
| socios | 28.495.961 |

| UF | estabelecimentos |
|---|---|
| SP | 21.369.926 |
| MG | 7.988.006 |
| RJ | 6.253.182 |
| PR | 5.029.433 |
| RS | 5.015.901 |
| SC | 3.607.531 |

Depois de conferir, dá pra liberar 4,7 GB apagando os Parquet — mas aí um recarregamento exige baixar de novo:

```bash
rm -rf dados/bruto
```

---

## 3. Uso

### Descobrir o CNAE

```bash
python3 -m cnpj cnaes --busca tecelagem
```

### Porta A — filtro

Sempre conte antes de gastar:

```bash
python3 -m cnpj buscar --uf SC,PR --cnae 13 --matriz --contar
```

Depois corte e exporte:

```bash
python3 -m cnpj buscar --uf SC,SP,RS,PR,MG,RJ,MT --cnae 13,14 --matriz --porte medio --limite 300 --ordenar contato --out lista.csv
```

| flag | efeito |
|---|---|
| `--cnae 13,14` | prefixo: `13` pega a divisão toda, `1322300` pega o código exato |
| `--matriz` | **use quase sempre** — sem isso, 9 agências do mesmo banco viram 9 "leads" |
| `--ordenar contato` | prioriza quem já tem telefone/e-mail no cadastro — economiza requisição |
| `--com-contato` | descarta de saída quem não tem contato nenhum |
| `--capital-min` | corte por capital social |
| `--abertura-de 20200101` | empresas abertas a partir da data |

Sem `--cnae`, vêm **todos os CNAEs**.

### Porta B — planilha

```bash
python3 -m cnpj planilha ~/Downloads/clientes.xlsx --out lista.csv
```

Detecta a coluna de CNPJ sozinho (a que tiver mais valores passando no dígito verificador), deduplica e descarta inválido. Aceita `.xlsx` e `.csv`, com ou sem pontuação.

### Enriquecer e exportar

```bash
python3 -m cnpj enriquecer lista.csv --lote 10 --apify --out leads.csv
```

| flag | efeito |
|---|---|
| `--lote 10` | grava parcial a cada 10 — queda no meio não perde trabalho |
| `--apify` | roda Maps + Instagram em 100% do lote |
| `--linkedin` | inclui decisor (caro — ver custos) |
| `--teto-usd 5` | teto duro de gasto por run do Apify |

---

## 4. O portão

O filtro é grátis e devolve centenas de milhares em segundos. O enriquecimento é **1 requisição por segundo**.

| volume | tempo de enriquecimento |
|---|---|
| 300 | 5 min |
| 1.000 | 17 min |
| 10.000 | 2h47 |
| 100.000 | 28 h |

**Nunca mande o resultado bruto do filtro direto pro enriquecimento.** Conte, ranqueie com `--ordenar`, corte com `--limite`. Ranquear é de graça — os dados da Receita já estão no disco.

---

## 5. Actors do Apify

IDs **públicos** — qualquer conta usa os mesmos, com o próprio token. O que é secreto é o `APIFY_TOKEN`.

### Em uso

| Actor | ID | Papel |
|---|---|---|
| `vortex_data/google-maps` | `AabCualFIriz3X6Fs` | tel, e-mail, WhatsApp, @IG, categoria |
| `apify/instagram-profile-scraper` | `dSCLg0C3YEZ83HzYX` | bio, site, categoria — **pelo handle** |
| `harvestapi/linkedin-company-employees` | `Vb6LZkh4EqRlR0Ka9` | decisor por cargo |

### Opcional

| Actor | ID | Quando |
|---|---|---|
| `harvestapi/linkedin-profile-scraper` | `LpVuK3Zozwuipa5bp` | só se você já tem a URL do perfil |

### Proibido

| Actor | ID | Por quê |
|---|---|---|
| `apify/instagram-search-scraper` | `DrF9mzPPEuVizVF4l` | **lixo.** "lenceria paraguay" devolveu hospital no Azerbaijão e cinema na Índia. Instagram é sempre pelo handle. |

### Custos medidos

| Actor | runs | gasto |
|---|---|---|
| google-maps | 9 | US$ 0,89 |
| instagram-profile | 4 | US$ 0,07 |
| linkedin-company-employees | 4 | US$ 0,21 |

Total da exploração: **US$ 1,31**.

⚠️ **Conta no plano FREE.** Maps sai ~US$ 0,10 por run; um lote de 10 é 1 run. O crédito grátis dá na casa de 500 empresas/mês. Rodando Apify em 100%, esse é o teto antes de precisar de plano pago.

---

## 6. Limites e garantias

**EmpresAqui** — 1 req/s por token. 401/403 aborta na hora; 429 e 5xx entram em backoff exponencial. Sem cota de volume no plano atual.

**Cobertura parcial do enrichment** — medido em 05/11/2026: de 11 CNPJs consultados, **4 voltaram com `enrichment: null`** e os demais vieram com campos vazios. Por isso o Apify roda em 100%, não só nos furos.

**Dados mascarados** — alguns registros vêm ofuscados (Petrobras: `********@*********.***.**`). É da fonte, não do parser.

**Nunca inventa contato.** Campo sem dado sai vazio no CSV.

**Procedência por campo** — `fonte_telefone`, `fonte_email`, `fonte_whatsapp` dizem de qual camada veio cada dado. Necessário para auditoria e LGPD.

**Casamento do scraping** — por similaridade de nome, piso 0,62. Abaixo disso não casa: prefere deixar vazio a errar. É o caso "Lazos" → "Frigorífico Los Lazos".

**Cache permanente** — em `dados/empresaqui.sqlite`. Rodar de novo é instantâneo; matar no meio e religar não reprocessa. Apagar o arquivo força reconsulta de tudo.

---

## 7. Manutenção

**Mensal** — a Receita republica a base. Para atualizar, edite a competência em `cnpj/config.py` (`FONTE_ESPELHO_HF`), depois:

```bash
rm -rf dados/bruto dados/cnpj.duckdb && python3 -m cnpj baixar --completo && python3 -m cnpj carregar && python3 -m cnpj conferir
```

O cache do EmpresAqui **não** deve ser apagado nessa troca — ele é por CNPJ e continua válido.

**Rotação de token** — ao rotacionar no EmpresAqui, o anterior para de funcionar na hora. Atualize o `~/.zshrc` antes de rodar lote longo.

---

## 8. Problemas comuns

| sintoma | causa | o que fazer |
|---|---|---|
| `Could not set lock on file` | outro processo usando o DuckDB | espere a carga terminar, ou feche a outra sessão |
| `Defina EMPRESAQUI_TOKEN` | variável não exportada | `source ~/.zshrc` |
| HTTP 401/403 no EmpresAqui | token rotacionado ou inválido | gere outro em `/acesso/api` |
| enriquecimento devolve tudo vazio | cobertura parcial da fonte | use `--apify` |
| `nenhum CNPJ aproveitável` | coluna não detectada | confira se a planilha tem CNPJ com 14 ou 8 dígitos |
| download trava | host oficial da Receita instável | o pipeline usa o espelho; rode de novo, tem retomada |
