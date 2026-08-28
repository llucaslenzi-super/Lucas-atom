# Workflow Standalone Santander (sandbox)

> Workflow autocontido de emissão de boletos Santander. Não depende do main workflow multi-banco (`Agente Boletos Soul`), roda ponta a ponta sozinho via webhook público.

- **ID:** `aZkmtgneJDtbUAPk`
- **URL:** https://soultextil.app.n8n.cloud/workflow/aZkmtgneJDtbUAPk
- **Nome:** `Santander Boletos Standalone (sandbox)`
- **Nodes:** 11 (webhook → parse → if(sandbox) → token → fan-out → montar body → POST → format → aggregate → response; ramo prod → throw)
- **Endpoint:** `POST https://soultextil.app.n8n.cloud/webhook/santander/emitir`
- **Ambiente:** sandbox-only. Requests com `env=prod` são rejeitadas com `env_must_be_sandbox` (proteção anti-boleto-real hardcoded no `Parse Request`).

## Estado atual (28/08/2026)

| Item | Status |
|---|---|
| Workflow criado no n8n | ✅ |
| 11 nodes conectados corretamente | ✅ |
| Placeholders substituídos por client_id/secret reais sandbox | ✅ |
| Teste com pin data (execution `2462`) | ✅ Response `{ok_count:1, fail_count:0, nossonumero, linhadigitavel, codbarras, qr_pix, qr_url}` |
| Bloqueio de prod (execution `2463`) | ✅ Falhou com `env_must_be_sandbox` (comportamento esperado) |
| Cred `santander_gaspar_mtls` vinculada | ⚠️ pendente (nodes Sandbox Token e Santander POST Boleto ficam com aviso) |
| Workflow ativado (webhook live) | ⚠️ pendente (você precisa dar clique no toggle Active — classifier me bloqueou de ativar) |

## Contrato

### Request

```
POST https://soultextil.app.n8n.cloud/webhook/santander/emitir
Content-Type: application/json
```

Body:

```json
{
  "env": "sandbox",
  "emitido_por": "quem-esta-chamando",
  "parcelas": [
    {
      "filial": "SC",
      "codcliente": "99999",
      "cliente": "NOME COMPLETO DO CLIENTE LTDA",
      "cnpjcpf": "35588873000141",
      "documento": "AUD001",
      "parcela": "1",
      "valor": 1.00,
      "datavencimento": "2026-09-30",
      "dataemissao": "2026-08-28",
      "email": "cliente@exemplo.com",
      "celular": "47999999999",
      "endereco": "RUA X",
      "enderecocobranca": "RUA X 100",
      "bairro": "CENTRO",
      "bairrocobranca": "CENTRO",
      "cidade": "GASPAR",
      "cidadecobranca": "GASPAR",
      "estado": "SC",
      "estadocobranca": "SC",
      "cep": "89110000",
      "cepcobranca": "89110000"
    }
  ]
}
```

Campos obrigatórios: `filial, codcliente, cliente, cnpjcpf, documento, parcela, valor, datavencimento`. O resto tem fallback pra `NAO INFORMADO`/`CENTRO`/`SC`/`89110-000`.

### Response

```json
{
  "ok_count": 1,
  "fail_count": 0,
  "total": 1,
  "env": "sandbox",
  "emissoes": [
    {
      "chave_unica": "SC|99999|AUD001|1",
      "santander_ok": true,
      "santander_status": 201,
      "nossonumero": "00028697000000012345",
      "linhadigitavel": "03399.12345 67890.123456 78901.234567 8 90123456789012345",
      "codbarras": "03399123456789012345678901234567890123456789",
      "qr_pix": "00020126580014BR.GOV.BCB.PIX...",
      "qr_url": "https://sandbox.santander.com.br/qr/...",
      "erro": null
    }
  ]
}
```

Se algum boleto falhar, aparece em `emissoes[].erro` com a mensagem do Santander e `santander_ok=false`. HTTP response continua 200 (o webhook devolve sucesso agregado — inspecione `fail_count` e `emissoes[].erro`).

## Passos pra colocar de pé

**1. Vincular cred `santander_gaspar_mtls` nos 2 HTTP nodes** (n8n UI):

- Abre o workflow no editor
- Node `Sandbox Token Santander` → aba Credentials → seleciona `santander_gaspar_mtls`
- Node `Santander POST Boleto` → aba Credentials → seleciona `santander_gaspar_mtls`
- Salvar

Se a cred não existir ainda: Credentials → New → HTTP SSL Auth → upload PFX Gaspar SC + senha `123456` → nome exato `santander_gaspar_mtls`.

**2. Ativar workflow** (n8n UI):

- Toggle `Inactive → Active` no canto superior direito
- (Classifier automático bloqueou eu fazer isso via MCP — precisa clique manual)

**3. Testar com curl real:**

```bash
curl -sS -X POST "https://soultextil.app.n8n.cloud/webhook/santander/emitir" \
  -H "Content-Type: application/json" \
  -d '{
    "env":"sandbox",
    "emitido_por":"curl-test",
    "parcelas":[{
      "filial":"SC","codcliente":"99999","cliente":"TESTE SOUL LTDA",
      "cnpjcpf":"35588873000141","documento":"TST001","parcela":"1",
      "valor":1,"datavencimento":"2026-09-30","dataemissao":"2026-08-28",
      "email":"teste@soultextil.com.br","celular":"47999999999",
      "endereco":"RUA X","enderecocobranca":"RUA X 100",
      "bairro":"CENTRO","bairrocobranca":"CENTRO",
      "cidade":"GASPAR","cidadecobranca":"GASPAR",
      "estado":"SC","estadocobranca":"SC","cep":"89110000","cepcobranca":"89110000"
    }]
  }'
```

Esperado: HTTP 200 com `{"ok_count":1,"fail_count":0,...,"nossonumero":"...","linhadigitavel":"...","qr_pix":"..."}`.

## O que ele NÃO faz

- Não loga no Nekt (dashboard multi-banco faz isso via `Prep Log Row` — aqui é standalone puro)
- Não envia email/WhatsApp (mesma coisa — dashboard faz)
- Não gera PDF (endpoint separado do Santander, não implementado aqui)
- Não emite em produção (bloqueado no `Parse Request` por segurança)

Se precisar dessas features, use o dashboard multi-banco (`Agente Boletos Soul`) que já pluga o `Adapter Santander Gaspar` — este standalone é pra testes isolados/integrações externas.

## Testes rodados

**Execution `2462` (sandbox happy path):**

- Input: 1 parcela válida R$1
- Passou por: Webhook → Parse → EnvCheck(true) → Sandbox Token (mock) → Fan Out → Montar Body (payer CNPJ, CEP formatado) → POST (mock 201) → Format → Aggregate → Response
- Output: `{ok_count:1, fail_count:0, total:1, emissoes:[{nossonumero:"00028697...", linhadigitavel:"03399...", codbarras, qr_pix, qr_url}]}`

**Execution `2463` (proteção prod):**

- Input: `env: "prod"`
- Falhou logo no Parse Request com `env_must_be_sandbox [line 6]`
- Nenhuma chamada ao Santander foi feita
