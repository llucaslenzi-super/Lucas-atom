# API de Cobrança Santander — Referência técnica

> Doc técnica da API `collection_bill_management/v2` do Santander, com os endpoints validados em sandbox durante a integração da Soul Têxtil.

---

## Sumário

1. [Endpoints e URLs](#1-endpoints-e-urls)
2. [Autenticação (OAuth2 + mTLS)](#2-autenticação-oauth2--mtls)
3. [Workspace de Cobrança](#3-workspace-de-cobrança)
4. [Emissão de Boleto](#4-emissão-de-boleto)
5. [Consulta e instruções](#5-consulta-e-instruções)
6. [Geração de PDF](#6-geração-de-pdf)
7. [Códigos de erro](#7-códigos-de-erro)
8. [Mapping ERP Soul → API Santander](#8-mapping-erp-soul--api-santander)
9. [Diferenças vs Sicoob/Itaú](#9-diferenças-vs-sicoobitaú)
10. [Testes reais executados](#10-testes-reais-executados)

---

## 1. Endpoints e URLs

| Ambiente | Base URL API | OAuth Token URL |
|---|---|---|
| Sandbox  | `https://trust-sandbox.api.santander.com.br/collection_bill_management/v2` | `https://trust-sandbox.api.santander.com.br/auth/oauth/v2/token` |
| Produção | `https://trust-open.api.santander.com.br/collection_bill_management/v2` | `https://trust-open.api.santander.com.br/auth/oauth/v2/token` |

**Rotas usadas:**

| Método | Path | O que faz |
|---|---|---|
| POST | `/workspaces` | Cria workspace de cobrança (1x por convênio) |
| GET | `/workspaces` | Lista workspaces |
| GET | `/workspaces/{workspace_id}` | Detalhe de 1 workspace |
| PATCH | `/workspaces/{workspace_id}` | Atualiza workspace |
| DELETE | `/workspaces/{workspace_id}` | Cancela workspace |
| POST | `/workspaces/{workspace_id}/bank_slips` | **Registra boleto** (emissão) |
| PATCH | `/workspaces/{workspace_id}/bank_slips` | Instruções (baixar, protestar, alterar) |
| GET | `/workspaces/{workspace_id}/bank_slips` | Lista paginada (só status LIQUIDADO) |
| GET | `/workspaces/{workspace_id}/bank_slips/{bank_slip_id}` | Consulta SONDA (dados do registro) |
| GET | `/bills?beneficiaryCode=…&bankNumber=…` | Busca boleto por Nosso Número |
| GET | `/bills/{bill_id}` | Busca boleto por ID (composto) |
| POST | `/bills/{bill_id}/bank_slips` | **Gera PDF (2ª via)** |

`bank_slip_id` = `nsuCode.nsuDate.environment.covenantCode.bankNumber` (ex: `123.2022-12-12.P.1234567.123`)
`bill_id` = `<BankNumber>.<BeneficiaryCode>` (ex: `9999999999999.999999999`) ou a linha digitável

---

## 2. Autenticação (OAuth2 + mTLS)

**Toda chamada Santander exige DOIS mecanismos combinados:**

1. **mTLS** com certificado A1 e-CNPJ (ICP-Brasil) — obrigatório inclusive na chamada OAuth
2. **Bearer JWT** obtido via OAuth2 client_credentials

### 2.1 Obter token

```http
POST /auth/oauth/v2/token
Content-Type: application/x-www-form-urlencoded

client_id=<CLIENT_ID>&client_secret=<CLIENT_SECRET>&grant_type=client_credentials
```

Response (`HTTP 200`):
```json
{
  "access_token": "eyJraWQi...JWT completo...",
  "expires_in": 900,
  "token_type": "bearer",
  "not-before-policy": 1614173461,
  "session_state": "6ade7946-...",
  "scope": ""
}
```

- **Validade:** 900s (15min). Renovar antes de expirar.
- **Não há refresh_token** — sempre autenticação nova.
- **Sem `scope`** — não precisa passar scope no request.

### 2.2 Chamar API com token

Todas as chamadas subsequentes:
```http
POST /collection_bill_management/v2/...
Authorization: Bearer <access_token>
X-Application-Key: <client_id>
Content-Type: application/json
```

**⚠️ Header `X-Application-Key` é obrigatório** (não é o mesmo pattern do Sicoob que manda `client_id`).

### 2.3 Regras do certificado (portal Santander)

- Formato: `.PEM`, `.CER` ou `.CRT` (mas o adapter usa `.pfx` direto via cred HTTP SSL do n8n)
- Tipo: **A1** (não A3)
- Cadeia completa (root + intermediate + leaf)
- Tamanho: 2048 bits
- Validade mínima: 30 dias
- Autoridade: ICP-Brasil (Serasa, Certisign, Valid, AC Digital, etc)
- **Não aceita:** self-signed, e-CPF

---

## 3. Workspace de Cobrança

**Camada específica do Santander** — não existe no Sicoob nem no Itaú. É um "espaço" que agrupa um ou mais convênios, e é onde os boletos são registrados.

**Regra prática:** 1 workspace por convênio, criada 1x (no ambiente), e o UUID hardcoded no adapter.

### 3.1 Criar workspace

```http
POST /workspaces
Authorization: Bearer <token>
X-Application-Key: <client_id>
Content-Type: application/json

{
  "type": "BILLING",
  "covenants": [{ "code": 3567206 }],
  "description": "Workspace Soul Têxtil PE",
  "webhookURL": "https://seudominio.com.br/webhook/santander-callback",
  "bankSlipBillingWebhookActive": true,
  "pixBillingWebhookActive": true
}
```

Response (`HTTP 201`):
```json
{
  "id": "92446ad6-d52a-4141-bee4-58a019358faa",
  "type": "BILLING",
  "status": "ACTIVE",
  "covenants": [{ "code": "3567206" }],
  "webhookURL": "https://...",
  "bankSlipBillingWebhookActive": true,
  "pixBillingWebhookActive": true
}
```

**Guardar o `id`** — é o `workspace_id` usado em todos os POSTs de boleto.

### 3.2 Regras da workspace
- `type` só aceita `"BILLING"`
- `covenants.code` é **integer** (não string), max 9 dígitos
- `webhookURL` opcional — se informar, cadastra a URL de callback pro banco notificar liquidação
- `bankSlipBillingWebhookActive` / `pixBillingWebhookActive` habilitam webhook por canal de pagamento

---

## 4. Emissão de Boleto

### 4.1 Payload

```http
POST /workspaces/{workspace_id}/bank_slips
Authorization: Bearer <token>
X-Application-Key: <client_id>
Content-Type: application/json

{
  "environment": "TESTE",
  "nsuCode": "TST00000000000000001",
  "nsuDate": "2026-08-25",
  "covenantCode": "0028697",
  "bankNumber": "1",
  "clientNumber": "SOULTEST001",
  "dueDate": "2026-09-25",
  "issueDate": "2026-08-25",
  "nominalValue": "100.00",
  "documentKind": "DUPLICATA_MERCANTIL",
  "paymentType": "REGISTRO",
  "writeOffQuantityDays": "30",
  "finePercentage": "2.00",
  "interestPercentage": "2.50",
  "payer": {
    "name": "Cliente Teste Sandbox",
    "documentType": "CPF",
    "documentNumber": "94620639079",
    "address": "Rua Teste, 100",
    "neighborhood": "Centro",
    "city": "Gaspar",
    "state": "SC",
    "zipCode": "89111-000"
  },
  "messages": [
    "Teste automacao Soul",
    "Emissao via API Santander"
  ]
}
```

### 4.2 Campos obrigatórios

| Campo | Tipo | Pattern / Regra |
|---|---|---|
| `environment` | enum | `TESTE` ou `PRODUCAO` |
| `nsuCode` | string | `^[A-Za-z0-9]{1,20}$` — **único por dia** por convênio. Sugestão: prefix `TST` (sandbox) / `PRD` (prod) + timestamp ms + índice |
| `nsuDate` | date | `YYYY-MM-DD` |
| `covenantCode` | string | `^[0-9]{1,9}$` — código do convênio |
| `bankNumber` | string | `^[0-9]{1,13}$` — Nosso Número (livre — gerado pela Soul) |
| `dueDate` | date | `YYYY-MM-DD` — vencimento |
| `issueDate` | date | `YYYY-MM-DD` — emissão |
| `nominalValue` | string | `^[0-9]{1,13}\.[0-9]{2}$` — valor com ponto (ex: `"100.00"`) |
| `documentKind` | enum | `DUPLICATA_MERCANTIL` (comum), `DUPLICATA_SERVICO`, `NOTA_PROMISSORIA`, `RECIBO`, `OUTROS`, etc |
| `paymentType` | enum | `REGISTRO` (comum), `DIVERGENTE`, `PARCIAL` |
| `payer.name` | string | max 40 chars |
| `payer.documentType` | enum | `CPF` ou `CNPJ` |
| `payer.documentNumber` | string | só dígitos |
| `payer.address` | string | max 40 chars |
| `payer.neighborhood` | string | max 30 chars |
| `payer.city` | string | max 20 chars |
| `payer.state` | enum | 2 letras UF (SC, SP, PE, RJ, MG, etc — 27 estados aceitos) |
| `payer.zipCode` | string | `^[0-9]{5}-[0-9]{3}$` — **CEP com hífen** |

### 4.3 Campos opcionais úteis

| Campo | Tipo | Descrição |
|---|---|---|
| `clientNumber` | string | max 15 chars — Seu Número (ex: número do pedido) |
| `participantCode` | string | max 25 chars — controle interno |
| `finePercentage` | string | `^[0-9]{1,3}\.[0-9]{2}$` — % multa (ex: `"2.00"`) |
| `fineQuantityDays` | string | dias após vencimento pra multa incidir |
| `interestPercentage` | string | % juros ao mês |
| `deductionValue` | string | valor abatimento |
| `discount` | object | `type: VALOR_DATA_FIXA / VALOR_DIA_CORRIDO / VALOR_DIA_UTIL / ISENTO` + até 3 descontos |
| `protestType` | enum | `SEM_PROTESTO`, `DIAS_CORRIDOS`, `DIAS_UTEIS`, `CADASTRO_CONVENIO` |
| `protestQuantityDays` | string | dias pra protestar (0-99) |
| `writeOffQuantityDays` | string | dias pra baixa automática (0-90) |
| `messages` | array | até 4 strings, max 100 chars cada — mensagens de instrução no boleto |
| `key` | object | Chave PIX (`type: CPF / CNPJ / CELULAR / EMAIL / EVP` + `dictKey`) |
| `txId` | string | 26-35 chars — identificador Bolepix |

### 4.4 Response

```json
{
  "environment": "TESTE",
  "nsuCode": "TST00000000000000001",
  "nsuDate": "2026-08-25",
  "covenantCode": "0028697",
  "bankNumber": "1",
  "clientNumber": "SOULTEST001",
  "dueDate": "2026-09-25",
  "issueDate": "2026-08-25",
  "nominalValue": "100.00",
  "payer": { ... },
  "documentKind": "DUPLICATA_MERCANTIL",
  "paymentType": "REGISTRO",
  "barcode": "03396939700000001009356720600000000123450101",
  "digitableLine": "03399356782060000000201234501011693970000000100",
  "entryDate": "2023-09-09",
  "qrCodePix": "00020101021226920014br.gov.bcb.pix2570pix.santander.com.br/qr/v2/cobv/9fa03dbd-...",
  "qrCodeUrl": "pix.santander.com.br/qr/v2/cobv/9fa03dbd-0b9c-4910-8ab3-14f6bf48a246"
}
```

**Campos-chave no retorno** (usar no log/dashboard):
- `barcode` — código de barras (44 dígitos)
- `digitableLine` — linha digitável (47 dígitos formatados)
- `qrCodePix` — payload PIX (BR Code)
- `qrCodeUrl` — URL curta do QR
- `entryDate` — data de entrada no banco

**⚠️ Não retorna PDF.** Pra ter o PDF, usar endpoint separado `/bills/{bill_id}/bank_slips` (ver seção 6).

---

## 5. Consulta e instruções

### 5.1 Consulta SONDA (após registro)

```http
GET /workspaces/{workspace_id}/bank_slips/{bank_slip_id}
```

Onde `bank_slip_id = "{nsuCode}.{nsuDate}.{environment_letter}.{covenantCode}.{bankNumber}"`
- `environment_letter` = `T` (teste) ou `P` (prod)
- Exemplo: `TST00000000000000001.2026-08-25.T.0028697.1`

Disponível em até D+2 do registro.

### 5.2 Lista paginada (só LIQUIDADOS)

```http
GET /workspaces/{workspace_id}/bank_slips?status=LIQUIDADO&paymentDateInitial=2026-08-01&paymentDateFinal=2026-08-31&limit=50&offset=0
```

**⚠️ Atenção:** hoje só o status `LIQUIDADO` funciona nessa consulta. Outros status (`ATIVO`, `BAIXADO`, `LIQUIDADO PARCIALMENTE`) — usar SONDA individual.

### 5.3 Instruções (PATCH)

Uma única rota `PATCH /workspaces/{workspace_id}/bank_slips` cobre **alterar / baixar / protestar** (até 10 instruções por request).

**Alterar vencimento:**
```json
{
  "covenantCode": "0028697",
  "bankNumber": "1",
  "dueDate": "2026-10-15"
}
```

**Baixar:**
```json
{
  "covenantCode": "0028697",
  "bankNumber": "1",
  "operation": "BAIXAR"
}
```

**Protestar / cancelar protesto:**
```json
{
  "covenantCode": "0028697",
  "bankNumber": "1",
  "operation": "PROTESTAR"   // ou "CANCELAR_PROTESTO"
}
```

**Alterar min/max (BOLETO_DIVERGENTE):**
```json
{
  "covenantCode": "0028697",
  "bankNumber": "1",
  "valueType": "VALOR",
  "minValueOrPercentage": "10.00",
  "maxValueOrPercentage": "20.00"
}
```

---

## 6. Geração de PDF

Após emitir, pra baixar o PDF do boleto:

```http
POST /bills/{bill_id}/bank_slips
Authorization: Bearer <token>
X-Application-Key: <client_id>
Content-Type: application/json

{
  "payerDocumentNumber": 94620639079
}
```

Onde `bill_id = "{bankNumber}.{beneficiaryCode}"` (ex: `1.0028697`).

Response (`HTTP 200`):
```json
{ "link": "https://..." }
```

Devolve **link (URL)**, não binário. Baixar o PDF do link.

---

## 7. Códigos de erro

Padrão de resposta de erro:
```json
{
  "_errorCode": 422,
  "_message": "Validação falhou",
  "_details": "campo bankNumber inválido: excede 13 dígitos",
  "_timestamp": "2026-08-25T18:04:32.867Z",
  "_traceId": "f44288eb-beea-46e0-933a-121d9646bc8f",
  "_errors": [
    {
      "_code": 40100,
      "_field": "bankNumber",
      "_message": "excede tamanho máximo"
    }
  ]
}
```

| HTTP | Significado prático |
|---|---|
| 400 | Bad Request — payload malformado (JSON inválido, campo faltando) |
| 401 | Unauthorized — token vencido, ausente, ou mTLS não fechou. **Renovar token.** |
| 403 | Forbidden — client_id sem permissão pra API. **Verificar app no portal.** |
| 404 | Not Found — workspace_id / bank_slip_id / bill_id inexistente |
| 406 | Not Acceptable — Content-Type errado |
| 409 | Conflict — recurso já existe (ex: workspace com convênio já cadastrado) |
| 410 | Gone — recurso deletado |
| 415 | Unsupported Media Type — Content-Type diferente de application/json |
| 422 | Unprocessable Entity — validação de campo falhou. Ler `_errors[]` |
| 429 | Too Many Requests — rate limit. Backoff exponencial |
| 500 | Internal Server Error — banco tá com problema. Retry depois |
| 501 | Not Implemented — endpoint não disponível ainda |

Sempre logar `_traceId` — é o ID que o Santander pede pra abrir chamado.

---

## 8. Mapping ERP Soul → API Santander

Campos vindos das parcelas do ERP Soul (Sankhya) e como mapear pro payload de emissão:

| Campo parcela ERP | Campo Santander | Transformação |
|---|---|---|
| `filial` | (contexto) | usado só pra log — Santander não recebe |
| `codcliente` | (contexto) | usado só pra log |
| `documento` | `clientNumber` (parcial) + `bankNumber` (parcial) | `clientNumber` = `"{documento}-{parcela}"` (max 15). `bankNumber` = `digitsOnly({documento}{parcelaNum:03})` (max 13) |
| `parcela` | (contexto + clientNumber) | número extraído com regex `^\d+` |
| `valor` | `nominalValue` | `Number(valor).toFixed(2)` — formato `"100.00"` |
| `datavencimento` | `dueDate` | `YYYY-MM-DD` (10 chars) |
| `dataemissao` | `issueDate` | `YYYY-MM-DD` (default: hoje) |
| `cliente` | `payer.name` | slice(0, 40) |
| `cnpjcpf` | `payer.documentNumber` + `payer.documentType` | `digitsOnly()` — 14 dígitos → CNPJ, 11 → CPF |
| `enderecocobranca` / `endereco` | `payer.address` | firstNonEmpty + slice(0, 40) |
| `bairrocobranca` / `bairro` | `payer.neighborhood` | firstNonEmpty + slice(0, 30) |
| `cidadecobranca` / `cidade` | `payer.city` | firstNonEmpty + slice(0, 20) |
| `estado` / `estadocobranca` | `payer.state` | UF 2 letras UPPER, default `SC` |
| `cep` / `cepcobranca` | `payer.zipCode` | 8 dígitos → `XXXXX-XXX` |

**Config hardcoded (não vem da parcela):**
- `covenantCode` = `"0028697"`
- `environment` = `"TESTE"` (sandbox) ou `"PRODUCAO"` (prod)
- `documentKind` = `"DUPLICATA_MERCANTIL"`
- `paymentType` = `"REGISTRO"`
- `writeOffQuantityDays` = `"30"`
- `finePercentage` = `"2.00"`
- `interestPercentage` = `"2.50"`

**Gerado dinamicamente:**
- `nsuCode` = `prefix + Date.now() + itemIndex.padStart(3, "0")` — prefix `TST` (sandbox) / `PRD` (prod)
- `nsuDate` = hoje
- `messages` = array de 3 strings com identificação do pedido/parcela

---

## 9. Diferenças vs Sicoob / Itaú

| Aspecto | Sicoob | Itaú | Santander |
|---|---|---|---|
| OAuth endpoint | `auth.sicoob.com.br/auth/realms/cooperado/protocol/openid-connect/token` | `sandbox.devportal.itau.com.br/api/oauth/jwt` (sandbox) | `trust-{env}.api.santander.com.br/auth/oauth/v2/token` |
| Escopo OAuth | `boletos_inclusao boletos_consulta` | sem scope | sem scope |
| mTLS obrigatório | Sim (todas as chamadas) | Não (hoje sandbox-only) | **Sim (inclusive OAuth)** |
| Header identificação | `client_id: <uuid>` | `x-itau-apikey` + `x-itau-correlationID` | **`X-Application-Key: <client_id>`** |
| Camada de "workspace" | não existe | não existe | **existe — criar 1x antes de emitir** |
| Endpoint emissão | `/boletos` | `/boletos` | **`/workspaces/{id}/bank_slips`** |
| Response emissão traz PDF | Opcional (`gerarPdf: true`) | Não | **Não** — endpoint separado `POST /bills/{id}/bank_slips` |
| Response traz linha digitável | Sim | Sim | Sim — **junto com QR PIX** no mesmo POST |
| ID único da chamada | `numeroCliente` + `nossoNumero` | `id_boleto_itau` | **`nsuCode` (único por dia) + `bank_slip_id` composto** |
| Rota CRUD (consultar/alterar/baixar/2ª via) | Endpoints separados | Endpoints separados | **PATCH único** cobre alterar/baixar/protestar + endpoints separados pra consulta e PDF |

---

## 10. Testes reais executados

Durante a integração (25/08/2026), foram executados os 3 curl abaixo — todos com `HTTP 200/201`:

### 10.1 Obter token (sandbox)

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "https://trust-sandbox.api.santander.com.br/auth/oauth/v2/token" \
  --cert-type P12 \
  --cert "$HOME/Downloads/<CAMINHO_PFX_ECNPJ>:<SENHA_PFX>" \
  -d "client_id=<SANDBOX_CLIENT_ID>" \
  -d "client_secret=<sandbox_secret>" \
  -d "grant_type=client_credentials"
```
Resultado: `HTTP 200` — token JWT válido por 900s, `iss: "Santander JWT Authority Sandbox"`, `x5t#S256` = fingerprint SHA256 do cert Gaspar SC.

### 10.2 Criar workspace (sandbox)

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "https://trust-sandbox.api.santander.com.br/collection_bill_management/v2/workspaces" \
  --cert-type P12 \
  --cert "$HOME/Downloads/<CAMINHO_PFX_ECNPJ>:<SENHA_PFX>" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Application-Key: <SANDBOX_CLIENT_ID>" \
  -H "Content-Type: application/json" \
  -d '{"type":"BILLING","covenants":[{"code":3567206}],"description":"Teste Soul Sandbox","bankSlipBillingWebhookActive":true,"pixBillingWebhookActive":true,"webhookURL":"https://teste"}'
```
Resultado: `HTTP 201` — workspace criada, `id: <SANDBOX_WORKSPACE_UUID>`.

### 10.3 Emitir boleto R$ 100 (sandbox)

```bash
curl -sS -w "\nHTTP %{http_code}\n" \
  -X POST "https://trust-sandbox.api.santander.com.br/collection_bill_management/v2/workspaces/<SANDBOX_WORKSPACE_UUID>/bank_slips" \
  --cert-type P12 \
  --cert "$HOME/Downloads/<CAMINHO_PFX_ECNPJ>:<SENHA_PFX>" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Application-Key: <SANDBOX_CLIENT_ID>" \
  -H "Content-Type: application/json" \
  -d '{"environment":"TESTE","nsuCode":"TST00000000000000001","nsuDate":"2026-08-25","covenantCode":"3567206","bankNumber":"1","clientNumber":"SOULTEST001","dueDate":"2026-09-25","issueDate":"2026-08-25","nominalValue":"100.00","payer":{"name":"Cliente Teste Sandbox","documentType":"CPF","documentNumber":"94620639079","address":"Rua Teste, 100","neighborhood":"Centro","city":"Gaspar","state":"SC","zipCode":"89111-000"},"documentKind":"DUPLICATA_MERCANTIL","paymentType":"REGISTRO","writeOffQuantityDays":"30","messages":["Teste automacao Soul","Emissao via API Santander"]}'
```
Resultado: `HTTP 201` — boleto emitido:
- `barcode`: `03396939700000001009356720600000000123450101`
- `digitableLine`: `03399356782060000000201234501011693970000000100`
- `qrCodePix`: `00020101021226920014br.gov.bcb.pix2570pix.santander.com.br/qr/v2/cobv/9fa03dbd-...`
- `qrCodeUrl`: `pix.santander.com.br/qr/v2/cobv/9fa03dbd-0b9c-4910-8ab3-14f6bf48a246`

**Ciclo completo OAuth → workspace → boleto validado ponta a ponta.**
