# Cobrança WhatsApp Soul Têxtil — Documentação Técnica Completa

> Sistema automatizado de cobrança via WhatsApp para Soul Têxtil. 3 filiais × 2 fluxos = 6 agentes ativos.
> Arquitetura: **NEKT (SQL) → Google Sheets → n8n → Z-API**.

---

## Sumário

1. [Visão geral e arquitetura](#1-visão-geral-e-arquitetura)
2. [Régua de cobrança](#2-régua-de-cobrança)
3. [Credenciais Z-API (3 instâncias)](#3-credenciais-z-api-3-instâncias)
4. [Tabelas-fonte no Nekt](#4-tabelas-fonte-no-nekt)
5. [Planilhas Google Sheets (IDs)](#5-planilhas-google-sheets-ids)
6. [Operação diária](#6-operação-diária)
7. [Bugs documentados e fixes](#7-bugs-documentados-e-fixes)
8. [Volumetria validada (24/jun/2026)](#8-volumetria-validada-24jun2026)
9. **[Anexo — SQL completo dos 6 agentes](#anexo-a--sql-completo-dos-6-agentes)**
10. **[Anexo — JSON dos 6 workflows n8n](#anexo-b--json-dos-6-workflows-n8n)**

---

## 1. Visão geral e arquitetura

```
ERP SQL Server (3 databases: dbGaspar, dbSoul_LojaSp, dbSoulMatriz)
    ↓ extração contínua via Nekt (raw layer mssql_*)
Nekt — 6 transformations SQL (Athena/Trino) → tabelas trusted
    ↓ Destination Google Sheets (clear A2:K ou A2:M, trigger manual)
Google Sheets — 6 planilhas (aba `dados`) — preview/auditoria
    ↓ Rubens revisa; marca N em ENVIO pra pular
n8n — 6 workflows (Manual Trigger)
    ↓ HTTP POST Z-API send-text + Wait 4s + Mark Enviado=OK
WhatsApp do cliente
```

### Princípios

- **Gatilhos manuais** em todas as etapas. Rubens decide a hora.
- **Anti-duplo**: coluna `enviado` na planilha. n8n marca `OK` após disparo. Filter pula linhas com `enviado=OK`.
- **Override humano**: coluna `ENVIO`. Se Rubens digitar `N`/`n`, pula a linha.
- **Filtro de qualidade**: só dispara quem tem `status_contato = OK ✅`.
- **Rate limit**: Wait 4s entre disparos (Z-API barra acima de 1 msg/s sustentado).

---

## 2. Régua de cobrança

### Filtros comuns aos 2 fluxos
- `saldodocumento > 0`
- `tipodocumento IN (10, 80, 70, 3, 7, 68)` — Boleto, PIX, Cartão Parcelado, Cheque Terceiros, Crediário, Cheques Repassados
- Limpeza de telefone: `regexp_replace(telefone, '[^0-9]', '')`
- Limpeza de nome: `regexp_replace(nome, '[\r\n\t]', ' ')`

### Status do contato
```
vazio                                     → SEM CONTATO
< 10 dígitos                              → CONTATO INVALIDO
10-11 dígitos                             → OK ✅
12-13 dígitos com prefixo 55              → OK ✅
demais                                    → CONTATO INVALIDO
```

### Fluxo 1 — Lembrete Semanal (a vencer)
Roda em **seg / qua / sex**. Janela varia por dia:

| Dia (`date_format %a`) | Janela de vencimento |
| --- | --- |
| Mon | hoje → hoje+2 (até quarta) |
| Wed | hoje → hoje+2 (até sexta) |
| Fri | hoje → hoje+3 (até segunda) |
| Outros | hoje → hoje+2 (degrada graciosamente) |

Cabeçalho da mensagem:
```
Olá, tudo bem?

Cliente: {nome}

Lembrete, nesta semana você tem vencimento(s) para:

{linhas}
```

### Fluxo 2 — Acompanhamento de Vencidos
Roda **todo dia útil**. Janela fixa: `datavencimento BETWEEN hoje-180 AND hoje-2`.

| Ciclo | dias_vencido | Disparo |
| --- | --- | --- |
| 1 | exatamente 2 dias | primeira cobrança |
| 2 | 3 a 10 dias | cobrança diária |
| 3 | 11 a 180 dias | cobrança contínua (todo dia útil) |

Cabeçalho:
```
Olá, tudo bem?

Cliente: {nome}

Verificamos que ficou pendente:

{linhas}
```

### Formato das linhas (idêntico nos 2 fluxos)
- **Cheques** (tipos 3, 68): `Cheque {doc} / venc. {dd/mm/yyyy} / Valor: R$ {valor}`
- **Demais com pedido**: `venc. {dd/mm/yyyy} / Valor: R$ {valor} / Doc.{N} / Ped.{pedidos}`
- **Demais sem pedido**: `venc. {dd/mm/yyyy} / Valor: R$ {valor} / Doc.{N}`

### Diferenças de extração de pedido por filial

| Filial | Caminho | Função SQL |
| --- | --- | --- |
| Gaspar (SC) | `documentoorigem LIKE 'RNF%'` → `NF.referencia` → `FaturaItens.nrpedido` | `array_agg(DISTINCT fi.nrpedido)` |
| Loja SP | `CR.documento = NF.documentoorigem` + `origemnota='Fatura'` + `Pedido(s):` em `observacoes` | `regexp_extract(nf.observacoes, 'Pedido\(s\):\s*([0-9,]+)', 1)` |
| Matriz PE | idêntico ao SP | `regexp_extract(...)` |

> PE: ~97% das NFs Fatura têm `codigodestinatario = 999999` (Consumidor Final), o que reduz cobertura de Ped.{N} na mensagem (≈19.5%).

---

## 3. Credenciais Z-API (3 instâncias)

| Filial | Instance ID | Token | Client-Token |
| --- | --- | --- | --- |
| SC (Gaspar) | `3F4CA04EC2A9F2C35C05CE717FF40C71` | `DA5E5295DD430239591BB4B4` | `Fc7c6d29c0a2b420c9fccde34c997c5c9S` |
| SP (Loja SP) | `3F5095DD7D7FF21EFBAF0E47AC50613B` | `94F9624905675A9AE02241B1` | `F46e884cedc2249428dec027269797b7fS` |
| PE (Matriz) | `3F50950C8D302225807376D0BCEB03A2` | `65FF9A941F2B71EB3B6262BF` | `F46e884cedc2249428dec027269797b7fS` |

Endpoint padrão:
```
POST https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}/send-text
Header: Client-Token: {CLIENT_TOKEN}
Body  : { "phone": "55XXYYYYYYYYY", "message": "..." }
```

---

## 4. Tabelas-fonte no Nekt

### Gaspar (SC)
- `nekt_raw.mssql_gaspar_dbo_cr_documentos`
- `nekt_raw.mssql_gaspar_dbo_clientes`
- `nekt_raw.mssql_gaspar_dbo_nota_fiscal_capa`
- `nekt_raw.mssql_gaspar_dbo_fatura_itens`

### Loja SP
- `nekt_raw.mssql_loja_sp_dbo_cr_documentos`
- `nekt_raw.mssql_loja_sp_dbo_clientes`
- `nekt_raw.mssql_loja_sp_dbo_nota_fiscal_capa`

### Matriz PE
- `nekt_raw.mssql_matriz_dbo_cr_documentos`
- `nekt_raw.mssql_matriz_dbo_clientes`
- `nekt_raw.mssql_matriz_dbo_nota_fiscal_capa`

---

## 5. Planilhas Google Sheets (IDs)

Drive folder: `SOUL - RUBENS / AGENTE DE COBRANÇA WHATSAPP` (id `1g00PjGA72gYve0dm3s8iGw9axvz4Ett5`).

| Planilha | Spreadsheet ID | Colunas | Clear range |
| --- | --- | --- | --- |
| Cobrança SC — Lembrete Semanal | `1HDZx62IhpsbioCethOd0n-PBCQLd9Tdfku1rpXQdlys` | A:K | A2:K |
| Cobrança SC — Acompanhamento Vencidos | `1RQdWwEpyH6lSsAy56mS8WaF-_kYIBiw8OOZRHC4PROg` | A:M | A2:M |
| Cobrança SP — Lembrete Semanal | `1ezrtPXOAUkpDt8WWpuYSmhQCrvZfqavRtgbOZRTovNg` | A:K | A2:K |
| Cobrança SP — Acompanhamento Vencidos | `1qed4eWDTS3nQJShO13Jcg0C7a2ANF0dYqIR3N8l5dCg` | A:M | A2:M |
| Cobrança PE — Lembrete Semanal | `1BSsLJoUF8zoXZ-0bg-ciOvyxOf8A3cWIZXn3pAgbtAE` | A:K | A2:K |
| Cobrança PE — Acompanhamento Vencidos | `1BfHsVRx6dnrbNhaMTPayz8Lfp4q06AJPu5HoRnGNed4` | A:M | A2:M |

Em todas: aba `dados`, cabeçalho na linha 1, dados a partir da linha 2.

**Cabeçalho Lembrete (A:K — 11 colunas):**
`Filial | CodCliente | Cliente | Telefone | Telefone_Digitos | Status_Contato | Qtd_Titulos | Valor_Total | Mensagem | ENVIO | enviado`

**Cabeçalho Vencidos (A:M — 13 colunas):**
`Filial | CodCliente | Cliente | Telefone | Telefone_Digitos | Status_Contato | Qtd_Titulos | Valor_Total | Ciclo_Predominante | Dias_Vencido_Max | Mensagem | ENVIO | enviado`

---

## 6. Operação diária

### Lembrete (seg/qua/sex de manhã)
1. Nekt → Queries → seleciona a query da filial → **Run now** (5-6 min)
2. (trigger automático) Destination escreve na planilha
3. Abre planilha → revisa → marca `N` na coluna `ENVIO` em quem quer pular
4. n8n → Workflow da filial → **Execute Workflow**
5. Mensagens disparam a ~4s de intervalo. Coluna `enviado` vai virando `OK` linha por linha.

### Vencidos (todo dia útil de manhã)
Mesmo fluxo, com 2 colunas extras: `Ciclo_Predominante` (1/2/3) e `Dias_Vencido_Max`. Ordenado por dias_vencido_max desc (mais antigos em cima).

### Formatação condicional sugerida (Sheets)
Na coluna `enviado` (K nas de Lembrete, M nas de Vencidos):
- **Formatar → Formatação condicional**
- Regra: "O texto contém exatamente" `OK` → fundo verde, texto branco bold

---

## 7. Bugs documentados e fixes

### Bug 1 — `day_of_week` no engine de execução do Nekt
- **Sintoma**: Query Lembrete produziu janela 17-20 em vez de 17-19.
- **Causa**: A `CASE day_of_week(...) WHEN 5 THEN +3 ELSE +2` rodava com semântica diferente entre Trino (1=Mon) e Spark/BigQuery (1=Sun). Engine de execução do pipeline difere do Explorer.
- **Fix**: Trocar `day_of_week(...) = 5` por `date_format(..., '%a') = 'Fri'` — funções de nome de dia são determinísticas. **Aplicado em SP e PE Lembrete**. Gaspar Lembrete ainda usa `day_of_week` (criado antes do fix, mas funciona porque a query foi materializada antes da diferença aparecer).

### Bug 2 — Planilha "Forbidden" no n8n
- **Sintoma**: `Forbidden - perhaps check your credentials?` no nó Read Sheets.
- **Causa**: Conta OAuth do n8n sem acesso à planilha.
- **Fix**: Compartilhar cada planilha nova com o e-mail da credencial Google Sheets do n8n (Editor).

### Bug 3 — Caminho de pedido errado em SP/PE
- **Sintoma**: Cliente sem `Ped.{N}` na mensagem.
- **Causa**: SP e PE não usam `RNF→FaturaItens` como Gaspar — pedido vem da string `Pedido(s):` em `NF.observacoes`.
- **Fix**: Path específico via `regexp_extract` documentado acima.

### Bug 4 — Tabela materializada não atualizou
- **Sintoma**: Edita query no Nekt, salva, Run now no Destination, mas tabela continua com dados antigos.
- **Causa**: Run now no Destination não re-executa a query — só re-escreve a partir da tabela materializada.
- **Fix**: Rodar Run now na **Query** primeiro, depois no Destination. Ou configurar trigger por evento (Destination roda após Query terminar).

---

## 8. Volumetria validada (24/jun/2026)

| Fluxo | Clientes | Títulos | Valor total |
| --- | --- | --- | --- |
| SC Lembrete (janela 24-26) | 31 | 40 | R$ 248k |
| SC Vencidos | 11 | 23 | R$ 68k |
| SP Lembrete | 48 | 62 | R$ 285k |
| SP Vencidos | 55 | 159 | **R$ 1.725k** |
| PE Lembrete | 61 | 119 | R$ 564k |
| PE Vencidos | 70 | 223 | **R$ 1.042k** |
| **Total** | ~270 | ~626 | **~R$ 3.9M** |

---

# ANEXO A — SQL completo dos 6 agentes

## A.1 Gaspar/SC — Lembrete Semanal
**Arquivo**: `gaspar_agente_cobranca_lembrete_semanal.sql`
**Output table**: `nekt_trusted.gaspar_agente_cobranca_lembrete_semanal`

```sql
WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
janela AS (
  SELECT data_execucao,
    data_execucao AS data_inicio,
    CASE day_of_week(data_execucao)
      WHEN 5 THEN date_add('day', 3, data_execucao)
      ELSE date_add('day', 2, data_execucao)
    END AS data_fim
  FROM params
),
titulos AS (
  SELECT
    cr.codcliente, cr.tipodocumento, cr.documento, cr.parcela,
    CAST(cr.datavencimento AS DATE) AS datavencimento,
    cr.saldodocumento, cr.documentoorigem,
    CASE WHEN cr.documentoorigem LIKE 'RNF%'
         THEN TRY(CAST(SUBSTR(cr.documentoorigem, 4) AS BIGINT))
         ELSE NULL END AS rnf_extraido
  FROM nekt_raw.mssql_gaspar_dbo_cr_documentos cr
  CROSS JOIN janela j
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 70, 3, 7, 68)
    AND CAST(cr.datavencimento AS DATE) BETWEEN j.data_inicio AND j.data_fim
),
nf_link AS (
  SELECT t.codcliente, t.tipodocumento, t.documento, t.parcela,
    TRY(CAST(nf.documentoorigem AS BIGINT)) AS nrfatura
  FROM titulos t
  LEFT JOIN nekt_raw.mssql_gaspar_dbo_nota_fiscal_capa nf
    ON nf.referencia = t.rnf_extraido AND nf.origemnota = 'Fatura'
),
pedidos_por_titulo AS (
  SELECT nl.codcliente, nl.tipodocumento, nl.documento, nl.parcela,
    array_join(array_agg(DISTINCT CAST(fi.nrpedido AS VARCHAR)), ',') AS pedidos_str
  FROM nf_link nl
  JOIN nekt_raw.mssql_gaspar_dbo_fatura_itens fi ON fi.nrfatura = nl.nrfatura
  WHERE fi.nrpedido IS NOT NULL
  GROUP BY nl.codcliente, nl.tipodocumento, nl.documento, nl.parcela
),
linhas AS (
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento,
    CASE
      WHEN t.tipodocumento IN (3, 68) THEN
        'Cheque ' || t.documento || ' / venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
      WHEN ppt.pedidos_str IS NOT NULL THEN
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento || ' / Ped.' || ppt.pedidos_str
      ELSE
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento
    END AS linha_mensagem
  FROM titulos t
  LEFT JOIN pedidos_por_titulo ppt
    ON ppt.codcliente = t.codcliente AND ppt.tipodocumento = t.tipodocumento
   AND ppt.documento = t.documento AND ppt.parcela = t.parcela
),
clientes_clean AS (
  SELECT c.codcliente,
    regexp_replace(c.nome, '[\r\n\t]', ' ') AS nome,
    c.telefone AS telefone_raw,
    regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '') AS telefone_digitos
  FROM nekt_raw.mssql_gaspar_dbo_clientes c
),
agg AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total,
    array_join(array_agg(l.linha_mensagem), chr(10)) AS linhas_msg
  FROM linhas l GROUP BY l.codcliente
)
SELECT
  'SC' AS filial,
  cc.codcliente, cc.nome,
  cc.telefone_raw AS telefone,
  cc.telefone_digitos,
  CASE
    WHEN cc.telefone_digitos = '' THEN 'SEM CONTATO'
    WHEN LENGTH(cc.telefone_digitos) < 10 THEN 'CONTATO INVALIDO'
    WHEN LENGTH(cc.telefone_digitos) IN (10, 11) THEN 'OK'
    WHEN LENGTH(cc.telefone_digitos) IN (12, 13) AND SUBSTR(cc.telefone_digitos, 1, 2) = '55' THEN 'OK'
    ELSE 'CONTATO INVALIDO'
  END AS status_contato,
  a.qtd_titulos, a.valor_total,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Lembrete, nesta semana você tem vencimento(s) para:' || chr(10) || chr(10)
   || a.linhas_msg AS mensagem
FROM agg a
JOIN clientes_clean cc ON cc.codcliente = a.codcliente
ORDER BY a.valor_total DESC
```

---

## A.2 Gaspar/SC — Acompanhamento Vencidos
**Arquivo**: `gaspar_agente_cobranca_acompanhamento_vencidos.sql`
**Output table**: `nekt_trusted.gaspar_agente_cobranca_acompanhamento_vencidos`

```sql
WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
titulos AS (
  SELECT
    cr.codcliente, cr.tipodocumento, cr.documento, cr.parcela,
    CAST(cr.datavencimento AS DATE) AS datavencimento,
    cr.saldodocumento, cr.documentoorigem,
    date_diff('day', CAST(cr.datavencimento AS DATE), p.data_execucao) AS dias_vencido,
    CASE WHEN cr.documentoorigem LIKE 'RNF%'
         THEN TRY(CAST(SUBSTR(cr.documentoorigem, 4) AS BIGINT))
         ELSE NULL END AS rnf_extraido
  FROM nekt_raw.mssql_gaspar_dbo_cr_documentos cr
  CROSS JOIN params p
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 70, 3, 7, 68)
    AND CAST(cr.datavencimento AS DATE) BETWEEN date_add('day', -180, p.data_execucao) AND date_add('day', -2, p.data_execucao)
),
nf_link AS (
  SELECT t.codcliente, t.tipodocumento, t.documento, t.parcela,
    TRY(CAST(nf.documentoorigem AS BIGINT)) AS nrfatura
  FROM titulos t
  LEFT JOIN nekt_raw.mssql_gaspar_dbo_nota_fiscal_capa nf
    ON nf.referencia = t.rnf_extraido AND nf.origemnota = 'Fatura'
),
pedidos_por_titulo AS (
  SELECT nl.codcliente, nl.tipodocumento, nl.documento, nl.parcela,
    array_join(array_agg(DISTINCT CAST(fi.nrpedido AS VARCHAR)), ',') AS pedidos_str
  FROM nf_link nl
  JOIN nekt_raw.mssql_gaspar_dbo_fatura_itens fi ON fi.nrfatura = nl.nrfatura
  WHERE fi.nrpedido IS NOT NULL
  GROUP BY nl.codcliente, nl.tipodocumento, nl.documento, nl.parcela
),
linhas AS (
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento, t.dias_vencido,
    CASE WHEN t.dias_vencido = 2 THEN 1
         WHEN t.dias_vencido BETWEEN 3 AND 10 THEN 2
         ELSE 3 END AS ciclo,
    CASE
      WHEN t.tipodocumento IN (3, 68) THEN
        'Cheque ' || t.documento || ' / venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
      WHEN ppt.pedidos_str IS NOT NULL THEN
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento || ' / Ped.' || ppt.pedidos_str
      ELSE
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento
    END AS linha_mensagem
  FROM titulos t
  LEFT JOIN pedidos_por_titulo ppt
    ON ppt.codcliente = t.codcliente AND ppt.tipodocumento = t.tipodocumento
   AND ppt.documento = t.documento AND ppt.parcela = t.parcela
),
clientes_clean AS (
  SELECT c.codcliente,
    regexp_replace(c.nome, '[\r\n\t]', ' ') AS nome,
    c.telefone AS telefone_raw,
    regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '') AS telefone_digitos
  FROM nekt_raw.mssql_gaspar_dbo_clientes c
),
ciclos_por_cliente AS (
  SELECT codcliente, ciclo, COUNT(*) AS qtd
  FROM linhas GROUP BY codcliente, ciclo
),
ciclo_predominante AS (
  SELECT codcliente, ciclo,
    ROW_NUMBER() OVER (PARTITION BY codcliente ORDER BY qtd DESC, ciclo DESC) AS rn
  FROM ciclos_por_cliente
),
agg AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total,
    MAX(l.dias_vencido) AS dias_vencido_max,
    array_join(array_agg(l.linha_mensagem), chr(10)) AS linhas_msg
  FROM linhas l GROUP BY l.codcliente
)
SELECT
  'SC' AS filial,
  cc.codcliente, cc.nome,
  cc.telefone_raw AS telefone,
  cc.telefone_digitos,
  CASE
    WHEN cc.telefone_digitos = '' THEN 'SEM CONTATO'
    WHEN LENGTH(cc.telefone_digitos) < 10 THEN 'CONTATO INVALIDO'
    WHEN LENGTH(cc.telefone_digitos) IN (10, 11) THEN 'OK'
    WHEN LENGTH(cc.telefone_digitos) IN (12, 13) AND SUBSTR(cc.telefone_digitos, 1, 2) = '55' THEN 'OK'
    ELSE 'CONTATO INVALIDO'
  END AS status_contato,
  a.qtd_titulos, a.valor_total,
  'Ciclo ' || CAST(cp.ciclo AS VARCHAR) AS ciclo_predominante,
  a.dias_vencido_max,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Verificamos que ficou pendente:' || chr(10) || chr(10)
   || a.linhas_msg AS mensagem,
  CAST(NULL AS VARCHAR) AS envio,
  CAST(NULL AS VARCHAR) AS enviado
FROM agg a
JOIN clientes_clean cc ON cc.codcliente = a.codcliente
JOIN ciclo_predominante cp ON cp.codcliente = a.codcliente AND cp.rn = 1
ORDER BY a.dias_vencido_max DESC, a.valor_total DESC
```

---

## A.3 Loja SP — Lembrete Semanal
**Arquivo**: `loja_sp_agente_cobranca_lembrete_semanal.sql`
**Output table**: `nekt_trusted.loja_sp_agente_cobranca_lembrete_semanal`

```sql
WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
janela AS (
  SELECT data_execucao,
    data_execucao AS data_inicio,
    CASE date_format(data_execucao, '%a')
      WHEN 'Fri' THEN date_add('day', 3, data_execucao)
      ELSE date_add('day', 2, data_execucao)
    END AS data_fim
  FROM params
),
titulos AS (
  SELECT
    cr.codcliente, cr.tipodocumento, cr.documento, cr.parcela,
    CAST(cr.datavencimento AS DATE) AS datavencimento,
    cr.saldodocumento,
    TRY_CAST(cr.documento AS BIGINT) AS doc_int
  FROM nekt_raw.mssql_loja_sp_dbo_cr_documentos cr
  CROSS JOIN janela j
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 70, 3, 7, 68)
    AND CAST(cr.datavencimento AS DATE) BETWEEN j.data_inicio AND j.data_fim
),
pedidos_por_titulo AS (
  SELECT t.codcliente, t.tipodocumento, t.documento, t.parcela,
    MAX(regexp_extract(nf.observacoes, 'Pedido\(s\):\s*([0-9,]+)', 1)) AS pedidos_str
  FROM titulos t
  JOIN nekt_raw.mssql_loja_sp_dbo_nota_fiscal_capa nf
    ON TRY_CAST(nf.documentoorigem AS BIGINT) = t.doc_int
   AND nf.origemnota = 'Fatura'
  WHERE regexp_like(nf.observacoes, 'Pedido\(s\):')
  GROUP BY t.codcliente, t.tipodocumento, t.documento, t.parcela
),
linhas AS (
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento,
    CASE
      WHEN t.tipodocumento IN (3, 68) THEN
        'Cheque ' || t.documento || ' / venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
      WHEN ppt.pedidos_str IS NOT NULL AND ppt.pedidos_str <> '' THEN
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento || ' / Ped.' || ppt.pedidos_str
      ELSE
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento
    END AS linha_mensagem
  FROM titulos t
  LEFT JOIN pedidos_por_titulo ppt
    ON ppt.codcliente = t.codcliente AND ppt.tipodocumento = t.tipodocumento
   AND ppt.documento = t.documento AND ppt.parcela = t.parcela
),
clientes_clean AS (
  SELECT c.codcliente,
    regexp_replace(c.nome, '[\r\n\t]', ' ') AS nome,
    c.telefone AS telefone_raw,
    regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '') AS telefone_digitos
  FROM nekt_raw.mssql_loja_sp_dbo_clientes c
),
agg AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total,
    array_join(array_agg(l.linha_mensagem), chr(10)) AS linhas_msg
  FROM linhas l GROUP BY l.codcliente
)
SELECT
  'SP' AS filial,
  cc.codcliente, cc.nome,
  cc.telefone_raw AS telefone,
  cc.telefone_digitos,
  CASE
    WHEN cc.telefone_digitos = '' THEN 'SEM CONTATO'
    WHEN LENGTH(cc.telefone_digitos) < 10 THEN 'CONTATO INVALIDO'
    WHEN LENGTH(cc.telefone_digitos) IN (10, 11) THEN 'OK'
    WHEN LENGTH(cc.telefone_digitos) IN (12, 13) AND SUBSTR(cc.telefone_digitos, 1, 2) = '55' THEN 'OK'
    ELSE 'CONTATO INVALIDO'
  END AS status_contato,
  a.qtd_titulos, a.valor_total,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Lembrete, nesta semana você tem vencimento(s) para:' || chr(10) || chr(10)
   || a.linhas_msg AS mensagem,
  CAST(NULL AS VARCHAR) AS envio,
  CAST(NULL AS VARCHAR) AS enviado
FROM agg a
JOIN clientes_clean cc ON cc.codcliente = a.codcliente
ORDER BY a.valor_total DESC
```

---

## A.4 Loja SP — Acompanhamento Vencidos
**Arquivo**: `loja_sp_agente_cobranca_acompanhamento_vencidos.sql`
**Output table**: `nekt_trusted.loja_sp_agente_cobranca_acompanhamento_vencidos`

```sql
WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
titulos AS (
  SELECT
    cr.codcliente, cr.tipodocumento, cr.documento, cr.parcela,
    CAST(cr.datavencimento AS DATE) AS datavencimento,
    cr.saldodocumento,
    date_diff('day', CAST(cr.datavencimento AS DATE), p.data_execucao) AS dias_vencido,
    TRY_CAST(cr.documento AS BIGINT) AS doc_int
  FROM nekt_raw.mssql_loja_sp_dbo_cr_documentos cr
  CROSS JOIN params p
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 70, 3, 7, 68)
    AND CAST(cr.datavencimento AS DATE) BETWEEN date_add('day', -180, p.data_execucao) AND date_add('day', -2, p.data_execucao)
),
pedidos_por_titulo AS (
  SELECT t.codcliente, t.tipodocumento, t.documento, t.parcela,
    MAX(regexp_extract(nf.observacoes, 'Pedido\(s\):\s*([0-9,]+)', 1)) AS pedidos_str
  FROM titulos t
  JOIN nekt_raw.mssql_loja_sp_dbo_nota_fiscal_capa nf
    ON TRY_CAST(nf.documentoorigem AS BIGINT) = t.doc_int
   AND nf.origemnota = 'Fatura'
  WHERE regexp_like(nf.observacoes, 'Pedido\(s\):')
  GROUP BY t.codcliente, t.tipodocumento, t.documento, t.parcela
),
linhas AS (
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento, t.dias_vencido,
    CASE WHEN t.dias_vencido = 2 THEN 1
         WHEN t.dias_vencido BETWEEN 3 AND 10 THEN 2
         ELSE 3 END AS ciclo,
    CASE
      WHEN t.tipodocumento IN (3, 68) THEN
        'Cheque ' || t.documento || ' / venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
      WHEN ppt.pedidos_str IS NOT NULL AND ppt.pedidos_str <> '' THEN
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento || ' / Ped.' || ppt.pedidos_str
      ELSE
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento
    END AS linha_mensagem
  FROM titulos t
  LEFT JOIN pedidos_por_titulo ppt
    ON ppt.codcliente = t.codcliente AND ppt.tipodocumento = t.tipodocumento
   AND ppt.documento = t.documento AND ppt.parcela = t.parcela
),
clientes_clean AS (
  SELECT c.codcliente,
    regexp_replace(c.nome, '[\r\n\t]', ' ') AS nome,
    c.telefone AS telefone_raw,
    regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '') AS telefone_digitos
  FROM nekt_raw.mssql_loja_sp_dbo_clientes c
),
ciclos_por_cliente AS (
  SELECT codcliente, ciclo, COUNT(*) AS qtd
  FROM linhas GROUP BY codcliente, ciclo
),
ciclo_predominante AS (
  SELECT codcliente, ciclo,
    ROW_NUMBER() OVER (PARTITION BY codcliente ORDER BY qtd DESC, ciclo DESC) AS rn
  FROM ciclos_por_cliente
),
agg AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total,
    MAX(l.dias_vencido) AS dias_vencido_max,
    array_join(array_agg(l.linha_mensagem), chr(10)) AS linhas_msg
  FROM linhas l GROUP BY l.codcliente
)
SELECT
  'SP' AS filial,
  cc.codcliente, cc.nome,
  cc.telefone_raw AS telefone,
  cc.telefone_digitos,
  CASE
    WHEN cc.telefone_digitos = '' THEN 'SEM CONTATO'
    WHEN LENGTH(cc.telefone_digitos) < 10 THEN 'CONTATO INVALIDO'
    WHEN LENGTH(cc.telefone_digitos) IN (10, 11) THEN 'OK'
    WHEN LENGTH(cc.telefone_digitos) IN (12, 13) AND SUBSTR(cc.telefone_digitos, 1, 2) = '55' THEN 'OK'
    ELSE 'CONTATO INVALIDO'
  END AS status_contato,
  a.qtd_titulos, a.valor_total,
  'Ciclo ' || CAST(cp.ciclo AS VARCHAR) AS ciclo_predominante,
  a.dias_vencido_max,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Verificamos que ficou pendente:' || chr(10) || chr(10)
   || a.linhas_msg AS mensagem,
  CAST(NULL AS VARCHAR) AS envio,
  CAST(NULL AS VARCHAR) AS enviado
FROM agg a
JOIN clientes_clean cc ON cc.codcliente = a.codcliente
JOIN ciclo_predominante cp ON cp.codcliente = a.codcliente AND cp.rn = 1
ORDER BY a.dias_vencido_max DESC, a.valor_total DESC
```

---

## A.5 Matriz PE — Lembrete Semanal
**Arquivo**: `matriz_agente_cobranca_lembrete_semanal.sql`
**Output table**: `nekt_trusted.matriz_agente_cobranca_lembrete_semanal`

```sql
WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
janela AS (
  SELECT data_execucao,
    data_execucao AS data_inicio,
    CASE date_format(data_execucao, '%a')
      WHEN 'Fri' THEN date_add('day', 3, data_execucao)
      ELSE date_add('day', 2, data_execucao)
    END AS data_fim
  FROM params
),
titulos AS (
  SELECT
    cr.codcliente, cr.tipodocumento, cr.documento, cr.parcela,
    CAST(cr.datavencimento AS DATE) AS datavencimento,
    cr.saldodocumento,
    TRY_CAST(cr.documento AS BIGINT) AS doc_int
  FROM nekt_raw.mssql_matriz_dbo_cr_documentos cr
  CROSS JOIN janela j
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 70, 3, 7, 68)
    AND CAST(cr.datavencimento AS DATE) BETWEEN j.data_inicio AND j.data_fim
),
pedidos_por_titulo AS (
  SELECT t.codcliente, t.tipodocumento, t.documento, t.parcela,
    MAX(regexp_extract(nf.observacoes, 'Pedido\(s\):\s*([0-9,]+)', 1)) AS pedidos_str
  FROM titulos t
  JOIN nekt_raw.mssql_matriz_dbo_nota_fiscal_capa nf
    ON TRY_CAST(nf.documentoorigem AS BIGINT) = t.doc_int
   AND nf.origemnota = 'Fatura'
  WHERE regexp_like(nf.observacoes, 'Pedido\(s\):')
  GROUP BY t.codcliente, t.tipodocumento, t.documento, t.parcela
),
linhas AS (
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento,
    CASE
      WHEN t.tipodocumento IN (3, 68) THEN
        'Cheque ' || t.documento || ' / venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
      WHEN ppt.pedidos_str IS NOT NULL AND ppt.pedidos_str <> '' THEN
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento || ' / Ped.' || ppt.pedidos_str
      ELSE
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento
    END AS linha_mensagem
  FROM titulos t
  LEFT JOIN pedidos_por_titulo ppt
    ON ppt.codcliente = t.codcliente AND ppt.tipodocumento = t.tipodocumento
   AND ppt.documento = t.documento AND ppt.parcela = t.parcela
),
clientes_clean AS (
  SELECT c.codcliente,
    regexp_replace(c.nome, '[\r\n\t]', ' ') AS nome,
    c.telefone AS telefone_raw,
    regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '') AS telefone_digitos
  FROM nekt_raw.mssql_matriz_dbo_clientes c
),
agg AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total,
    array_join(array_agg(l.linha_mensagem), chr(10)) AS linhas_msg
  FROM linhas l GROUP BY l.codcliente
)
SELECT
  'PE' AS filial,
  cc.codcliente, cc.nome,
  cc.telefone_raw AS telefone,
  cc.telefone_digitos,
  CASE
    WHEN cc.telefone_digitos = '' THEN 'SEM CONTATO'
    WHEN LENGTH(cc.telefone_digitos) < 10 THEN 'CONTATO INVALIDO'
    WHEN LENGTH(cc.telefone_digitos) IN (10, 11) THEN 'OK'
    WHEN LENGTH(cc.telefone_digitos) IN (12, 13) AND SUBSTR(cc.telefone_digitos, 1, 2) = '55' THEN 'OK'
    ELSE 'CONTATO INVALIDO'
  END AS status_contato,
  a.qtd_titulos, a.valor_total,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Lembrete, nesta semana você tem vencimento(s) para:' || chr(10) || chr(10)
   || a.linhas_msg AS mensagem,
  CAST(NULL AS VARCHAR) AS envio,
  CAST(NULL AS VARCHAR) AS enviado
FROM agg a
JOIN clientes_clean cc ON cc.codcliente = a.codcliente
ORDER BY a.valor_total DESC
```

---

## A.6 Matriz PE — Acompanhamento Vencidos
**Arquivo**: `matriz_agente_cobranca_acompanhamento_vencidos.sql`
**Output table**: `nekt_trusted.matriz_agente_cobranca_acompanhamento_vencidos`

```sql
WITH
params AS (SELECT CURRENT_DATE AS data_execucao),
titulos AS (
  SELECT
    cr.codcliente, cr.tipodocumento, cr.documento, cr.parcela,
    CAST(cr.datavencimento AS DATE) AS datavencimento,
    cr.saldodocumento,
    date_diff('day', CAST(cr.datavencimento AS DATE), p.data_execucao) AS dias_vencido,
    TRY_CAST(cr.documento AS BIGINT) AS doc_int
  FROM nekt_raw.mssql_matriz_dbo_cr_documentos cr
  CROSS JOIN params p
  WHERE cr.saldodocumento > 0
    AND cr.tipodocumento IN (10, 80, 70, 3, 7, 68)
    AND CAST(cr.datavencimento AS DATE) BETWEEN date_add('day', -180, p.data_execucao) AND date_add('day', -2, p.data_execucao)
),
pedidos_por_titulo AS (
  SELECT t.codcliente, t.tipodocumento, t.documento, t.parcela,
    MAX(regexp_extract(nf.observacoes, 'Pedido\(s\):\s*([0-9,]+)', 1)) AS pedidos_str
  FROM titulos t
  JOIN nekt_raw.mssql_matriz_dbo_nota_fiscal_capa nf
    ON TRY_CAST(nf.documentoorigem AS BIGINT) = t.doc_int
   AND nf.origemnota = 'Fatura'
  WHERE regexp_like(nf.observacoes, 'Pedido\(s\):')
  GROUP BY t.codcliente, t.tipodocumento, t.documento, t.parcela
),
linhas AS (
  SELECT t.codcliente, t.datavencimento, t.documento, t.saldodocumento, t.dias_vencido,
    CASE WHEN t.dias_vencido = 2 THEN 1
         WHEN t.dias_vencido BETWEEN 3 AND 10 THEN 2
         ELSE 3 END AS ciclo,
    CASE
      WHEN t.tipodocumento IN (3, 68) THEN
        'Cheque ' || t.documento || ' / venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
      WHEN ppt.pedidos_str IS NOT NULL AND ppt.pedidos_str <> '' THEN
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento || ' / Ped.' || ppt.pedidos_str
      ELSE
        'venc. ' || date_format(t.datavencimento, '%d/%m/%Y')
        || ' / Valor: R$ ' || replace(format('%.2f', t.saldodocumento), '.', ',')
        || ' / Doc.' || t.documento
    END AS linha_mensagem
  FROM titulos t
  LEFT JOIN pedidos_por_titulo ppt
    ON ppt.codcliente = t.codcliente AND ppt.tipodocumento = t.tipodocumento
   AND ppt.documento = t.documento AND ppt.parcela = t.parcela
),
clientes_clean AS (
  SELECT c.codcliente,
    regexp_replace(c.nome, '[\r\n\t]', ' ') AS nome,
    c.telefone AS telefone_raw,
    regexp_replace(COALESCE(c.telefone, ''), '[^0-9]', '') AS telefone_digitos
  FROM nekt_raw.mssql_matriz_dbo_clientes c
),
ciclos_por_cliente AS (
  SELECT codcliente, ciclo, COUNT(*) AS qtd
  FROM linhas GROUP BY codcliente, ciclo
),
ciclo_predominante AS (
  SELECT codcliente, ciclo,
    ROW_NUMBER() OVER (PARTITION BY codcliente ORDER BY qtd DESC, ciclo DESC) AS rn
  FROM ciclos_por_cliente
),
agg AS (
  SELECT l.codcliente, COUNT(*) AS qtd_titulos,
    SUM(l.saldodocumento) AS valor_total,
    MAX(l.dias_vencido) AS dias_vencido_max,
    array_join(array_agg(l.linha_mensagem), chr(10)) AS linhas_msg
  FROM linhas l GROUP BY l.codcliente
)
SELECT
  'PE' AS filial,
  cc.codcliente, cc.nome,
  cc.telefone_raw AS telefone,
  cc.telefone_digitos,
  CASE
    WHEN cc.telefone_digitos = '' THEN 'SEM CONTATO'
    WHEN LENGTH(cc.telefone_digitos) < 10 THEN 'CONTATO INVALIDO'
    WHEN LENGTH(cc.telefone_digitos) IN (10, 11) THEN 'OK'
    WHEN LENGTH(cc.telefone_digitos) IN (12, 13) AND SUBSTR(cc.telefone_digitos, 1, 2) = '55' THEN 'OK'
    ELSE 'CONTATO INVALIDO'
  END AS status_contato,
  a.qtd_titulos, a.valor_total,
  'Ciclo ' || CAST(cp.ciclo AS VARCHAR) AS ciclo_predominante,
  a.dias_vencido_max,
  'Olá, tudo bem?' || chr(10) || chr(10)
   || 'Cliente: ' || cc.nome || chr(10) || chr(10)
   || 'Verificamos que ficou pendente:' || chr(10) || chr(10)
   || a.linhas_msg AS mensagem,
  CAST(NULL AS VARCHAR) AS envio,
  CAST(NULL AS VARCHAR) AS enviado
FROM agg a
JOIN clientes_clean cc ON cc.codcliente = a.codcliente
JOIN ciclo_predominante cp ON cp.codcliente = a.codcliente AND cp.rn = 1
ORDER BY a.dias_vencido_max DESC, a.valor_total DESC
```

---

# ANEXO B — JSON dos 6 workflows n8n

> Todos os 6 workflows seguem o mesmo padrão (Manual Trigger → Read Sheets → Filter → Loop → Z-API → Wait → Mark Enviado). Diferem apenas no `documentId` da planilha e nas credenciais Z-API. Cada um é apresentado abaixo com seu JSON completo.

### Padrão de Filter (idêntico em todos)
```
envio ≠ "N"      (case-insensitive — pula linhas que Rubens marcou)
AND enviado ≠ "OK"   (anti-duplo)
AND status_contato contém "OK"  (só dispara contato válido)
AND telefone_digitos ≠ ""  (precisa ter número)
```

---

## B.1 Cobrança SC — Lembrete Semanal
**Arquivo**: `n8n_cobranca_sc_lembrete.json`
**Spreadsheet**: `1HDZx62IhpsbioCethOd0n-PBCQLd9Tdfku1rpXQdlys`
**Z-API**: instance SC

```json
{
  "name": "Cobrança SC — Lembrete Semanal",
  "nodes": [
    { "parameters": {}, "id": "a1111111-1111-1111-1111-111111111111", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [240, 300] },
    { "parameters": { "documentId": { "__rl": true, "value": "1HDZx62IhpsbioCethOd0n-PBCQLd9Tdfku1rpXQdlys", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "options": {} }, "id": "a2222222-2222-2222-2222-222222222222", "name": "Read Sheets", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [460, 300] },
    { "parameters": { "conditions": { "options": { "caseSensitive": false, "leftValue": "", "typeValidation": "loose" }, "conditions": [ { "id": "cond-envio", "leftValue": "={{ $json.envio }}", "rightValue": "N", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-enviado", "leftValue": "={{ $json.enviado }}", "rightValue": "OK", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-status", "leftValue": "={{ $json.status_contato }}", "rightValue": "OK", "operator": { "type": "string", "operation": "contains" } }, { "id": "cond-tel", "leftValue": "={{ $json.telefone_digitos }}", "rightValue": "", "operator": { "type": "string", "operation": "notEquals" } } ], "combinator": "and" }, "options": {} }, "id": "a3333333-3333-3333-3333-333333333333", "name": "Filter", "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [680, 300] },
    { "parameters": { "batchSize": 1, "options": {} }, "id": "a4444444-4444-4444-4444-444444444444", "name": "Loop", "type": "n8n-nodes-base.splitInBatches", "typeVersion": 3, "position": [900, 300] },
    { "parameters": { "method": "POST", "url": "=https://api.z-api.io/instances/3F4CA04EC2A9F2C35C05CE717FF40C71/token/DA5E5295DD430239591BB4B4/send-text", "sendHeaders": true, "headerParameters": { "parameters": [ { "name": "Client-Token", "value": "Fc7c6d29c0a2b420c9fccde34c997c5c9S" } ] }, "sendBody": true, "contentType": "json", "specifyBody": "json", "jsonBody": "={\n  \"phone\": \"{{ $json.telefone_digitos }}\",\n  \"message\": {{ JSON.stringify($json.mensagem) }}\n}", "options": {} }, "id": "a5555555-5555-5555-5555-555555555555", "name": "Z-API Send Text", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1120, 300] },
    { "parameters": { "amount": 4, "unit": "seconds" }, "id": "a6666666-6666-6666-6666-666666666666", "name": "Wait", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [1340, 300] },
    { "parameters": { "operation": "update", "documentId": { "__rl": true, "value": "1HDZx62IhpsbioCethOd0n-PBCQLd9Tdfku1rpXQdlys", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "columns": { "mappingMode": "defineBelow", "value": { "codcliente": "={{ $('Loop').item.json.codcliente }}", "enviado": "OK" }, "matchingColumns": ["codcliente"] }, "options": {} }, "id": "a7777777-7777-7777-7777-777777777777", "name": "Mark Enviado", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [1560, 300] }
  ],
  "connections": {
    "Manual Trigger": { "main": [[{ "node": "Read Sheets", "type": "main", "index": 0 }]] },
    "Read Sheets": { "main": [[{ "node": "Filter", "type": "main", "index": 0 }]] },
    "Filter": { "main": [ [{ "node": "Loop", "type": "main", "index": 0 }], [] ] },
    "Loop": { "main": [ [], [{ "node": "Z-API Send Text", "type": "main", "index": 0 }] ] },
    "Z-API Send Text": { "main": [[{ "node": "Wait", "type": "main", "index": 0 }]] },
    "Wait": { "main": [[{ "node": "Mark Enviado", "type": "main", "index": 0 }]] },
    "Mark Enviado": { "main": [[{ "node": "Loop", "type": "main", "index": 0 }]] }
  },
  "settings": { "executionOrder": "v1" }
}
```

---

## B.2 Cobrança SC — Acompanhamento Vencidos
**Arquivo**: `n8n_cobranca_sc_vencidos.json`
**Spreadsheet**: `1RQdWwEpyH6lSsAy56mS8WaF-_kYIBiw8OOZRHC4PROg`
**Z-API**: instance SC

```json
{
  "name": "Cobrança SC — Acompanhamento Vencidos",
  "nodes": [
    { "parameters": {}, "id": "b1111111-1111-1111-1111-111111111111", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [240, 300] },
    { "parameters": { "documentId": { "__rl": true, "value": "1RQdWwEpyH6lSsAy56mS8WaF-_kYIBiw8OOZRHC4PROg", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "options": {} }, "id": "b2222222-2222-2222-2222-222222222222", "name": "Read Sheets", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [460, 300] },
    { "parameters": { "conditions": { "options": { "caseSensitive": false, "leftValue": "", "typeValidation": "loose" }, "conditions": [ { "id": "cond-envio", "leftValue": "={{ $json.envio }}", "rightValue": "N", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-enviado", "leftValue": "={{ $json.enviado }}", "rightValue": "OK", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-status", "leftValue": "={{ $json.status_contato }}", "rightValue": "OK", "operator": { "type": "string", "operation": "contains" } }, { "id": "cond-tel", "leftValue": "={{ $json.telefone_digitos }}", "rightValue": "", "operator": { "type": "string", "operation": "notEquals" } } ], "combinator": "and" }, "options": {} }, "id": "b3333333-3333-3333-3333-333333333333", "name": "Filter", "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [680, 300] },
    { "parameters": { "batchSize": 1, "options": {} }, "id": "b4444444-4444-4444-4444-444444444444", "name": "Loop", "type": "n8n-nodes-base.splitInBatches", "typeVersion": 3, "position": [900, 300] },
    { "parameters": { "method": "POST", "url": "=https://api.z-api.io/instances/3F4CA04EC2A9F2C35C05CE717FF40C71/token/DA5E5295DD430239591BB4B4/send-text", "sendHeaders": true, "headerParameters": { "parameters": [ { "name": "Client-Token", "value": "Fc7c6d29c0a2b420c9fccde34c997c5c9S" } ] }, "sendBody": true, "contentType": "json", "specifyBody": "json", "jsonBody": "={\n  \"phone\": \"{{ $json.telefone_digitos }}\",\n  \"message\": {{ JSON.stringify($json.mensagem) }}\n}", "options": {} }, "id": "b5555555-5555-5555-5555-555555555555", "name": "Z-API Send Text", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1120, 300] },
    { "parameters": { "amount": 4, "unit": "seconds" }, "id": "b6666666-6666-6666-6666-666666666666", "name": "Wait", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [1340, 300] },
    { "parameters": { "operation": "update", "documentId": { "__rl": true, "value": "1RQdWwEpyH6lSsAy56mS8WaF-_kYIBiw8OOZRHC4PROg", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "columns": { "mappingMode": "defineBelow", "value": { "codcliente": "={{ $('Loop').item.json.codcliente }}", "enviado": "OK" }, "matchingColumns": ["codcliente"] }, "options": {} }, "id": "b7777777-7777-7777-7777-777777777777", "name": "Mark Enviado", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [1560, 300] }
  ],
  "connections": {
    "Manual Trigger": { "main": [[{ "node": "Read Sheets", "type": "main", "index": 0 }]] },
    "Read Sheets": { "main": [[{ "node": "Filter", "type": "main", "index": 0 }]] },
    "Filter": { "main": [ [{ "node": "Loop", "type": "main", "index": 0 }], [] ] },
    "Loop": { "main": [ [], [{ "node": "Z-API Send Text", "type": "main", "index": 0 }] ] },
    "Z-API Send Text": { "main": [[{ "node": "Wait", "type": "main", "index": 0 }]] },
    "Wait": { "main": [[{ "node": "Mark Enviado", "type": "main", "index": 0 }]] },
    "Mark Enviado": { "main": [[{ "node": "Loop", "type": "main", "index": 0 }]] }
  },
  "settings": { "executionOrder": "v1" }
}
```

---

## B.3 Cobrança SP — Lembrete Semanal
**Arquivo**: `n8n_cobranca_sp_lembrete.json`
**Spreadsheet**: `1ezrtPXOAUkpDt8WWpuYSmhQCrvZfqavRtgbOZRTovNg`
**Z-API**: instance SP

```json
{
  "name": "Cobrança SP — Lembrete Semanal",
  "nodes": [
    { "parameters": {}, "id": "c1111111-1111-1111-1111-111111111111", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [240, 300] },
    { "parameters": { "documentId": { "__rl": true, "value": "1ezrtPXOAUkpDt8WWpuYSmhQCrvZfqavRtgbOZRTovNg", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "options": {} }, "id": "c2222222-2222-2222-2222-222222222222", "name": "Read Sheets", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [460, 300] },
    { "parameters": { "conditions": { "options": { "caseSensitive": false, "leftValue": "", "typeValidation": "loose" }, "conditions": [ { "id": "cond-envio", "leftValue": "={{ $json.envio }}", "rightValue": "N", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-enviado", "leftValue": "={{ $json.enviado }}", "rightValue": "OK", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-status", "leftValue": "={{ $json.status_contato }}", "rightValue": "OK", "operator": { "type": "string", "operation": "contains" } }, { "id": "cond-tel", "leftValue": "={{ $json.telefone_digitos }}", "rightValue": "", "operator": { "type": "string", "operation": "notEquals" } } ], "combinator": "and" }, "options": {} }, "id": "c3333333-3333-3333-3333-333333333333", "name": "Filter", "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [680, 300] },
    { "parameters": { "batchSize": 1, "options": {} }, "id": "c4444444-4444-4444-4444-444444444444", "name": "Loop", "type": "n8n-nodes-base.splitInBatches", "typeVersion": 3, "position": [900, 300] },
    { "parameters": { "method": "POST", "url": "=https://api.z-api.io/instances/3F5095DD7D7FF21EFBAF0E47AC50613B/token/94F9624905675A9AE02241B1/send-text", "sendHeaders": true, "headerParameters": { "parameters": [ { "name": "Client-Token", "value": "F46e884cedc2249428dec027269797b7fS" } ] }, "sendBody": true, "contentType": "json", "specifyBody": "json", "jsonBody": "={\n  \"phone\": \"{{ $json.telefone_digitos }}\",\n  \"message\": {{ JSON.stringify($json.mensagem) }}\n}", "options": {} }, "id": "c5555555-5555-5555-5555-555555555555", "name": "Z-API Send Text", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1120, 300] },
    { "parameters": { "amount": 4, "unit": "seconds" }, "id": "c6666666-6666-6666-6666-666666666666", "name": "Wait", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [1340, 300] },
    { "parameters": { "operation": "update", "documentId": { "__rl": true, "value": "1ezrtPXOAUkpDt8WWpuYSmhQCrvZfqavRtgbOZRTovNg", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "columns": { "mappingMode": "defineBelow", "value": { "codcliente": "={{ $('Loop').item.json.codcliente }}", "enviado": "OK" }, "matchingColumns": ["codcliente"] }, "options": {} }, "id": "c7777777-7777-7777-7777-777777777777", "name": "Mark Enviado", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [1560, 300] }
  ],
  "connections": {
    "Manual Trigger": { "main": [[{ "node": "Read Sheets", "type": "main", "index": 0 }]] },
    "Read Sheets": { "main": [[{ "node": "Filter", "type": "main", "index": 0 }]] },
    "Filter": { "main": [ [{ "node": "Loop", "type": "main", "index": 0 }], [] ] },
    "Loop": { "main": [ [], [{ "node": "Z-API Send Text", "type": "main", "index": 0 }] ] },
    "Z-API Send Text": { "main": [[{ "node": "Wait", "type": "main", "index": 0 }]] },
    "Wait": { "main": [[{ "node": "Mark Enviado", "type": "main", "index": 0 }]] },
    "Mark Enviado": { "main": [[{ "node": "Loop", "type": "main", "index": 0 }]] }
  },
  "settings": { "executionOrder": "v1" }
}
```

---

## B.4 Cobrança SP — Acompanhamento Vencidos
**Arquivo**: `n8n_cobranca_sp_vencidos.json`
**Spreadsheet**: `1qed4eWDTS3nQJShO13Jcg0C7a2ANF0dYqIR3N8l5dCg`
**Z-API**: instance SP

```json
{
  "name": "Cobrança SP — Acompanhamento Vencidos",
  "nodes": [
    { "parameters": {}, "id": "d1111111-1111-1111-1111-111111111111", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [240, 300] },
    { "parameters": { "documentId": { "__rl": true, "value": "1qed4eWDTS3nQJShO13Jcg0C7a2ANF0dYqIR3N8l5dCg", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "options": {} }, "id": "d2222222-2222-2222-2222-222222222222", "name": "Read Sheets", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [460, 300] },
    { "parameters": { "conditions": { "options": { "caseSensitive": false, "leftValue": "", "typeValidation": "loose" }, "conditions": [ { "id": "cond-envio", "leftValue": "={{ $json.envio }}", "rightValue": "N", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-enviado", "leftValue": "={{ $json.enviado }}", "rightValue": "OK", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-status", "leftValue": "={{ $json.status_contato }}", "rightValue": "OK", "operator": { "type": "string", "operation": "contains" } }, { "id": "cond-tel", "leftValue": "={{ $json.telefone_digitos }}", "rightValue": "", "operator": { "type": "string", "operation": "notEquals" } } ], "combinator": "and" }, "options": {} }, "id": "d3333333-3333-3333-3333-333333333333", "name": "Filter", "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [680, 300] },
    { "parameters": { "batchSize": 1, "options": {} }, "id": "d4444444-4444-4444-4444-444444444444", "name": "Loop", "type": "n8n-nodes-base.splitInBatches", "typeVersion": 3, "position": [900, 300] },
    { "parameters": { "method": "POST", "url": "=https://api.z-api.io/instances/3F5095DD7D7FF21EFBAF0E47AC50613B/token/94F9624905675A9AE02241B1/send-text", "sendHeaders": true, "headerParameters": { "parameters": [ { "name": "Client-Token", "value": "F46e884cedc2249428dec027269797b7fS" } ] }, "sendBody": true, "contentType": "json", "specifyBody": "json", "jsonBody": "={\n  \"phone\": \"{{ $json.telefone_digitos }}\",\n  \"message\": {{ JSON.stringify($json.mensagem) }}\n}", "options": {} }, "id": "d5555555-5555-5555-5555-555555555555", "name": "Z-API Send Text", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1120, 300] },
    { "parameters": { "amount": 4, "unit": "seconds" }, "id": "d6666666-6666-6666-6666-666666666666", "name": "Wait", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [1340, 300] },
    { "parameters": { "operation": "update", "documentId": { "__rl": true, "value": "1qed4eWDTS3nQJShO13Jcg0C7a2ANF0dYqIR3N8l5dCg", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "columns": { "mappingMode": "defineBelow", "value": { "codcliente": "={{ $('Loop').item.json.codcliente }}", "enviado": "OK" }, "matchingColumns": ["codcliente"] }, "options": {} }, "id": "d7777777-7777-7777-7777-777777777777", "name": "Mark Enviado", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [1560, 300] }
  ],
  "connections": {
    "Manual Trigger": { "main": [[{ "node": "Read Sheets", "type": "main", "index": 0 }]] },
    "Read Sheets": { "main": [[{ "node": "Filter", "type": "main", "index": 0 }]] },
    "Filter": { "main": [ [{ "node": "Loop", "type": "main", "index": 0 }], [] ] },
    "Loop": { "main": [ [], [{ "node": "Z-API Send Text", "type": "main", "index": 0 }] ] },
    "Z-API Send Text": { "main": [[{ "node": "Wait", "type": "main", "index": 0 }]] },
    "Wait": { "main": [[{ "node": "Mark Enviado", "type": "main", "index": 0 }]] },
    "Mark Enviado": { "main": [[{ "node": "Loop", "type": "main", "index": 0 }]] }
  },
  "settings": { "executionOrder": "v1" }
}
```

---

## B.5 Cobrança PE — Lembrete Semanal
**Arquivo**: `n8n_cobranca_pe_lembrete.json`
**Spreadsheet**: `1BSsLJoUF8zoXZ-0bg-ciOvyxOf8A3cWIZXn3pAgbtAE`
**Z-API**: instance PE

```json
{
  "name": "Cobrança PE — Lembrete Semanal",
  "nodes": [
    { "parameters": {}, "id": "e1111111-1111-1111-1111-111111111111", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [240, 300] },
    { "parameters": { "documentId": { "__rl": true, "value": "1BSsLJoUF8zoXZ-0bg-ciOvyxOf8A3cWIZXn3pAgbtAE", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "options": {} }, "id": "e2222222-2222-2222-2222-222222222222", "name": "Read Sheets", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [460, 300] },
    { "parameters": { "conditions": { "options": { "caseSensitive": false, "leftValue": "", "typeValidation": "loose" }, "conditions": [ { "id": "cond-envio", "leftValue": "={{ $json.envio }}", "rightValue": "N", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-enviado", "leftValue": "={{ $json.enviado }}", "rightValue": "OK", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-status", "leftValue": "={{ $json.status_contato }}", "rightValue": "OK", "operator": { "type": "string", "operation": "contains" } }, { "id": "cond-tel", "leftValue": "={{ $json.telefone_digitos }}", "rightValue": "", "operator": { "type": "string", "operation": "notEquals" } } ], "combinator": "and" }, "options": {} }, "id": "e3333333-3333-3333-3333-333333333333", "name": "Filter", "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [680, 300] },
    { "parameters": { "batchSize": 1, "options": {} }, "id": "e4444444-4444-4444-4444-444444444444", "name": "Loop", "type": "n8n-nodes-base.splitInBatches", "typeVersion": 3, "position": [900, 300] },
    { "parameters": { "method": "POST", "url": "=https://api.z-api.io/instances/3F50950C8D302225807376D0BCEB03A2/token/65FF9A941F2B71EB3B6262BF/send-text", "sendHeaders": true, "headerParameters": { "parameters": [ { "name": "Client-Token", "value": "F46e884cedc2249428dec027269797b7fS" } ] }, "sendBody": true, "contentType": "json", "specifyBody": "json", "jsonBody": "={\n  \"phone\": \"{{ $json.telefone_digitos }}\",\n  \"message\": {{ JSON.stringify($json.mensagem) }}\n}", "options": {} }, "id": "e5555555-5555-5555-5555-555555555555", "name": "Z-API Send Text", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1120, 300] },
    { "parameters": { "amount": 4, "unit": "seconds" }, "id": "e6666666-6666-6666-6666-666666666666", "name": "Wait", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [1340, 300] },
    { "parameters": { "operation": "update", "documentId": { "__rl": true, "value": "1BSsLJoUF8zoXZ-0bg-ciOvyxOf8A3cWIZXn3pAgbtAE", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "columns": { "mappingMode": "defineBelow", "value": { "codcliente": "={{ $('Loop').item.json.codcliente }}", "enviado": "OK" }, "matchingColumns": ["codcliente"] }, "options": {} }, "id": "e7777777-7777-7777-7777-777777777777", "name": "Mark Enviado", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [1560, 300] }
  ],
  "connections": {
    "Manual Trigger": { "main": [[{ "node": "Read Sheets", "type": "main", "index": 0 }]] },
    "Read Sheets": { "main": [[{ "node": "Filter", "type": "main", "index": 0 }]] },
    "Filter": { "main": [ [{ "node": "Loop", "type": "main", "index": 0 }], [] ] },
    "Loop": { "main": [ [], [{ "node": "Z-API Send Text", "type": "main", "index": 0 }] ] },
    "Z-API Send Text": { "main": [[{ "node": "Wait", "type": "main", "index": 0 }]] },
    "Wait": { "main": [[{ "node": "Mark Enviado", "type": "main", "index": 0 }]] },
    "Mark Enviado": { "main": [[{ "node": "Loop", "type": "main", "index": 0 }]] }
  },
  "settings": { "executionOrder": "v1" }
}
```

---

## B.6 Cobrança PE — Acompanhamento Vencidos
**Arquivo**: `n8n_cobranca_pe_vencidos.json`
**Spreadsheet**: `1BfHsVRx6dnrbNhaMTPayz8Lfp4q06AJPu5HoRnGNed4`
**Z-API**: instance PE

```json
{
  "name": "Cobrança PE — Acompanhamento Vencidos",
  "nodes": [
    { "parameters": {}, "id": "f1111111-1111-1111-1111-111111111111", "name": "Manual Trigger", "type": "n8n-nodes-base.manualTrigger", "typeVersion": 1, "position": [240, 300] },
    { "parameters": { "documentId": { "__rl": true, "value": "1BfHsVRx6dnrbNhaMTPayz8Lfp4q06AJPu5HoRnGNed4", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "options": {} }, "id": "f2222222-2222-2222-2222-222222222222", "name": "Read Sheets", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [460, 300] },
    { "parameters": { "conditions": { "options": { "caseSensitive": false, "leftValue": "", "typeValidation": "loose" }, "conditions": [ { "id": "cond-envio", "leftValue": "={{ $json.envio }}", "rightValue": "N", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-enviado", "leftValue": "={{ $json.enviado }}", "rightValue": "OK", "operator": { "type": "string", "operation": "notEquals" } }, { "id": "cond-status", "leftValue": "={{ $json.status_contato }}", "rightValue": "OK", "operator": { "type": "string", "operation": "contains" } }, { "id": "cond-tel", "leftValue": "={{ $json.telefone_digitos }}", "rightValue": "", "operator": { "type": "string", "operation": "notEquals" } } ], "combinator": "and" }, "options": {} }, "id": "f3333333-3333-3333-3333-333333333333", "name": "Filter", "type": "n8n-nodes-base.if", "typeVersion": 2, "position": [680, 300] },
    { "parameters": { "batchSize": 1, "options": {} }, "id": "f4444444-4444-4444-4444-444444444444", "name": "Loop", "type": "n8n-nodes-base.splitInBatches", "typeVersion": 3, "position": [900, 300] },
    { "parameters": { "method": "POST", "url": "=https://api.z-api.io/instances/3F50950C8D302225807376D0BCEB03A2/token/65FF9A941F2B71EB3B6262BF/send-text", "sendHeaders": true, "headerParameters": { "parameters": [ { "name": "Client-Token", "value": "F46e884cedc2249428dec027269797b7fS" } ] }, "sendBody": true, "contentType": "json", "specifyBody": "json", "jsonBody": "={\n  \"phone\": \"{{ $json.telefone_digitos }}\",\n  \"message\": {{ JSON.stringify($json.mensagem) }}\n}", "options": {} }, "id": "f5555555-5555-5555-5555-555555555555", "name": "Z-API Send Text", "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1120, 300] },
    { "parameters": { "amount": 4, "unit": "seconds" }, "id": "f6666666-6666-6666-6666-666666666666", "name": "Wait", "type": "n8n-nodes-base.wait", "typeVersion": 1.1, "position": [1340, 300] },
    { "parameters": { "operation": "update", "documentId": { "__rl": true, "value": "1BfHsVRx6dnrbNhaMTPayz8Lfp4q06AJPu5HoRnGNed4", "mode": "id" }, "sheetName": { "__rl": true, "value": "dados", "mode": "name" }, "columns": { "mappingMode": "defineBelow", "value": { "codcliente": "={{ $('Loop').item.json.codcliente }}", "enviado": "OK" }, "matchingColumns": ["codcliente"] }, "options": {} }, "id": "f7777777-7777-7777-7777-777777777777", "name": "Mark Enviado", "type": "n8n-nodes-base.googleSheets", "typeVersion": 4.5, "position": [1560, 300] }
  ],
  "connections": {
    "Manual Trigger": { "main": [[{ "node": "Read Sheets", "type": "main", "index": 0 }]] },
    "Read Sheets": { "main": [[{ "node": "Filter", "type": "main", "index": 0 }]] },
    "Filter": { "main": [ [{ "node": "Loop", "type": "main", "index": 0 }], [] ] },
    "Loop": { "main": [ [], [{ "node": "Z-API Send Text", "type": "main", "index": 0 }] ] },
    "Z-API Send Text": { "main": [[{ "node": "Wait", "type": "main", "index": 0 }]] },
    "Wait": { "main": [[{ "node": "Mark Enviado", "type": "main", "index": 0 }]] },
    "Mark Enviado": { "main": [[{ "node": "Loop", "type": "main", "index": 0 }]] }
  },
  "settings": { "executionOrder": "v1" }
}
```

---

_Documentação gerada em 24/jun/2026. Sistema desenvolvido por Lucas Lenzi (Atom Work) para Rubens / Soul Têxtil._
_Branch git: `claude/brave-bohr-b8a4je` no repo `llucaslenzi-super/Lucas-atom`._
