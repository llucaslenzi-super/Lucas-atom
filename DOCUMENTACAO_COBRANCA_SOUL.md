# Cobrança WhatsApp Soul Têxtil — Documentação Completa

> Sistema automatizado de cobrança via WhatsApp para Soul Têxtil, cobrindo 3 filiais (Gaspar/SC, Loja SP, Matriz PE) com 2 tipos de fluxo (Lembrete Semanal + Acompanhamento de Vencidos), totalizando 6 agentes ativos.

---

## 1. Visão geral

### Objetivo
Disparar mensagens automatizadas de cobrança via WhatsApp para clientes da Soul Têxtil, com base nos títulos a receber do ERP (SQL Server). Régua de cobrança detalhada nos docs do Drive (`SOUL - RUBENS / AGENTE DE COBRANÇA WHATSAPP`).

### Arquitetura

```
ERP SQL Server (3 databases) 
    ↓ extração via Nekt
Nekt (Athena/Trino) → 6 queries SQL
    ↓ Destination Google Sheets
Google Sheets (6 planilhas, 1 por fluxo) — preview/auditoria
    ↓ Rubens revisa, marca N em quem quer pular
n8n (6 workflows, gatilho manual)
    ↓ Z-API send-text (3 instâncias, 1 por filial)
WhatsApp do cliente
```

### Princípios

- **Gatilhos manuais** em todas as etapas (Run now no Nekt, Execute Workflow no n8n).
- **Anti-duplo**: cada planilha tem coluna `enviado` que o n8n marca `OK` após disparo. Filter pula linhas com `enviado=OK`.
- **Override humano**: coluna `ENVIO` na planilha; se Rubens digitar `N` ou `n`, pula a linha.
- **Filtro de qualidade**: só dispara linhas com `status_contato = OK ✅`.
- **Rate limit**: Wait de 4 segundos entre disparos (Z-API barra acima de 1 msg/s sustentado).

---

## 2. Stack e credenciais

### Nekt
- Engine: Amazon Athena (Trino SQL dialect)
- Output layer: `nekt_trusted`
- Folders: `gaspar_cobranca`, `loja_sp_cobranca`, `matriz_cobranca`

### Google Sheets
Drive folder: `SOUL - RUBENS / AGENTE DE COBRANÇA WHATSAPP` (id `1g00PjGA72gYve0dm3s8iGw9axvz4Ett5`)

### n8n
- 6 workflows com gatilho manual
- Credencial Google Sheets OAuth única (reutilizada nos 12 nós Read/Update)

### Z-API (3 instâncias separadas)

| Filial | Instance ID | Token | Client-Token |
| --- | --- | --- | --- |
| SC (Gaspar) | `3F4CA04EC2A9F2C35C05CE717FF40C71` | `DA5E5295DD430239591BB4B4` | `Fc7c6d29c0a2b420c9fccde34c997c5c9S` |
| SP (Loja SP) | `3F5095DD7D7FF21EFBAF0E47AC50613B` | `94F9624905675A9AE02241B1` | `F46e884cedc2249428dec027269797b7fS` |
| PE (Matriz) | `3F50950C8D302225807376D0BCEB03A2` | `65FF9A941F2B71EB3B6262BF` | `F46e884cedc2249428dec027269797b7fS` |

> Endpoint padrão: `POST https://api.z-api.io/instances/{INSTANCE_ID}/token/{TOKEN}/send-text` com header `Client-Token: {CLIENT_TOKEN}` e body `{ "phone": "55XXYYYYYYYYY", "message": "..." }`.

---

## 3. Régua de cobrança (do doc do Rubens)

### Filtros comuns aos dois fluxos
- `saldodocumento > 0`
- `tipodocumento IN (10, 80, 70, 3, 7, 68)` — Boleto, PIX, Cartão Parcelado, Cheque Terceiros, Crediário, Cheques Repassados
- Limpeza de telefone: `regexp_replace(telefone, '[^0-9]', '')`
- Limpeza de nome: `regexp_replace(nome, '[\r\n\t]', ' ')`

