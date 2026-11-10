# Agentes — comece aqui

Antes de qualquer alteração, leia nesta ordem:

1. **`BUILD_SPEC.md`** — a especificação completa do backend do Atom: o produto, o
   stack travado, o que já está pronto, o que falta (Blocos 5–9), o workflow n8n e o
   checklist de segredos. É o contrato de execução. Siga o **§7** na ordem; cada passo
   tem verificação.
2. **`README.md`** — como rodar local (Docker ou nativo) e a arquitetura multi-tenant.
3. O código em `app/` e os testes em `tests/`.

Regras não-negociáveis (detalhe em `BUILD_SPEC.md §2` e `§6`):
- Não troque o stack travado (GCP, Postgres sem pgvector, Cloud Run, n8n, OpenAI
  `gpt-6.1-terra`, actors Apify, Places) sem autorização explícita do Lucas.
- `tenant_id` vem **só do JWT**; RLS ativa; segredos só via Secret Manager.
- Cota debitada pelos leads **entregues**; guardrail de custo obrigatório.
- Afirmou limite/preço/parâmetro sem fonte? Marque `LACUNA` e pergunte — não chute.
- Sem a chave de uma API, implemente o cliente e deixe o passo **bloqueado**; não
  invente resposta de API.

Antes de abrir PR: `pytest` verde (inclui isolamento tenant A×B e cota com corrida).
