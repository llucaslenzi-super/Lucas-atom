# Adapter Santander Gaspar — Especificação

> Adapter n8n pluggado no agente multibanco de boletos da Soul Têxtil, seguindo o pattern estabelecido pelos adapters Sicoob PE/SP e Itaú Gaspar/PE.

**Workflow n8n:** `cxjhU46JBfCnKM12` — `Adapter Santander Gaspar`
URL: https://soultextil.app.n8n.cloud/workflow/cxjhU46JBfCnKM12

---

## Contrato (Execute Sub-Workflow)

O adapter é invocado do main workflow `Agente Boletos Soul` (`PKhlEnAj93IA9Mwv`) via `Sub Adapter Santander Gaspar` (executeWorkflow node).

### Input (do main pro adapter)
```json
{
  "env": "sandbox" | "prod",
  "parcelas": [
    { "filial": "...", "codcliente": ..., "documento": "...", "parcela": "...", "valor": ..., "datavencimento": "YYYY-MM-DD", "cliente": "...", "cnpjcpf": "...", "endereco": "...", "bairro": "...", "cidade": "...", "estado": "...", "cep": "..." },
    ...
  ],
  "emitido_por": "dashboard"
}
```

### Output (do adapter pro main, 1 item por parcela)
```json
{
  "chave_unica": "filial|codcliente|documento|parcela",
  "parcela": { ... },
  "config": { ...CFG_SANTANDER_GASPAR },
  "boleto_sent": { ...payload enviado },
  "santander_response": { ...raw JSON do banco },
  "santander_status": 201,
  "santander_ok": true,
  "nossonumero": "1",
  "linhadigitavel": "03399356782060...",
  "codbarras": "03396939700000...",
  "qr_pix": "00020101021226...",
  "qr_url": "pix.santander.com.br/qr/v2/cobv/...",
  "entry_date_ret": "2026-08-25",
  "base_url": "https://trust-sandbox...",
  "client_id": "<SANDBOX_CLIENT_ID>",
  "workspace_id": "<SANDBOX_WORKSPACE_UUID>",
  "env": "sandbox",
  "emitido_por": "dashboard"
}
```

O node `Adapt Santander Gaspar Output` no main normaliza esse output pro formato padrão que o `Prep Log Row` espera:
```json
{
  "resultado": { "nossoNumero": "...", "codigoBarras": "...", "linhaDigitavel": "...", "pdfBoleto": "" },
  "mensagens": null | [{ "codigo": "...", "mensagem": "..." }],
  "santander_status": 201,
  "santander_ok": true,
  "__adapter_ctx": {
    "chave_unica": "...",
    "parcela": {...},
    "config": {...},
    "base_url": "...",
    "api_client_id": "...",
    "workspace_id": "...",
    "qr_pix": "...",
    "qr_url": "...",
    "entry_date_ret": "...",
    "banco_response_full": {...},
    "env": "sandbox",
    "emitido_por": "dashboard",
    "bancoConta": "santander_gaspar"
  }
}
```

---

## Config hardcoded

`CFG_SANTANDER_GASPAR` (dentro do node `Fan Out Parcelas Santander`):

```javascript
const CFG_SANTANDER_GASPAR = {
  filial: 'Gaspar (SC)',
  bancoConta: 'santander_gaspar',
  convenio: '0028697',
  cnpj_beneficiario: '35588873000222',
  nome_cobranca: 'SOUL INDUSTRIA DE TECIDOS LTDA',
  document_kind: 'DUPLICATA_MERCANTIL',
  payment_type: 'REGISTRO',
  fine_percentage: '2.00',
  interest_percentage: '2.50',
  write_off_days: '30'
};
```

`ENV_MAP`:

```javascript
const ENV_MAP = {
  sandbox: {
    base_url: 'https://trust-sandbox.api.santander.com.br/collection_bill_management/v2',
    client_id: '<SANDBOX_CLIENT_ID>',
    workspace_id: '<SANDBOX_WORKSPACE_UUID>'
  },
  prod: {
    base_url: 'https://trust-open.api.santander.com.br/collection_bill_management/v2',
    client_id: '__SANTANDER_GASPAR_PROD_CLIENT_ID__',
    workspace_id: '__SANTANDER_GASPAR_PROD_WORKSPACE_ID__'
  }
};
```

