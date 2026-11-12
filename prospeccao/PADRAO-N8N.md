# n8n — o que o Agente de Prospecção tem na Atom

Instância **`atomtecnologia.app.n8n.cloud`**, projeto **Missner**
(`U7PD2iEcNVV1GxIs`), que é onde o agente de vendas Missner também mora.

**Nada na soultextil.** As ferramentas MCP do n8n desta sessão apontam para
lá; toda escrita é feita pela API REST com o JWT, nunca por MCP.

---

## Duas coisas aprendidas na prática, e que custam tempo se esquecidas

**1. Data Table é por projeto.** Workflow criado por API cai no projeto
pessoal, e aí o nó de Data Table falha com *"could not be found in this
project"*. A criação não aceita `projectId`: cria e depois
`PUT /workflows/{id}/transfer` com `{"destinationProjectId": "..."}`.

**2. `Content-Disposition` não vem de graça.** O `Respond to Webhook` em modo
binário manda o `Content-Type` certo mas não o `Content-Disposition`, e aí o
navegador decide sozinho o que fazer com o arquivo. Sem ele, não é download:
é sorte.

---

## Data Tables

| nome | id | para quê |
|---|---|---|
| `prospeccao_pedidos` | `7xKe4gdNqDX4SKEC` | fila de entrada: filtro ou planilha, status, motivo |
| `prospeccao_listas` | `pvMmLx229Y5TAsEP` | lista pronta em base64, esperando download |

Prefixo **`prospeccao_`** de propósito. O agente de vendas usa `missner_` em
treze tabelas; `misner_` com um esse ao lado de `missner_` com dois é acidente
esperando acontecer.

### Colunas

```
prospeccao_pedidos   status · filtro · total · formatos
                     planilha_nome · planilha_b64
                     pedido_id · motivo · criado_em

prospeccao_listas    chave · pedido_id · fatia · formato
                     filename · ct · b64 · empresas
                     criado_em · baixado_em
```

`chave` é `pedido-fatia-formato`, e é o que torna a entrega **idempotente**:
reenviar a mesma fatia sobrescreve em vez de duplicar, então a ponte pode
morrer no meio sem estragar nada.

---

## Workflows

| nome | id | disparo | caminho |
|---|---|---|---|
| `Prospecção · Guardar` | `Ph67Xx9EWhZjAhCD` | webhook POST | `/webhook/prospeccao-guardar` |
| `Prospecção · Baixar` | `Xqd8A28VhasiNUBZ` | webhook GET | `/webhook/prospeccao-baixar?c=<chave>` |
| `Prospecção · Limpar` | `pdkZrtUSu9emN6vm` | diário, 4h10 | — |

Os três **ativos**.

- **Guardar** — a ponte manda a lista em base64. Confere o segredo, monta a
  chave e faz `upsert`. Recusa com 401 sem o segredo.
- **Baixar** — Data Table → nó Code monta o binário → `Respond` com
  `respondWith: binary` e `Content-Disposition: attachment`. É a cópia do
  `Missner · Serve Material`, que já estava na instância. Chave inexistente ou
  lista expirada devolve 404 com motivo, não um arquivo de zero byte.
- **Limpar** — apaga linha já baixada e linha com mais de 7 dias. É o que
  mantém a cota de 50 MB sob controle.

### O segredo da ponte

Uma constante dentro do nó `Valida` do Guardar, e a mesma string na metadata
da VM como `PONTE_TOKEN`. Para rodar, troca nos dois lugares. Não está no
repositório, que é público.

---

## Medido, não estimado

```
cota de Data Table da instância       50 MB  (teto do n8n Cloud; a variável
                                       que o levanta só existe em auto-hospedado)
já ocupado pelos outros workflows    4,5 MB
livre                               45,5 MB  = 98 listas de 100 empresas

lista de 100 empresas, 78 colunas:
  XLSX   156 KB → 208 KB em base64
  CSV    199 KB → 265 KB
  PDF    237 KB → 316 KB
```

## Testado ponta a ponta

Planilha real de 100 empresas gerada pelo exportador do projeto, enviada ao
Guardar e baixada pelo Baixar:

```
original  79.953 bytes
baixado   79.953 bytes      sha256 idêntico
Content-Disposition: attachment; filename="prospeccao-...-001.xlsx"
abre no Excel · 100 linhas · cabeçalho CNPJ · Razão Social · Nome Fantasia ·
Contatos · E-mail · Instagram
```

Linhas de teste apagadas depois; a instância voltou a 4,51 MB.

---

## O que ainda não existe

- `Prospecção · Pedir` — a entrada do cliente
- `servico/ponte.py` na VM — quem lê a fila e manda a lista
- a interface
