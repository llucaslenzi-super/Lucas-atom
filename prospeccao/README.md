# Pipeline de Prospecção por CNPJ

Duas portas de entrada, uma espinha de enriquecimento, saída em CSV. **Sem IA no caminho do dado.**

```
PORTA A — filtro                     PORTA B — planilha
UF + CNAE + porte + situação         .xlsx/.csv com CNPJs
        │                                    │
        └─────────────┬──────────────────────┘
                      ▼
          lista de CNPJ (DV validado)
                      ▼
          [1] Receita local (DuckDB)      grátis · ilimitado · segundos
                      ▼
          [2] PORTÃO: contar → ranquear → cortar N
                      ▼
          [3] EmpresAqui API              1 req/s · cache · retomada
                      ▼
                  CSV final
```

## Por que duas fontes

A API do EmpresAqui **só consulta por CNPJ** — não tem filtro por UF, CNAE ou
porte. E mesmo que tivesse, 1 req/s não varre 73 milhões de estabelecimentos.

Então o filtro mora na base pública da Receita, no disco: grátis, sem limite,
devolve dezenas de milhares em segundos. A API entra depois, só nos escolhidos,
pra trazer o que a Receita não tem — WhatsApp, Instagram, LinkedIn, e-mail e
site validados.

| | Receita (disco) | EmpresAqui (API) |
|---|---|---|
| custo | zero | assinatura |
| limite | nenhum | 1 req/s |
| entrega | quem é, onde está, CNAE, porte, sócios | como falar com a empresa |

## Instalar

```bash
pip install duckdb
export EMPRESAQUI_TOKEN="seu_token"     # nunca commitar
```

## Preparar a base (uma vez)

```bash
python -m cnpj baixar       # ~5 GB em Parquet, base nacional
python -m cnpj carregar     # → DuckDB com índices
python -m cnpj conferir     # OBRIGATÓRIO: confere se os campos caíram no lugar
```

`conferir` não é opcional. Se a ordem das colunas estiver trocada, os dados
carregam **sem erro nenhum** e ficam silenciosamente errados.

## Usar

```bash
# achar o código CNAE
python -m cnpj cnaes --busca tecelagem

# PORTA A — contar antes de gastar
python -m cnpj buscar --uf SC,PR --cnae 13 --contar
python -m cnpj buscar --uf SC,PR,RS,MG --cnae 13,14 --porte medio \
                      --limite 300 --ordenar contato --out lista.csv

# PORTA B — planilha (detecta a coluna de CNPJ sozinho)
python -m cnpj planilha minha_lista.xlsx --out lista.csv

# enriquecer e exportar
python -m cnpj enriquecer lista.csv --out leads.csv
```

### O portão

O filtro é grátis e devolve dezenas de milhares. O enriquecimento é 1 req/s.
**Nunca mande o resultado bruto do filtro direto pro enriquecimento** — 10.000
CNPJs levariam 2h47. Use `--limite` com `--ordenar`:

- `--ordenar contato` — prioriza quem já tem telefone/e-mail no cadastro
- `--ordenar capital` — maiores primeiro
- `--com-contato` — descarta de saída quem não tem contato nenhum

Ranquear é de graça: os dados da Receita já estão no disco.

## Garantias

- **Nunca inventa contato.** Campo sem dado sai vazio.
- **Dígito verificador validado antes da requisição** — CNPJ torto não vira chamada.
- **Cache permanente.** Rodar de novo é instantâneo; matar no meio e religar não reprocessa.
- **Procedência por campo** (`fonte_telefone`, `fonte_email`, `fonte_whatsapp`) — auditoria e LGPD.
- 429 e 5xx com backoff exponencial; 401/403 aborta na hora.

## Formatos da API (confirmados contra a API real)

| | |
|---|---|
| CNPJ 14 dígitos | objeto único, 41 chaves na raiz |
| CNPJ 8 dígitos | `{cnpj_base, quantidade, resultados[]}` — matriz + filiais numa requisição |
| sócios | **chaves numéricas** (`"0"`, `"1"`) na raiz, não array |
| `enrichment` | 34 campos no plano Plus; `null` fora dele |
| `cnae_secundario` | CSV em string, não array |
| datas | `00000000` significa vazio |
| `site` | vem sem protocolo |

## Estrutura

```
cnpj/
  config.py       caminhos, token, decodificadores
  layout.py       schema dos arquivos da Receita  ← conferir contra o PDF oficial
  carregar.py     download + carga no DuckDB
  buscar.py       o filtro mestre
  empresaqui.py   cliente da API: rate limit, cache, achatamento
  exportar.py     leitura de planilha + escrita do CSV
  __main__.py     CLI
```

## Fontes

- Base: espelho [CNPJ Aberto](https://dados.cnpjaberto.com.br/) (Parquet, via Hugging Face) · oficial: [arquivos.receitafederal.gov.br](https://arquivos.receitafederal.gov.br/dados/cnpj/dados_abertos_cnpj/)
- API: [empresaqui.com.br/acesso/api](https://www.empresaqui.com.br/acesso/api)