**Placeholders `__SANTANDER_GASPAR_PROD_*__`** ficam pendentes até:
1. Criar app produção no portal Santander → substitui `__SANTANDER_GASPAR_PROD_CLIENT_ID__` + secret nos body params do `Prod Token Santander`
2. Criar workspace prod via curl → substitui `__SANTANDER_GASPAR_PROD_WORKSPACE_ID__`

---

## Estrutura (8 nodes)

Mesmo esqueleto do Adapter Sicoob PE, com adaptações Santander:

```
Adapter Trigger
    │
    ▼
Env Check Santander (IF env === 'sandbox')
    ├── true  ──▶ Sandbox Token Santander ──┐
    └── false ──▶ Prod Token Santander ─────┤
                                            ▼
                                Fan Out Parcelas Santander
                                            │
                                            ▼ (1 item por parcela)
                                Montar Body Boleto Santander
                                            │
                                            ▼
                                Santander POST Boleto
                                            │
                                            ▼
                                Format Adapter Output Santander
                                            │
                                            ▼ (retorna pro main)
```

### Nodes detalhados

#### 1. `Adapter Trigger` (executeWorkflowTrigger v1.2)
Contrato fixo: `{env, parcelas, emitido_por}` (schema declarado).

#### 2. `Env Check Santander` (IF v2.3)
`$json.env === 'sandbox'` → branch true. Fallback (prod) → branch false.

#### 3. `Sandbox Token Santander` (httpRequest v4.5)
```
POST https://trust-sandbox.api.santander.com.br/auth/oauth/v2/token
Content-Type: application/x-www-form-urlencoded
Body (form):
  grant_type=client_credentials
  client_id=<SANDBOX_CLIENT_ID>
  client_secret=<sandbox_secret>
Credential: santander_gaspar_mtls (HTTP SSL)
provideSslCertificates: true
timeout: 30000ms
```

#### 4. `Prod Token Santander` (httpRequest v4.5)
Idêntico ao sandbox, trocando URL pra `trust-open` e client_id/secret pra `__SANTANDER_GASPAR_PROD_CLIENT_ID__` / `__SANTANDER_GASPAR_PROD_CLIENT_SECRET__`.

#### 5. `Fan Out Parcelas Santander` (Code v2, runOnceForAllItems)
Mescla `Adapter Trigger` + tokenResp e explode 1 item por parcela, injetando CFG + envCfg + access_token.

#### 6. `Montar Body Boleto Santander` (Code v2, runOnceForEachItem)
Monta o payload no schema Santander a partir da `parcela` (ver `API_BOLETOS_SANTANDER.md` seção 8 pro mapping ERP→API):
- `nsuCode` gerado como `prefix + Date.now() + itemIndex.padStart(3, "0")`
- `bankNumber` = `digitsOnly({documento}{parcelaNum:03})` (max 13)
- `clientNumber` = `"{documento}-{parcelaNum}"` (max 15)
- `payer.zipCode` normalizado pra formato `XXXXX-XXX`
- `payer.state` UPPER, default `SC`
- `payer.documentType` inferido do tamanho: 14 dígitos → CNPJ, 11 → CPF
- Fallbacks pra endereço/bairro/cidade: `enderecocobranca > endereco > 'NAO INFORMADO'`

#### 7. `Santander POST Boleto` (httpRequest v4.5)
```
POST {{ $json.base_url }}/workspaces/{{ $json.workspace_id }}/bank_slips
Headers:
  Authorization: Bearer {{ $json.access_token }}
  X-Application-Key: {{ $json.client_id }}
  Content-Type: application/json
  Accept: application/json
Body (raw JSON): {{ JSON.stringify($json.boleto) }}
Credential: santander_gaspar_mtls (HTTP SSL)
provideSslCertificates: true
fullResponse: true
neverError: true
responseFormat: json
timeout: 60000ms
```

Flags críticas (mesmo pattern Sicoob):
- **`fullResponse: true`** — retorna statusCode + body
- **`neverError: true`** — HTTP 4xx/5xx não bloqueia execução, deixa o Format Output tratar

#### 8. `Format Adapter Output Santander` (Code v2, runOnceForEachItem)
Parseia response e devolve o formato padronizado. Trata:
- Body como buffer (raro no Santander mas possível — pattern Sicoob preserva)
- Erro parse → grava `parse_error` no lugar
- `santander_ok = statusCode >= 200 && statusCode < 300`
- Extrai campos-chave: `bankNumber`, `barcode`, `digitableLine`, `qrCodePix`, `qrCodeUrl`, `entryDate`

---

## Credencial mTLS

