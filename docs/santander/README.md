# Santander Gaspar — Docs

Documentação da integração Santander (convênio 0028697, CNPJ Gaspar SC 35.588.873/0002-22) plugada no agente multibanco `Agente Boletos Soul` no n8n.

## Arquivos

| Arquivo | Pra que serve |
|---|---|
| [`API_BOLETOS_SANTANDER.md`](./API_BOLETOS_SANTANDER.md) | Doc técnica da API Santander — endpoints, OAuth mTLS, payloads campo a campo, erros, mapping ERP Soul → API. Inclui os 3 curl reais que funcionaram em sandbox. |
| [`ADAPTER_SANTANDER_GASPAR.md`](./ADAPTER_SANTANDER_GASPAR.md) | Spec do workflow n8n `Adapter Santander Gaspar` (id `cxjhU46JBfCnKM12`) — contrato input/output, config hardcoded, 8 nodes detalhados, diferenças vs Sicoob/Itaú. |
| [`PLUGAR_NO_MAIN_WORKFLOW.md`](./PLUGAR_NO_MAIN_WORKFLOW.md) | Registro do que foi alterado no main workflow (`PKhlEnAj93IA9Mwv`) pra plugar o adapter: Switch, nodes novos, conexões, Prep Log Row, dashboard. Rollback plan incluído. |
| [`CHECKLIST_PRODUCAO.md`](./CHECKLIST_PRODUCAO.md) | Checklist executável pra virar chave em produção — bootstrap portal, cred mTLS, workspace prod, testes obrigatórios. |

## Status atual

- ✅ **Sandbox validado ponta a ponta** (25/08/2026): OAuth mTLS + workspace criada + boleto R$100 emitido com linha digitável + QR PIX
- ✅ **Adapter workflow criado** no n8n (`cxjhU46JBfCnKM12`)
- ✅ **Plugado no main workflow** — Switch, Sub Adapter, Adapt Output, Prep Log Row, dashboard atualizado
- ⏸ **Produção pendente:** confirmar CNPJ do convênio com Aline + criar app prod no portal + subir cred `santander_gaspar_mtls` no n8n + criar workspace prod

## Nada mexido em Sicoob nem Itaú — alterações são 100% aditivas.