### Status do contato
```
vazio              → SEM CONTATO
< 10 dígitos       → CONTATO INVALIDO
10-11 dígitos      → OK ✅
12-13 dígitos com prefixo 55 → OK ✅
demais             → CONTATO INVALIDO
```

### Fluxo 1 — Lembrete Semanal (a vencer)
Roda em **seg / qua / sex**. Janela depende do dia:

| Dia (date_format %a) | Janela de vencimento |
| --- | --- |
| Mon (segunda) | hoje → hoje+2 (até quarta) |
| Wed (quarta) | hoje → hoje+2 (até sexta) |
| Fri (sexta) | hoje → hoje+3 (até segunda) |
| Outros | hoje → hoje+2 (degrada graciosamente) |

Cabeçalho da mensagem:
```
Olá, tudo bem?

Cliente: {nome}

Lembrete, nesta semana você tem vencimento(s) para:

{linhas}
```

### Fluxo 2 — Acompanhamento de Vencidos (depois do venc)
Roda **todo dia útil**. Janela fixa: `datavencimento BETWEEN hoje-180 AND hoje-2`.

Classificação por ciclo:

| Ciclo | dias_vencido | Disparo |
| --- | --- | --- |
| 1 | exatamente 2 dias | primeira cobrança |
| 2 | 3 a 10 dias | cobrança diária |
| 3 | 11 a 180 dias | cobrança contínua (todo dia útil) |

Cabeçalho da mensagem:
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

---

## 4. Diferenças por filial — extração de pedido

### Gaspar (SC)
- DocumentoOrigem no CR começa com `RNF{N}`.
- Path: `CR.documentoorigem LIKE 'RNF%'` → extrai N → `NF.referencia = N` → `FaturaItens.nrfatura = NF.documentoorigem` → `array_agg(DISTINCT nrpedido)`.
- Usa tabela `fatura_itens`.

### Loja SP e Matriz PE
- Pedido vem direto da string `Pedido(s): N1,N2,...` em `nota_fiscal_capa.observacoes`.
- Path: `CR.documento = NF.documentoorigem` (cast BIGINT) + `NF.origemnota = 'Fatura'` + `regexp_extract(NF.observacoes, 'Pedido\(s\):\s*([0-9,]+)', 1)`.
- **NÃO usa** `fatura_itens`.
- Em PE, ~97% das NFs Fatura têm `codigodestinatario = 999999` (Consumidor Final) → baixa cobertura de Ped.{N} na mensagem (≈19.5%).

---

## 5. Tabelas-fonte (Nekt nekt_raw)

### Gaspar (SC)
- `mssql_gaspar_dbo_cr_documentos`
- `mssql_gaspar_dbo_clientes`
- `mssql_gaspar_dbo_nota_fiscal_capa`
- `mssql_gaspar_dbo_fatura_itens`

### Loja SP
- `mssql_loja_sp_dbo_cr_documentos`
- `mssql_loja_sp_dbo_clientes`
- `mssql_loja_sp_dbo_nota_fiscal_capa`

### Matriz PE
- `mssql_matriz_dbo_cr_documentos`
- `mssql_matriz_dbo_clientes`
- `mssql_matriz_dbo_nota_fiscal_capa`

---

## 6. Os 6 agentes

### Estrutura padrão (todos seguem isso)

**Cabeçalho da planilha (11 colunas para Lembrete, 13 para Vencidos):**

```
filial, codcliente, nome, telefone, telefone_digitos,
status_contato, qtd_titulos, valor_total,
[ciclo_predominante, dias_vencido_max — só Vencidos]
mensagem, ENVIO, enviado
```

**Workflow n8n padrão:**
```
[Manual Trigger]
   → [Read Sheets]
   → [Filter] (envio≠N, enviado≠OK, status_contato contém OK, telefone preenchido)
      ├─ true  → [Loop batch=1]
      │           → [Z-API Send Text] (POST send-text)
      │           → [Wait 4s]
      │           → [Mark Enviado] (escreve "OK" na coluna enviado)
      │           → loop volta
      └─ false → descarta (não dispara)
```

