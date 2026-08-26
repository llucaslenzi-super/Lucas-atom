# Checklist pré-produção — Santander Gaspar

> Bater tudo antes de virar chave pro Santander em produção. Sandbox já funciona (validado 25/08/2026, boleto R$100 emitido com linha digitável + QR PIX).

---

## 1. Alinhamento com Santander (Aline / Rogerio)

- [ ] **Confirmar CNPJ do convênio `0028697`** — precisa bater com o CNPJ do certificado A1 usado no adapter. Se for `35.588.873/0002-22` (Soul PE, o que já testamos em sandbox): ✅ zero retrabalho. Se for outro CNPJ da Soul (`0001-41` Gaspar SC ou `0003-03`): precisa reemitir o `.pfx` no CNPJ correto OU pedir pra Aline mover o convênio.
- [ ] **Confirmar dados de conta:** agência, conta corrente, número do cliente, código do beneficiário, código da modalidade. Documentar em `ADAPTER_SANTANDER_GASPAR.md` no CFG_SANTANDER_GASPAR.
- [ ] **Confirmar convênio ativo em prod** (o e-mail do Santander diz que já geram boletos via API — validar se o convênio 0028697 aceita novos apps).

## 2. Portal Santander Developer (Lucas)

- [ ] **Criar aplicação de produção** no portal (a atual `sc api Santander boletos` é sandbox — sandbox não promove). Passos: My Applications → Create Production Application → subir mesmo cert `.pfx` → nomear `soul-boletos-prod` → confirmar. Anotar novo `client_id_prod` + `client_secret_prod`.
- [ ] **Ativar produto "Cobrança / Emissão de Boletos"** na app de prod (Add Products → Emissão de Boletos).
- [ ] **Guardar client_id/secret prod num vault** (não em código-fonte). Ex: 1Password, Bitwarden, ou variável de ambiente n8n.

## 3. n8n — Credencial e config

- [ ] **Subir cred `santander_gaspar_mtls`** no n8n (Credentials → New → HTTP SSL Auth → upload PFX Soul PE + senha do certificado). Nome exato importa: `santander_gaspar_mtls`.
- [ ] **Vincular cred nos 3 nodes HTTP do Adapter Santander Gaspar:**
  - `Sandbox Token Santander`
  - `Prod Token Santander`
  - `Santander POST Boleto`
  (Já configurados via `newCredential('santander_gaspar_mtls')` no adapter — aparecem com aviso "credential missing" até você vincular.)

## 4. n8n — Bootstrap workspace produção (curl manual)

- [ ] Rodar curl abaixo pra criar 1x a workspace de produção, guardar o `id` (UUID) retornado:

```bash
# 1) pegar token de produção
curl -sS -X POST "https://trust-open.api.santander.com.br/auth/oauth/v2/token" \
  --cert-type P12 \
  --cert "$HOME/Downloads/<CAMINHO_PFX_ECNPJ>:<SENHA_PFX>" \
  -d "client_id=<CLIENT_ID_PROD>" \
  -d "client_secret=<CLIENT_SECRET_PROD>" \
  -d "grant_type=client_credentials" > /tmp/tok_prod.json

# 2) extrair
TOKEN=$(python3 -c "import json; print(json.load(open('/tmp/tok_prod.json'))['access_token'])")

# 3) criar workspace prod
curl -sS -w "\nHTTP %{http_code}\n" -X POST "https://trust-open.api.santander.com.br/collection_bill_management/v2/workspaces" \
  --cert-type P12 \
  --cert "$HOME/Downloads/<CAMINHO_PFX_ECNPJ>:<SENHA_PFX>" \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Application-Key: <CLIENT_ID_PROD>" \
  -H "Content-Type: application/json" \
  -d '{"type":"BILLING","covenants":[{"code":28697}],"description":"Soul Textil Producao","bankSlipBillingWebhookActive":true,"pixBillingWebhookActive":true,"webhookURL":"https://soultextil.app.n8n.cloud/webhook/santander-callback"}'
```

