# Workflow Chat — Agente Text-to-SQL (Plataforma Soul)

Workflow n8n `Plataforma Soul · Chat` (id `xIC5nmRAcGsZ4ba0`).
Endpoint: `POST /webhook/plat/api/chat` (body `{ mensagem, modelo, conversa_id }`, header `Authorization: Bearer <token HMAC>`).

O chat deixou de usar um roteador de ferramentas fixas e passou a ser um **agente
text-to-SQL**: para qualquer pergunta, o Claude gera uma consulta SQL (Athena/Trino)
sobre as tabelas da Nekt liberadas para o perfil do usuário, executa via API da Nekt
e responde a partir dos dados reais. Se o SQL falhar, há **auto-correção** (o erro do
Athena volta para o Claude, que reescreve a consulta).

## Fluxo de nós

```
Webhook Chat
  → Get HMAC Chat (plat_config: hmac_secret)
  → Prep (01-prep.js)            valida token HMAC, mascara PII, monta o "planner"
  → Sessao Valida? (IF)
       falso → Respond 401
       verdadeiro → Router IA (HTTP Anthropic, Sonnet, tool "plano")
         → Rotear (02-rotear.js) lê o plano, VALIDA o SQL (SELECT-only, tabelas do
           perfil, bloqueio de R$ p/ Industrial, LIMIT), decide acao
         → Acao (Switch: tool | geral | fora)
             tool → Nekt Query (POST sql-query, onError=continue)
                → Nekt OK? (IF state==SUCCEEDED)
                    ok  → Nekt CSV → Parse Dados (03) → Resposta IA → Final Tool
                    erro→ Prep Reparo (04) → Reparo IA (HTTP Anthropic)
                          → Aplicar Reparo (05, revalida) → Nekt Query 2 (onError=continue)
                          → Nekt OK 2? (IF)
                               ok  → Nekt CSV → Parse Dados → Resposta IA → Final Tool
                               erro→ Falha Dados (06, mensagem amigável) → Finalize
             geral → Resposta Geral (HTTP) → Final Geral
             fora  → Final Fora
         → Finalize → Log Interacao (plat_interacoes) → Respond Chat
```

## Guardrails (defesa em camadas)

1. **Prep** — verificação HMAC do token; mascara CPF/CNPJ/telefone antes de enviar ao Claude.
2. **Planner (system prompt)** — só recebe o catálogo de tabelas do perfil; instruído a
   nunca gerar R$ para Industrial/Qualidade e nunca selecionar PII.
3. **Rotear (código)** — valida o SQL gerado: apenas `SELECT`/`WITH`, uma instrução, sem
   DDL/DML, apenas schemas `nekt_raw`/`nekt_service`/`nekt_trusted`, apenas as tabelas
   permitidas do perfil, bloqueio de colunas monetárias para perfis sem R$, e injeta `LIMIT`.
4. **Parse Dados (código)** — remove colunas de PII sempre e colunas de R$ para perfis sem
   permissão, **antes** de os dados chegarem ao Claude que redige a resposta.

## Mapeamento tabela → perfil

- **Industrial / Qualidade** (kg, peças, % — nunca R$): produtos, estoque_nr_peca,
  estoque_local, estoque_local_lote_fios, movimentos_estoque, grade_produtos,
  ficha_tecnica_produtos_composicao, pedidos_venda_capa, pedidos_venda_itens,
  op_tecelagem, op_tecelagem_entrada_fios, op_tint_capa, op_tint_item,
  op_tint_item_pecas, op_tint_item_pecas_separadas, op_tint_item_pedidos,
  fatura_capa, fatura_itens (só quantidades), clientes (só nome/cidade).
- **Financeiro / Comercial** (R$ e kg): nekt_service.faturas_unificadas_completo,
  cr_documentos, cp_documentos, cr_lancamentos, cp_lancamentos, credito_cliente,
  despesas (+subgrupos), cp_documentos_despesas, cp_documentos_centro_custo_conta_contabil,
  cp_documentos_tributos, baixa_cp_contra_cr (+lancto_cp/_cr), nota_fiscal_capa,
  nota_fiscal_eletronica_eventos, entradas_itens_lancamentos_saldos, cad_tear,
  clientes, fornecedores.
- **Diretoria / admin**: catálogo Industrial + Financeiro e liberação para qualquer
  tabela dos schemas `nekt_raw` / `nekt_service` / `nekt_trusted`.

> Tabelas do mapeamento do cliente que não estão sincronizadas no warehouse
> (nota_fiscal_duplicatas, apontamento_producao_tecelagem/tinturaria, ceps_transportadora,
> cp/cr_lancamentos_centro_custo_conta_contabil, despesas_orcamento) foram omitidas por
> não existirem em `nekt_raw`.

## Modelos e credenciais

- Planner e auto-correção: `claude-sonnet-5` (qualidade de SQL). A resposta final usa o
  modelo escolhido pelo usuário na interface (opus/sonnet/haiku).
- Credenciais n8n: Anthropic (`anthropicApi`), Nekt (`httpHeaderAuth`). Os arquivos `.js`
  aqui são o código dos nós Code; o HMAC secret e as chaves vivem apenas no n8n.

## Motor SQL

Amazon Athena (Trino/Presto). Tabelas referenciadas como `schema.tabela`. Datas com
`DATE '...'`, `current_date`, `date_add('day', n, current_date)`. Joins com
`CAST(a.chave AS VARCHAR)=CAST(b.chave AS VARCHAR)`.