### Tabela resumo dos 6 fluxos

| # | Fluxo | Query Nekt (output table) | Spreadsheet ID | Workflow n8n | Z-API |
| --- | --- | --- | --- | --- | --- |
| 1 | SC Lembrete | `gaspar_agente_cobranca_lembrete_semanalv2` | `1HDZx62IhpsbioCethOd0n-PBCQLd9Tdfku1rpXQdlys` | `n8n_cobranca_sc_lembrete.json` | SC |
| 2 | SC Vencidos | `gaspar_agente_cobranca_acompanhamento_vencidos` | `1RQdWwEpyH6lSsAy56mS8WaF-_kYIBiw8OOZRHC4PROg` | `n8n_cobranca_sc_vencidos.json` | SC |
| 3 | SP Lembrete | `loja_sp_agente_cobranca_lembrete_semanal` | `1ezrtPXOAUkpDt8WWpuYSmhQCrvZfqavRtgbOZRTovNg` | `n8n_cobranca_sp_lembrete.json` | SP |
| 4 | SP Vencidos | `loja_sp_agente_cobranca_acompanhamento_vencidos` | `1qed4eWDTS3nQJShO13Jcg0C7a2ANF0dYqIR3N8l5dCg` | `n8n_cobranca_sp_vencidos.json` | SP |
| 5 | PE Lembrete | `matriz_agente_cobranca_lembrete_semanal` | `1BSsLJoUF8zoXZ-0bg-ciOvyxOf8A3cWIZXn3pAgbtAE` | `n8n_cobranca_pe_lembrete.json` | PE |
| 6 | PE Vencidos | `matriz_agente_cobranca_acompanhamento_vencidos` | `1BfHsVRx6dnrbNhaMTPayz8Lfp4q06AJPu5HoRnGNed4` | `n8n_cobranca_pe_vencidos.json` | PE |

### Configuração Destination Google Sheets (em cada query Nekt)

- **Tab name**: `dados`
- **Cell range to clear**: `A2:K` (Lembrete) ou `A2:M` (Vencidos)
- **Trigger**: manual
- **Service account da Nekt**: compartilhar a planilha com o e-mail fornecido pela Nekt (mesmo nas 6)

---

## 7. Volumetria validada (24/jun/2026)

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

## 8. Bugs e correções importantes

### Bug 1 — `day_of_week` no engine de execução do Nekt
**Sintoma**: Query Lembrete produziu janela 17-20 em vez de 17-19 (incluiu dia a mais).
**Causa**: A `CASE day_of_week(...) WHEN 5 THEN +3 ELSE +2` rodava com semântica de engine diferente do Trino (Trino: 1=Monday; Spark/BigQuery: 1=Sunday). O engine de execução do pipeline Nekt difere do Explorer.
**Fix**: Trocar `day_of_week(...) = 5` por `date_format(..., '%a') = 'Fri'`, que retorna `Mon/Tue/.../Sun` e é determinístico em qualquer engine.

### Bug 2 — Planilha "Forbidden" no n8n
**Sintoma**: Erro `Forbidden - perhaps check your credentials?` no nó Read Sheets.
**Causa**: Service account/conta OAuth do n8n não tem acesso à planilha.
**Fix**: Compartilhar cada planilha nova com o e-mail da credencial Google Sheets do n8n (Editor).

### Bug 3 — Caminho de pedido errado em SP/PE
**Sintoma**: Cliente sem pedido aparecendo na mensagem.
**Causa**: SP e PE não usam `RNF→FaturaItens` como Gaspar — pedido vem da string `Pedido(s):` em `NF.observacoes`.
**Fix**: Path específico via `regexp_extract` documentado acima.

### Bug 4 — Tabela materializada não atualizou após edição
**Sintoma**: Editou a query no Nekt, salvou, Run now, mas a tabela continuou com dados antigos.
**Causa**: O Run now do Destination não re-executa a query — só re-escreve a partir da tabela materializada. Precisa rodar Run now na **Query** primeiro, depois no Destination (ou usar trigger por evento).
**Fix**: Configurar trigger por evento — Destination roda automaticamente após Query terminar.

