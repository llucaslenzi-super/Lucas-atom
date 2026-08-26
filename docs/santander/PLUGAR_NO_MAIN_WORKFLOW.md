# O que foi plugado no `Agente Boletos Soul` — Santander Gaspar

> Registro exato das alterações feitas no main workflow (`PKhlEnAj93IA9Mwv`) via MCP n8n. Nada de Sicoob/Itaú foi tocado — só adições.

---

## Estado antes (Sicoob PE/SP + Itaú Gaspar/PE)

Main workflow tinha 103 nodes, com 4 adapters plugados:
- Sub Adapter Sicoob PE (`2dCcttn2Fw1G61wk`)
- Sub Adapter Sicoob SP (`e75B9Q7Crrhiv6wu`)
- Sub Adapter Itaú Gaspar (`OL2Ges8VsJqlHxfz`)
- Sub Adapter Itaú PE (`3AC66gqhhM2PM4xe`)

Switch por bancoConta (do `/emitir`) tinha 4 outputs + fallback "outros".

Endpoints CRUD (`/consultar`, `/alterar`, `/baixar`, `/segunda-via`) só tinham chains pra Sicoob PE/SP (Itaú não tem CRUD ainda).

---

## Alterações aplicadas

### 1. Novo adapter workflow

Workflow criado do zero via MCP:
- **ID:** `cxjhU46JBfCnKM12`
- **Nome:** `Adapter Santander Gaspar`
- **URL:** https://soultextil.app.n8n.cloud/workflow/cxjhU46JBfCnKM12
- **8 nodes** (mesmo esqueleto do Sicoob PE, adaptações Santander — ver `ADAPTER_SANTANDER_GASPAR.md`)

### 2. Switch por bancoConta atualizado

Antes: 4 outputs (sicoob_pe, sicoob_sp, itau_gaspar, itau_pe)
Depois: **5 outputs** (+ santander_gaspar)

Regra adicionada (output 4):
```javascript
{
  outputKey: 'santander_gaspar',
  renameOutput: true,
  conditions: {
    combinator: 'and',
    conditions: [
      { leftValue: '{{ $json.bancoConta }}', operator: { operation: 'equals', type: 'string' }, rightValue: 'santander_gaspar' }
    ],
    options: { caseSensitive: true, leftValue: '', typeValidation: 'strict' }
  }
}
```

### 3. Novos nodes no main

| Node | Type | Position | Aponta pra |
|---|---|---|---|
| `Sub Adapter Santander Gaspar` | executeWorkflow v1.2 | `[1020, 1950]` | workflow `cxjhU46JBfCnKM12` |
| `Adapt Santander Gaspar Output` | code v2 (runOnceForEachItem) | `[1280, 1950]` | — |

### 4. Conexões novas

```
Switch por bancoConta (output 4: santander_gaspar)
    │
    ▼
Sub Adapter Santander Gaspar
    │
    ▼
Adapt Santander Gaspar Output
    │
    ▼
Prep Log Row
```

### 5. `Prep Log Row` atualizado

Adicionado branch novo pra reconhecer banco Santander:

```javascript
// antes:
if (banco === 'itau') {
  contaExibir = String((cfg && cfg.id_beneficiario) || '');
} else {
  contaExibir = String((cfg && cfg.numeroContaCorrente) || '');
}

// depois:
if (banco === 'itau') {
  contaExibir = String((cfg && cfg.id_beneficiario) || '');
} else if (banco === 'santander') {
  contaExibir = String((cfg && cfg.convenio) || '');
} else {
  contaExibir = String((cfg && cfg.numeroContaCorrente) || '');
}
```

Nenhum outro campo do log mudou. `banco_response_json` continua absorvendo o payload bruto de qualquer banco (incluindo `qr_pix` e `qr_url` do Santander, dentro do JSON).

### 6. Dashboard (`HTML Part 2`) atualizado

Adicionado novo optgroup no `<select id="banco-sel">`:

```html
<optgroup label="Sicoob">
  <option value="sicoob_pe">Sicoob PE</option>
  <option value="sicoob_sp">Sicoob SP</option>
</optgroup>
<optgroup label="Itaú (sandbox)">
  <option value="itau_gaspar">Itaú Gaspar SC</option>
  <option value="itau_pe">Itaú PE</option>
</optgroup>
<!-- NOVO -->
<optgroup label="Santander (sandbox)">
  <option value="santander_gaspar">Santander Gaspar SC</option>
</optgroup>
```