- [ ] Anotar `id` retornado — vira `__SANTANDER_GASPAR_PROD_WORKSPACE_ID__` no Fan Out do adapter.

## 5. n8n — Substituir placeholders de prod no adapter

No workflow `Adapter Santander Gaspar` (cxjhU46JBfCnKM12):

- [ ] Node **`Prod Token Santander`** → editar body params:
  - `client_id`: trocar `__SANTANDER_GASPAR_PROD_CLIENT_ID__` pelo real
  - `client_secret`: trocar `__SANTANDER_GASPAR_PROD_CLIENT_SECRET__` pelo real
- [ ] Node **`Fan Out Parcelas Santander`** → editar `ENV_MAP.prod`:
  - `client_id`: trocar `__SANTANDER_GASPAR_PROD_CLIENT_ID__` pelo real
  - `workspace_id`: trocar `__SANTANDER_GASPAR_PROD_WORKSPACE_ID__` pelo UUID retornado no passo 4

## 6. Webhook de callback (opcional, mas recomendado)

Se quiser receber notificação automática de liquidação de boleto:

- [ ] Confirmar que webhook `POST /webhook/santander-callback` está ativo no n8n (main workflow `POST sicoob-callback` cobre esse pattern; talvez precise criar um receiver específico pra Santander)
- [ ] Cadastrar URL no portal Santander (via API `POST /webhooks` ou pelo portal)
- [ ] Anotar `idWebhook` retornado

## 7. Testes obrigatórios (ordem)

### 7.1 Sandbox (garante que arquitetura tá plugada)

- [ ] **Emitir 1 boleto R$1** pelo dashboard: env=sandbox, banco=Santander Gaspar SC, 1 título qualquer. Confere log: `status_registro: ok` + `nossonumero` + `linhadigitavel` preenchidos.
- [ ] **Ler QR PIX** com qualquer app bancário — só leitura, sem pagar. Tem que aparecer info de teste do Santander.

### 7.2 Produção (validação real)

- [ ] **Emitir 1 boleto R$1** pra CNPJ interno da Soul (pagador = Soul, pra evitar cobrar cliente real). Confere log.
- [ ] **Pagar internamente** (transferir R$1 pra própria conta via linha digitável). Confere se webhook chega e o log atualiza pra `situacao_boleto: 'Pago'`.
- [ ] **Emitir 1 boleto pra cliente real** (pequeno valor, doc real). Confere se cliente recebe email + WhatsApp.

## 8. Rollback plan

Se qualquer coisa quebrar em prod:

- [ ] **Remover option Santander do dashboard** (HTML Part 2): usuário não consegue mais selecionar Santander → nenhum boleto novo emitido pra ele. Sicoob/Itaú continuam funcionando.
- [ ] **Backup do workflow atual** antes de mexer: exportar `Agente Boletos Soul` como JSON e guardar.
- [ ] **Boletos já emitidos** ficam válidos — o boleto tá registrado no Santander independente do n8n. Cliente paga normalmente.

## 9. Documentar depois de plugar

- [ ] Atualizar `ADAPTER_SANTANDER_GASPAR.md` com valores reais preenchidos (não secretos, só refs):
  - Workspace ID prod
  - Data de criação da app prod
  - Contato Aline/Rogerio
  - Peculiaridades descobertas em prod (se houver diferença do sandbox)

## 10. Bloqueadores conhecidos

| Bloqueador | Como resolver |
|---|---|
| Convênio 0028697 no CNPJ errado | Aline confirma qual CNPJ; se precisar outro, subir novo `.pfx` correspondente e trocar cred |
| Certificado vencido (18/06/2027) | Renovar A1 antes do vencimento na mesma AC (AC DIGITAL MULTIPLA G1). Trocar cred no n8n. |
| Rate limit 429 em prod | Implementar backoff exponencial no HTTP node (`retry: true`, `retryInterval`) |
| Webhook não chega | Verificar SSL certificate do endpoint público n8n; portal Santander exige HTTPS válido |