---

## 9. Operação diária (passo a passo do Rubens)

### Lembrete (seg/qua/sex de manhã)
1. Nekt → Queries → seleciona a query da filial → **Run now** (espera 5-6 min)
2. (trigger automático) Destination escreve na planilha
3. Abre planilha → revisa quem vai receber → marca `N` na coluna `ENVIO` em quem quer pular
4. n8n → Workflow da filial → **Execute Workflow**
5. Mensagens disparam em ~1 por 4 segundos. Coluna `enviado` vai virando `OK` linha por linha.

### Vencidos (todo dia útil de manhã)
Mesmo fluxo, com 2 colunas extras visíveis: `Ciclo_Predominante` (1/2/3) e `Dias_Vencido_Max`. Ordenado por dias_vencido_max desc — clientes mais atrasados em cima.

### Formatação condicional sugerida (Sheets)
Em cada planilha, na coluna `enviado` (K nas de Lembrete, M nas de Vencidos):
- **Formatar → Formatação condicional**
- "O texto contém exatamente" `OK` → fundo verde, texto branco bold

---

## 10. Próximas evoluções possíveis

- **Histórico**: hoje a Nekt sobrescreve a planilha (clear A2:K/M). Pra ter histórico, criar tabela append-only `cobranca_log` que recebe linhas de cada execução.
- **Marca "NAO ENVIADO"**: implementação adicional onde linhas que falharam no filtro recebem marcação explícita (em vez de ficar vazio). Workflow ramo duplo (testado em versão anterior do PE Vencidos, depois revertido pra estrutura simples).
- **Schedule automático**: hoje tudo é manual. Daria pra ativar cron na Nekt (08:30 seg/qua/sex pra Lembrete, dia útil pra Vencidos) e schedule trigger no n8n logo depois.
- **Métricas**: dashboard com taxa de resposta dos clientes, valor recuperado por ciclo, tempo médio de pagamento após cobrança.
- **Cliente Yvii** e similares com `status_contato = CONTATO INVALIDO` aparecem na planilha mas n8n pula — operadora pode corrigir o telefone na coluna `telefone_digitos` E mudar `status_contato` pra `OK` antes de re-executar.

---

## 11. Glossário rápido

- **Régua**: política de cobrança em ciclos (quando disparar baseado em dias de atraso)
- **RNF / ROM**: prefixos do campo `documentoorigem` na tabela CR — específicos do ERP da Soul
- **NrFatura**: número interno da fatura (BIGINT)
- **NrPedido**: número do pedido de venda
- **CR Documentos**: tabela de títulos a receber do ERP (Contas a Receber)
- **Ciclo predominante**: o ciclo do título mais antigo de um cliente (usado pra rotular o cliente como um todo)

---

## 12. Repositório

Branch: `claude/brave-bohr-b8a4je` no repo `llucaslenzi-super/Lucas-atom`.

Arquivos:
- `gaspar_agente_cobranca_lembrete_semanal.sql`
- `gaspar_agente_cobranca_acompanhamento_vencidos.sql`
- `loja_sp_agente_cobranca_lembrete_semanal.sql`
- `loja_sp_agente_cobranca_acompanhamento_vencidos.sql`
- `matriz_agente_cobranca_lembrete_semanal.sql`
- `matriz_agente_cobranca_acompanhamento_vencidos.sql`
- `n8n_cobranca_sc_lembrete.json`
- `n8n_cobranca_sc_vencidos.json`
- `n8n_cobranca_sp_lembrete.json`
- `n8n_cobranca_sp_vencidos.json`
- `n8n_cobranca_pe_lembrete.json`
- `n8n_cobranca_pe_vencidos.json`

---

_Documentação gerada em 24/jun/2026. Sistema desenvolvido por Lucas Lenzi (Atom Work) para Rubens / Soul Têxtil._