---

## Estado depois

Main workflow: **117 nodes** (era 103, +2 novos + 12 sub-nodes auto contados)

Adapters plugados via executeWorkflow:
1. Sicoob PE
2. Sicoob SP
3. Itaú Gaspar
4. Itaú PE
5. **Santander Gaspar** ← novo

Endpoints CRUD ainda só cobrem Sicoob PE/SP. Santander CRUD fica pra próxima fase (ver seção "Endpoints CRUD" em `ADAPTER_SANTANDER_GASPAR.md`).

---

## Como reverter (rollback)

Se der problema com Santander e quiser reverter:

1. **Remover option do dashboard:** editar `HTML Part 2`, remover as 3 linhas do `<optgroup label="Santander (sandbox)">`. Usuário deixa de ver Santander no dropdown → nenhum boleto novo emitido pra ele.

2. **(Opcional) Desligar Switch output:** editar Switch por bancoConta, remover a 5ª regra `santander_gaspar`. Requests com `bancoConta: santander_gaspar` caem no fallback "outros" (que retorna erro genérico).

3. **(Opcional) Deletar nodes:** remover `Sub Adapter Santander Gaspar` + `Adapt Santander Gaspar Output` + conexões relacionadas. Adapter fica órfão mas continua no n8n.

4. **(Opcional) Arquivar workflow adapter:** archive `cxjhU46JBfCnKM12` (não deleta, só desativa).

**Sicoob e Itaú continuam funcionando** — as alterações são aditivas, não modificam nenhum branch existente.

---

## Sub Adapter Santander Gaspar — config completo (JSON)

```json
{
  "name": "Sub Adapter Santander Gaspar",
  "type": "n8n-nodes-base.executeWorkflow",
  "typeVersion": 1.2,
  "position": [1020, 1950],
  "parameters": {
    "mode": "once",
    "options": { "waitForSubWorkflow": true },
    "source": "database",
    "workflowId": {
      "__rl": true,
      "cachedResultName": "Adapter Santander Gaspar",
      "mode": "id",
      "value": "cxjhU46JBfCnKM12"
    },
    "workflowInputs": {
      "attemptToConvertTypes": false,
      "convertFieldsToString": true,
      "mappingMode": "defineBelow",
      "matchingColumns": [],
      "schema": [
        { "id": "env", "displayName": "env", "type": "string", "required": false, "display": true, "canBeUsedToMatch": true, "defaultMatch": false },
        { "id": "parcelas", "displayName": "parcelas", "type": "array", "required": false, "display": true, "canBeUsedToMatch": true, "defaultMatch": false },
        { "id": "emitido_por", "displayName": "emitido_por", "type": "string", "required": false, "display": true, "canBeUsedToMatch": true, "defaultMatch": false }
      ],
      "value": {
        "env": "={{ $json.env }}",
        "parcelas": "={{ $json.parcelas }}",
        "emitido_por": "={{ $json.emitido_por }}"
      }
    }
  }
}
```

## Adapt Santander Gaspar Output — jsCode

```javascript
const j = $input.item.json;
const ok = j.santander_ok === true;
const resp = j.santander_response || {};
const resultado = ok ? { nossoNumero: j.nossonumero || '', codigoBarras: j.codbarras || '', linhaDigitavel: j.linhadigitavel || '', pdfBoleto: '' } : null;
const mensagens = ok ? null : [{ codigo: String(j.santander_status || 'ERR'), mensagem: (JSON.stringify(resp) || '').slice(0, 500) }];
const ctx = { chave_unica: j.chave_unica, parcela: j.parcela, config: j.config, base_url: j.base_url, api_client_id: j.client_id, env: j.env, emitido_por: j.emitido_por, bancoConta: 'santander_gaspar', workspace_id: j.workspace_id, qr_pix: j.qr_pix, qr_url: j.qr_url, entry_date_ret: j.entry_date_ret, banco_response_full: j.santander_response };
return { json: Object.assign({}, { resultado: resultado, mensagens: mensagens, santander_status: j.santander_status, santander_ok: ok }, { __adapter_ctx: ctx }) };
```