**Nome exato:** `santander_gaspar_mtls`
**Tipo n8n:** HTTP SSL Auth (httpSslAuth)
**Arquivo:** e-CNPJ Soul PE (`SOUL INDUSTRIA DE TECIDOS LTDA35588873000222 (1).pfx`)
**Senha:** (na cred do n8n, não em código)
**Validade:** 18/06/2027

Usada em 3 nodes: `Sandbox Token Santander`, `Prod Token Santander`, `Santander POST Boleto`.

Enquanto o `.pfx` não estiver subido no n8n como cred `santander_gaspar_mtls`, os 3 HTTP nodes têm `newCredential('santander_gaspar_mtls')` reservado (aparecerão com aviso "credential missing").

---

## Peculiaridades do Santander (vs Sicoob)

Documentadas pra facilitar debug e futuras expansões:

1. **Workspace obrigatória** — não emite direto no convênio; precisa ter o UUID da workspace na URL. Sicoob não tem essa camada. Sandbox: `<SANDBOX_WORKSPACE_UUID>` (guardado no config do adapter). Prod: pendente.

2. **`X-Application-Key` em vez de `client_id`** — header de identificação usa nome diferente do Sicoob (`client_id`).

3. **`nsuCode` único por dia** — gerado dinamicamente com timestamp ms + índice. Reutilizar mesmo `nsuCode` no mesmo dia dá erro 409.

4. **CEP com hífen** — pattern `^[0-9]{5}-[0-9]{3}$` exige o hífen. Sicoob aceita só dígitos.

5. **Response da emissão traz linha digitável + QR PIX juntos** — não precisa 2ª chamada. Sicoob precisa `gerarPdf: true` pra PDF.

6. **PDF é endpoint separado** — `POST /bills/{bill_id}/bank_slips` com body `{payerDocumentNumber}` retorna `{link}`. Não implementado no adapter atual (será feito quando adicionar Segunda-Via).

7. **mTLS inclusive no OAuth** — diferente do Itaú (que hoje é sandbox-only sem cert), o Santander exige cert no request de token.

8. **Sem `scope`** — no OAuth body só vai `grant_type + client_id + client_secret`.

9. **Rate limit** — não documentado mas 429 é possível. Backoff exponencial se aparecer.

---

## Integração no main workflow

**Já plugado em `Agente Boletos Soul` (`PKhlEnAj93IA9Mwv`) via MCP n8n:**

1. **Switch por bancoConta** (do `/emitir`) — adicionado output `santander_gaspar` como 5º output
2. **Sub Adapter Santander Gaspar** (executeWorkflow, position `[1020, 1950]`) — aponta pro `cxjhU46JBfCnKM12`
3. **Adapt Santander Gaspar Output** (Code, position `[1280, 1950]`) — copia pattern Adapt Itau Gaspar Output, adaptado pra ler `santander_*`
4. **Conexões:** `Switch[4] → Sub Adapter → Adapt Output → Prep Log Row`
5. **Prep Log Row atualizado** — branch novo `if (banco === 'santander') contaExibir = cfg.convenio`
6. **HTML Part 2 (dashboard)** — novo `<optgroup label="Santander (sandbox)"><option value="santander_gaspar">Santander Gaspar SC</option></optgroup>`

**Não mexi em nenhum Sicoob / Itaú.** Alterações são aditivas.

---

## Endpoints CRUD (consultar/alterar/baixar/segunda-via)

**Não implementado ainda pro Santander** — seguindo o pattern atual (Itaú também só tem /emitir, CRUD fica pra depois).

Quando for implementar:
- **Consultar:** `GET /workspaces/{workspace_id}/bank_slips/{bank_slip_id}` (SONDA) — precisa reconstruir `bank_slip_id` a partir de `nsuCode.nsuDate.env_letter.covenantCode.bankNumber`
- **Alterar:** `PATCH /workspaces/{workspace_id}/bank_slips` com `{covenantCode, bankNumber, dueDate}` (ou outros campos)
- **Baixar:** `PATCH /workspaces/{workspace_id}/bank_slips` com `{covenantCode, bankNumber, operation: "BAIXAR"}`
- **Segunda-via:** `POST /bills/{bill_id}/bank_slips` com `{payerDocumentNumber}` — retorna `{link}` do PDF

Ver `API_BOLETOS_SANTANDER.md` seção 5 e 6 pra detalhes.

Recomendação: quando plugar CRUD do Santander, considerar o refactor `endpoints CRUD → adapter pattern` mencionado no playbook (evita duplicação de nodes inline).
