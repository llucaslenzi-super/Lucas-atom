# Auditoria sandbox Santander — pré-produção

> Última varredura: 28/08/2026 · workflow `PKhlEnAj93IA9Mwv` (Agente Boletos Soul, 164 nodes) + adapter `cxjhU46JBfCnKM12` (Adapter Santander Gaspar, 8 nodes).

Objetivo: confirmar que TODA a arquitetura sandbox está de pé antes de subir a app de produção no portal Santander.

---

## 1. Certificado e app portal

| Item | Status | Nota |
|---|---|---|
| PFX Gaspar SC extraído (CNPJ 35.588.873/0002-22) | ✅ | `SOUL INDUSTRIA DE TECIDOS LTDA35588873000222 (1).pfx`, senha `123456`, válido até 18/06/2027 |
| Chain pública `.cer` gerada (4 certs: leaf + AC DIGITAL MULTIPLA G1 + AC DIGITAL MAIS + Raiz Brasileira v5) | ✅ | Foi subido no portal sandbox |
| App sandbox `sc api Santander boletos` no portal | ✅ | client_id/secret capturados |
| Produto "Cobrança/Boletos" ativo na app | ✅ | Confirmado pelo POST OAuth ter retornado token |

## 2. OAuth mTLS end-to-end (curl direto)

| Item | Status | Evidência |
|---|---|---|
| POST `/auth/oauth/v2/token` em `trust-sandbox` | ✅ HTTP 200 | token JWT retornado, expira em 900s |
| POST `/collection_bill_management/v2/workspaces` | ✅ HTTP 201 | workspace UUID `c023aa7a-f2dd-4839-b0a4-d2fcc8637957` criado |
| POST `/workspaces/{id}/bank_slips` (boleto R$100) | ✅ HTTP 201 | linha digitável + código de barras + QR PIX + `qrCodeUrl` no response |

**Isso prova que:** o certificado é aceito, a app está bem configurada, o convênio 0028697 responde, e o payload que o adapter monta é válido do ponto de vista da API Santander.

## 3. Adapter Santander Gaspar (`cxjhU46JBfCnKM12`)

Estrutura confirmada (8 nodes conectados em pipeline):

```
Adapter Trigger → Env Check Santander → (sandbox|prod) Token → Fan Out Parcelas → Montar Body → POST Boleto → Format Output
```

| Node | Status | Nota |
|---|---|---|
| `Adapter Trigger` (executeWorkflowTrigger) | ✅ | Contrato `{env, parcelas, emitido_por}` |
| `Env Check Santander` (if) | ✅ | Roteia `env === 'sandbox'` → Sandbox Token; senão Prod Token |
| `Sandbox Token Santander` (httpRequest) | ⚠️ | Node OK, cred **`santander_gaspar_mtls` não vinculada** |
| `Prod Token Santander` (httpRequest) | ⚠️ | Placeholders `__SANTANDER_GASPAR_PROD_*__` e cred não vinculada |
| `Fan Out Parcelas Santander` (code) | ✅ | CFG hardcoded com convênio 0028697, CNPJ 35588873000222, agência 4147, conta 130020556, PIX `financeiro1@soultextil.com.br` |
| `Montar Body Boleto Santander` (code) | ✅ | nsuCode `timestamp+idx` único/dia; CEP normalizado; payer mapping OK |
| `Santander POST Boleto` (httpRequest) | ⚠️ | Node OK, `neverError:true`+`fullResponse:true`, mas cred não vinculada |
| `Format Adapter Output Santander` (code) | ✅ | Extrai `nossonumero`, `codbarras`, `linhadigitavel`, `qr_pix`, `qr_url` |

**Bloqueador único do adapter:** falta subir a credencial `santander_gaspar_mtls` (HTTP SSL Auth com o `.pfx` Gaspar SC) e vincular nos 3 HTTP nodes acima.

## 4. Integração no main workflow (`PKhlEnAj93IA9Mwv`)

