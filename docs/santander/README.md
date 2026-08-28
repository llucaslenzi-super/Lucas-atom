# Santander Gaspar — Docs

Documentação da integração Santander (convênio 0028697, CNPJ Gaspar SC 35.588.873/0002-22) plugada no agente multibanco `Agente Boletos Soul` no n8n.

## Arquivos

| Arquivo | Pra que serve |
|---|---|
| [`API_BOLETOS_SANTANDER.md`](./API_BOLETOS_SANTANDER.md) | Doc técnica da API Santander — endpoints, OAuth mTLS, payloads campo a campo, erros, mapping ERP Soul → API. Inclui os 3 curl reais que funcionaram em sandbox. |
| [`ADAPTER_SANTANDER_GASPAR.md`](./ADAPTER_SANTANDER_GASPAR.md) | Spec do workflow n8n `Adapter Santander Gaspar` (id `cxjhU46JBfCnKM12`) — contrato input/output, config hardcoded, 8 nodes detalhados, diferenças vs Sicoob/Itaú. |
| [`PLUGAR_NO_MAIN_WORKFLOW.md`](./PLUGAR_NO_MAIN_WORKFLOW.md) | Registro do que foi alterado no main workflow (`PKhlEnAj93IA9Mwv`) pra plugar o adapter: Switch, nodes novos, conexões, Prep Log Row, dashboard. Rollback plan incluído. |
| [`CHECKLIST_PRODUCAO.md`](./CHECKLIST_PRODUCAO.md) | Checklist executável pra virar chave em produção — bootstrap portal, cred mTLS, workspace prod, testes obrigatórios. |
| [`AUDITORIA_SANDBOX.md`](./AUDITORIA_SANDBOX.md) | Snapshot da auditoria sandbox 28/08/2026 antes de subir prod — status de cada componente (cert, app portal, adapter, main workflow, cred), bloqueadores restantes. |
| [`PORTAL_PROD_STEP_BY_STEP.md`](./PORTAL_PROD_STEP_BY_STEP.md) | Guia clique-por-clique pra criar a app de produção no portal Santander Developer. Foca no que trava (upload cert, ativação do produto Cobrança, captura de client_id/secret). |

## Status atual

- ✅ **Sandbox validado ponta a ponta via curl** (25/08/2026): OAuth mTLS + workspace criada + boleto R$100 emitido com linha digitável + QR PIX
- ✅ **Adapter workflow criado** no n8n (`cxjhU46JBfCnKM12`, 8 nodes)
- ✅ **Plugado no main workflow** — Switch output 4, Sub Adapter, Adapt Output, Prep Log Row, dashboard atualizado
- ✅ **Auditoria pós-integração** (28/08/2026): Switch corrigido (routing das outras contas realinhado sem alterar comportamento), Santander re-adicionado no dropdown do dashboard
- ⏸ **Bloqueador único pra rodar sandbox pelo dashboard:** subir cred `santander_gaspar_mtls` (PFX Gaspar SC) no n8n e vincular nos 3 HTTP nodes do adapter
- ⏸ **Produção pendente:** confirmar CNPJ do convênio com Aline + criar app prod no portal + criar workspace prod + trocar placeholders no adapter

## Nada mexido em Sicoob nem Itaú — alterações são 100% aditivas.