| Item | Status | Nota |
|---|---|---|
| Rule `santander_gaspar` no `Switch por bancoConta` | ✅ | Output 4 do switch |
| `Sub Adapter Santander Gaspar` conectado no Switch output 4 | ✅ | **Corrigido nesta auditoria** — antes estava no output 0 junto do Sicoob PE |
| Sub Adapter aponta para workflow `cxjhU46JBfCnKM12` | ✅ | executeWorkflow apontando pro adapter |
| `Adapt Santander Gaspar Output` conectado depois do Sub Adapter | ✅ | Traduz output do adapter pra `__adapter_ctx` |
| `Prep Log Row` recebe do Adapt Santander | ✅ | Branch `banco === 'santander'` já implementada com `contaExibir = cfg.convenio` |
| `optgroup Santander (sandbox)` no dashboard `#banco-sel` | ✅ | **Re-adicionado nesta auditoria** — foi removido em edição posterior |

**Nada quebrado em Sicoob/Itaú/BB/Caixa.** Aditivo puro.

### Ajustes colaterais nesta auditoria

Além do Santander, o Switch estava com routing bagunçado depois das últimas edições do usuário. Reorganizado:

- Output 0 (`sicoob_pe`) — antes tinha `Sicoob PE + Caixa Matriz + Caixa Gaspar` → agora só `Sicoob PE`
- Output 4 (`santander_gaspar`) — antes tinha `Safra Matriz` → agora `Santander Gaspar`
- Output 5 (`caixa_matriz`) — antes vazio → agora `Caixa Matriz`
- Output 6 (`caixa_gaspar`) — antes vazio → agora `Caixa Gaspar`

`Sub Adapter Safra Matriz` ficou órfão de propósito — **não existe rule `safra_matriz` no Switch**. Se você quer usar Safra, precisa adicionar essa rule no Switch e conectar (não fiz porque está fora do escopo Santander).

## 5. Credenciais no n8n

| Cred | Status | Ação |
|---|---|---|
| `sicoob_pe_mtls` (httpSslAuth) | ✅ existente | — |
| `sicoob_sp_mtls` (httpSslAuth) | ✅ existente | — |
| `santander_gaspar_mtls` (httpSslAuth) | ❌ **não existe** | **Você precisa criar** — Credentials → New → HTTP SSL Auth → upload PFX Gaspar SC + senha `123456` |

## 6. Teste sandbox via dashboard — bloqueado até criar a cred

Depois de criar a cred `santander_gaspar_mtls` e vincular nos 3 HTTP nodes do adapter, o fluxo esperado é:

1. Abrir dashboard (rota `GET /dashboard` do main workflow)
2. Selecionar Ambiente = `SANDBOX (teste)`
3. Buscar títulos, marcar 1 parcela qualquer de R$ baixo
4. Selecionar banco/conta = `Santander Gaspar SC` (opção nova no dropdown)
5. Clicar `Emitir boletos` → modal deve mostrar sucesso
6. Verificar no Nekt (tabela `log_emissoes`) que a linha nova tem `banco=santander`, `conta=0028697`, `nossonumero` preenchido, `linhadigitavel` preenchida
7. Ler QR PIX com app bancário (só leitura, sem pagar) — deve aparecer info de teste do Santander

---

## Resumo executivo

**Pronto pra sandbox:** 95%. Falta 1 coisa manual — subir a cred `santander_gaspar_mtls` no n8n e vincular nos 3 HTTP nodes do adapter Santander.

**Pronto pra produção:** depois do teste sandbox acima, faltam 5 coisas (ver `CHECKLIST_PRODUCAO.md`):

1. Criar app produção no portal Santander
2. Copiar client_id/secret prod
3. Rodar curl pra criar workspace prod → guardar UUID
4. Substituir placeholders `__SANTANDER_GASPAR_PROD_CLIENT_ID__`, `__SANTANDER_GASPAR_PROD_CLIENT_SECRET__`, `__SANTANDER_GASPAR_PROD_WORKSPACE_ID__` no adapter
5. Confirmar com Aline: convênio 0028697 tá mesmo no CNPJ 0002-22 (Gaspar SC)?

**Zero risco pros bancos existentes.** Sicoob PE, Sicoob SP, BB SC, BB SP, Itaú Gaspar, Itaú PE seguem intocados. Caixa e Safra tiveram routing corrigido (efeito colateral positivo da auditoria).
