# Atom — Especificação de Build do Backend (handoff para execução autônoma)

> **Para um agente/Claude que vai executar:** este documento é auto-contido. Leia-o
> inteiro + `README.md` + o código em `app/` antes de agir. Siga o **plano de execução
> (§7)** na ordem, cada passo tem sua verificação. **Nunca** viole as invariantes (§6)
> nem troque o stack travado (§2) sem autorização explícita do Lucas na conversa.
> Em conflito entre uma instrução pontual e este contrato, **pare e pergunte**.

---

## 1. O produto em uma página

**Atom** é um SaaS multi-tenant que entrega um **agente de prospecção de exportação**:
o cliente (exportador brasileiro) sobe o relatório PEIEX, e o sistema descobre empresas
estrangeiras com perfil de comprador/importador, enriquece o contato e devolve um **lote
de leads** em XLSX/CSV/PDF.

**Jornada do cliente (o que o backend precisa suportar):**
1. **Cadastro (admin).** O operador (Lucas) cadastra a empresa cliente e emite login/senha. Sem self-signup, sem billing no v1.
2. **Upload do relatório.** Cliente loga e sobe o PDF do PEIEX — 2 modelos: *Plano de Exportação* (produto) e *Mapa de Valor* (serviço).
3. **Leitura.** O sistema extrai: tipo (produto/serviço), código fiscal (NCM p/ produto, NBS/CNAE p/ serviço), produto/serviço, mercado-alvo e perfil de comprador.
4. **Sugestão + ajuste.** O sistema sugere mercado/perfil a partir do relatório; o cliente confirma ou ajusta, **dentro dos mercados suportados**. Relatório sem país único → sugere pelo perfil e pede confirmação.
5. **Disparo com cota.** Cliente roda o agente. Cota = **leads entregues/mês** (teto por assinatura). Dentro de cada pesquisa o agente mira **350 por lote (25 chamadas × ~14 leads)** pra focar e não dispersar.
6. **Pipeline (6 etapas em cascata).** E1 descoberta → E2 enriquecimento → E3 Instagram (nos furos) → (E4 decisor, premium) → E5 limpeza → (E6 Places, amostral). Cada etapa grava auditoria no nosso Postgres.
7. **Entrega.** Lote exportável em **XLSX, CSV e PDF formatado**.
8. **Histórico.** Pesquisas salvas por tenant, acessíveis em outra sessão.

---

## 2. Stack travado (não trocar sem autorização do Lucas)

- Cloud **GCP**, região **southamerica-east1**. API **Cloud Run** · Banco **PostgreSQL (Cloud SQL), SEM pgvector** · Fila **Cloud Tasks** · Segredos **Secret Manager** · Export **Cloud Storage** · Imagens **Artifact Registry** · Obs **Cloud Logging/Monitoring** · Identidade **IAM + SA por serviço**.
- Orquestração do pipeline: **n8n self-hosted** (Compute Engine VM + Docker). Migração futura para worker em código é autorizada **só com OK do Lucas**.
- Linguagem/framework da API: **Python + FastAPI** (decidido nesta conversa; era LACUNA nos docs).
- Atores do pipeline (fixos): OpenAI `gpt-6.1-terra` (fallback `gpt-5.5`) + web_search; Apify `vortex_data/google-maps`, `apify/instagram-profile-scraper`, `harvestapi/linkedin-company-employees`; Google Places API (New).
- Trocar qualquer item (outra cloud/banco/modelo/actor, adicionar Apollo/Coresignal/Volza/pgvector, etc.) **exige autorização explícita**.

---

## 3. Estado atual do código (o que JÁ está pronto)

Tudo em `atom-backend/`, branch `claude/exciting-thompson-bz6ct8`. **Blocos 0–7 implementados e verificados localmente** (20/20 testes + smoke ao vivo por HTTP). Integrações externas estão **mockadas** atrás de interface (`app/providers/`).

| Já pronto | Onde |
|---|---|
| App FastAPI + `GET /v1/health`, docker-compose, Dockerfile | `app/main.py`, `docker-compose.yml`, `Dockerfile` |
| Schema completo (ARQUITETURA §5) + **RLS** por tenant, migration Alembic | `app/migrations/versions/0001_initial.py` |
| Auth argon2id + JWT (login/refresh) + middleware tenant (`SET LOCAL app.tenant_id`) + `auth_lookup` SECURITY DEFINER | `app/security.py`, `app/deps.py`, `app/routers/auth.py` |
| `POST/GET /v1/consultas` com **cota** (FOR UPDATE, debita por entregues) | `app/routers/consultas.py` |
| `POST /v1/relatorios` upload + **parser heurístico dos 2 modelos** (NCM/NBS) | `app/routers/relatorios.py`, `app/providers/report_parser.py` |
| Pipeline **worker local** (E1→E2→E5), stage events, teto de custo, persistência + débito de cota | `app/pipeline/worker.py` |
| **Callback HMAC** (o endpoint que o n8n vai chamar) | `app/routers/internal.py` |
| Export **XLSX/CSV/PDF** | `app/export.py`, endpoint em `consultas.py` |
| Interface de providers + mocks (trocar mock→real = plugar chave) | `app/providers/base.py`, `app/providers/mock.py`, `app/providers/__init__.py` |
| Testes: parser(4 modelos), jornada e2e, cota+corrida, isolamento A×B, callback HMAC | `tests/` |

**Decisão de sprint a reverter quando ligar o n8n:** a orquestração hoje é um worker em
Python (não n8n), de propósito, pra testar a jornada sem dependências. O design mantém o
n8n plugável: a camada de auditoria (`pipeline_runs`/`pipeline_stage_events`) e o callback
HMAC já existem. **§7 Bloco 6** descreve a migração para n8n.

---

## 4. Modelo de dados (resumo; detalhe na migration 0001)

Todas as tabelas de negócio carregam `tenant_id` (UUID) e têm RLS. Tabelas: `tenants`,
`users`, `assinaturas`, `relatorios`, `consultas`, `leads`, `exports`, `pipeline_runs`,
`pipeline_stage_events`, `eventos_auditoria`.

**Delta vs. ARQUITETURA §5 (já aplicado):** `relatorios`/`consultas` usam `tipo`
(produto|servico) + `codigo_fiscal` (NCM ou NBS) no lugar de `produto_ncm`; `exports` tem
`formato` (xlsx|csv|pdf).

---

## 5. Contrato da API

**Existentes (prontos):**
- `POST /v1/auth/login`, `POST /v1/auth/refresh`
- `POST /v1/relatorios` (multipart PDF) → `{id, tipo, codigo_fiscal, produto_descricao, mercado_sugerido, perfil_comprador}`
- `POST /v1/consultas` → 202 `{id, status, leads_solicitados, ...}`
- `GET /v1/consultas`, `GET /v1/consultas/{id}`, `GET /v1/consultas/{id}/leads`
- `GET /v1/consultas/{id}/export?formato=xlsx|csv|pdf`
- `POST /v1/internal/consultas/{id}/callback` (HMAC) — para o n8n

**A construir (§7):** endpoint de stage-event para o n8n reportar cada etapa
(`POST /v1/internal/consultas/{id}/stage`, HMAC); `GET /v1/catalogos/mercados` (catálogo
de mercados suportados); rota de retenção/exclusão LGPD (Bloco 9).

Regra de contrato: **nunca** aceitar `tenant_id` do cliente; sempre derivar do JWT.

---

## 6. Invariantes e guardrails (NÃO violáveis, valem em toda fase)

- Nenhuma query sem filtro por `tenant_id` derivado do JWT; `tenant_id` nunca vem do cliente.
- RLS ativa nas tabelas de negócio. Teste obrigatório: JWT do tenant A nunca retorna linha do tenant B.
- Segredos só via Secret Manager — nunca em código, env commitado ou log.
- Dado pessoal só em `southamerica-east1` (LGPD).
- Cota debitada pelos leads **entregues** (no callback), não no disparo; teto mensal respeitado em transação `FOR UPDATE`.
- **Guardrail de custo obrigatório** em toda consulta (teto por consulta e por tenant/dia). Sem ele, não faz deploy do pipeline. Estourou → para e marca `parcial`.
- Fallback de modelo `gpt-6.1-terra` → `gpt-5.5` quando falha ou devolve poucos leads válidos.
- Afirmou limite/preço/parâmetro? Tem que ter fonte (§10). Sem fonte = marca `LACUNA` e pergunta; não chuta.

---

## 7. Plano de execução — o que falta (ordem + verificação)

> Pré-condição p/ Blocos 5/6: o Lucas prover as chaves (§8) via Secret Manager / formulário
> seguro. Sem chave, implemente o cliente real + deixe o mock como fallback e **marque o passo
> como bloqueado**, não invente resposta de API.

### Bloco 5 — Integrações reais (substituem os mocks, mesmo contrato `app/providers/base.py`)

Para cada uma: implementar o cliente, ativar em `get_providers()` quando a chave existir,
e **verificar contra entrada real** (os 4 PEIEX: Surf/EUA, Sous/Paraguai, Rigbie/México, Techfrig/Argentina).

- **E1 Descoberta (OpenAI) — `descobrir(produto, mercado, perfil, n)`**
  - `POST https://api.openai.com/v1/responses`; modelo `gpt-6.1-terra` (fallback `gpt-5.5`); `reasoning.effort="low"`, `tools=[{"type":"web_search"}]`, `tool_choice="required"`, `max_output_tokens≈5000`.
  - Prompt blindado (sem isso o modelo pede permissão): *"Você é um pesquisador de prospecção B2B. PRODUTO: {produto}. MERCADO-ALVO: {pais}. PERFIL: {perfil}. Use a ferramenta de busca na web AGORA para achar {N} empresas REAIS compradoras/importadoras potenciais. NÃO peça permissão, NÃO escreva nada fora do JSON, NÃO invente telefones. Responda começando com '[' um array JSON de {N} objetos com chaves: empresa, cidade, site, contato."*
  - Saída: array JSON `{empresa, cidade, site, contato}`; fallback de parse por regex `\[.*\]`.
  - **Meta 25 chamadas × ~14 leads = 350**, variando ângulo (cidade/sub-setor/tipo), com dedup. Menos que 350 reais → entrega o que há (`parcial`).
  - Custo ~US$10/1.000 buscas + tokens. Verifica: devolve empresas on-target, 0 inventado.

- **E2 Enriquecimento (Apify Maps) — `enriquecer(nomes, pais)`**
  - `POST https://api.apify.com/v2/acts/vortex_data~google-maps/runs?token=…`; input `{searchStringsArray, locationQueries:[pais], maxCrawledPlacesPerSearch:10 (MÍNIMO 10, abaixo→400), skipPlacesNotMatchingSearch:true, extractContactsFromWebsite:true, language:"es"|"en"}`. Poll do run até `SUCCEEDED`, pega dataset.
  - Saída/item: `title, phone, website, emails[], whatsapps[], instagrams[], categoryName`. Vem sujo (empresas vizinhas); limpeza é na E5. Custo ~US$0,70/1.000 places.

- **E3 Instagram (Apify) — só nos furos — `instagram(handles)`**
  - Actor `apify/instagram-profile-scraper` (NÃO o de busca). Input `{usernames:[handles]}`. Saída `biography, externalUrl, businessEmail, fullName, username`.
  - Roda só em leads sem telefone nem e-mail após E2. Handle de `instagram.com/<handle>` (descartar `p`,`reel`,`explore`).

- **E4 Decisor (Apify LinkedIn) — PREMIUM/opcional — `decisor(empresas, cargos, pais)`**
  - Actor `harvestapi/linkedin-company-employees`. Input `{companies, jobTitles:["Compras","Purchasing","HSE",...], locations:[pais], profileScraperMode:"Full + email search ($12 per 1k)", maxItems:8, maxItemsPerCompany:2, companyBatchMode:"all_at_once"}`. Saída `firstName,lastName,headline,linkedinUrl,emails[]` (e-mail frequentemente vazio).
  - Só no plano Premium e só em vertical corporativa (indústria grande). LACUNA conhecida: e-mail do decisor não vem no modo "+email" → passo extra (verificador) se obrigatório.

- **E5 Limpeza/casamento (OpenAI) — `limpar(brutos, produto, perfil, alvo)`**
  - `gpt-6.1-terra`, `max_output_tokens≈4000`. Prompt: seleciona melhores leads do perfil (descarta fora do perfil), deduplica, escolhe UM telefone/UM whatsapp/UM email principais, score 0–100, racional curto em PT. **Responde APENAS JSON.**

- **E6 Validação (Google Places) — opcional/amostral — `validar(nome, cidade)`**
  - Places API (New): Text Search + Place Details. Custo ~US$32/1.000 → rodar em TODOS estoura o teto; usar em **10–20% dos leads** (QA) ou nos de maior valor.

**Guardrails de custo (obrigatórios no cliente):** `maxTotalChargeUsd` no Apify; contador de tokens/buscas no GPT; para e marca `parcial` ao estourar; fallback terra→5.5; cache por país+setor+janela no nosso banco (não re-chamar para o mesmo recorte recente).

### Bloco 6 — Orquestração no n8n (substitui o worker local)

Objetivo: workflow n8n que recebe `consulta_id`, roda a cascata via os actors/APIs acima, grava
cada etapa no nosso Postgres (via endpoint HMAC) e devolve os leads limpos via callback HMAC.

**Workflow (nós, em ordem):**
1. **Webhook** (POST, path `/atom/consulta`): recebe `{consulta_id}` + header HMAC. Valida a assinatura (Function node: HMAC-SHA256 do body com `CALLBACK_HMAC_SECRET`).
2. **HTTP Request — "buscar contexto"**: `GET` interno na nossa API (ou passa tudo no disparo) para obter produto, mercado(paises), perfil, plano, leads_solicitados da consulta.
3. **Loop de ângulos (E1)**: até 25 iterações HTTP Request → OpenAI Responses (`gpt-6.1-terra`), acumulando empresas com dedup, até ~350 ou esgotar. **Fallback** para `gpt-5.5` numa chamada que falhar/retornar pouco. Após E1: HTTP Request → `POST /v1/internal/consultas/{id}/stage` (etapa=descoberta).
4. **E2 (Apify Maps)**: start run → poll (Wait + HTTP até SUCCEEDED) → get dataset. Stage event (enriquecimento).
5. **IF — furos**: filtra leads sem telefone/email → **E3 (Apify Instagram)** só neles. Stage event (instagram).
6. **IF — plano premium**: **E4 (Apify LinkedIn)** nas empresas de maior fit. Stage event (decisor).
7. **E5 (OpenAI limpeza)**: HTTP Request → `gpt-6.1-terra`, JSON only → leads finais. Stage event (limpeza).
8. **Guardrail**: Function node soma custo das etapas; se > teto da consulta, trunca e marca `parcial`.
9. **HTTP Request — callback**: `POST /v1/internal/consultas/{id}/callback` com header `X-Signature` = HMAC do body, body `{leads:[...], custo_total_usd, parcial}`.

**Credenciais no n8n (Secret Manager → env do n8n):** `OPENAI_API_KEY`, `APIFY_TOKEN`,
`GOOGLE_PLACES_KEY`, `CALLBACK_HMAC_SECRET`, URL base da API.

**Na API (a construir p/ o n8n):** `POST /v1/internal/consultas/{id}/stage` (HMAC) que grava
um `pipeline_stage_events`. O `callback` já existe.

**Disparo:** `POST /v1/consultas` enfileira no **Cloud Tasks**, que chama o Webhook do n8n (em vez do `BackgroundTasks` local). Trocar `background.add_task(run_consulta, ...)` por um enqueue no Cloud Tasks apontando para o webhook do n8n.

**Verifica:** consulta real gera lote gravado; erro numa etapa marca `status=erro` com `erro_msg`; teto de custo para a consulta e marca `parcial`.

### Bloco 7 — Export (FEITO; validar com dados reais)

XLSX/CSV/PDF já implementados. Ao ligar GCP: gravar no **Cloud Storage** e devolver **signed URL** temporária em vez de stream direto.

### Bloco 8 — Infra GCP + deploy

1. Projeto GCP, região `southamerica-east1`, APIs (Run, SQL Admin, Secret Manager, Tasks, Storage, Artifact Registry, Logging, IAM).
2. Cloud SQL Postgres; 2 DBs `app` e `n8n`; roles `atom_owner`/`atom_app` + `citext`; **sem pgvector**. Rodar migrations.
3. Secret Manager: `OPENAI_API_KEY`, `APIFY_TOKEN`, `GOOGLE_PLACES_KEY`, `DB_*`, `JWT_SECRET`, `CALLBACK_HMAC_SECRET`. SA por serviço (least privilege).
4. Artifact Registry + bucket de export em `southamerica-east1`.
5. Deploy da API no **Cloud Run**; VM (Compute Engine + Docker) para **n8n**.
6. Trocar storage local por GCS + signed URL; `BackgroundTasks` por Cloud Tasks → webhook n8n.
7. Verifica: health 200 em prod; isolamento A×B mantém em prod; pipeline real gera lote dentro do teto.

### Bloco 9 — Endurecimento

- Observabilidade: logs estruturados (API + n8n) no Cloud Logging; **alerta de consumo de crédito** (OpenAI/Apify) no Monitoring.
- Robustez: Cloud Tasks com retry idempotente (job que falha por timeout re-tenta sem duplicar leads).
- Cache de recorte: país+setor+janela reaproveitado entre clientes.
- LGPD: job de expurgo por retenção; rota de exclusão do titular. Base legal (§8/§10 ARQUITETURA) é **LACUNA jurídica** — não é automática.

---

## 8. Checklist de segredos e recursos (o que o Lucas precisa prover)

| Item | Para quê | Bloqueia |
|---|---|---|
| `OPENAI_API_KEY` | E1 descoberta + E5 limpeza | Bloco 5/6 |
| `APIFY_TOKEN` | E2 Maps, E3 Instagram, E4 LinkedIn | Bloco 5/6 |
| `GOOGLE_PLACES_KEY` | E6 validação amostral | Bloco 5/6 (opcional) |
| Projeto GCP + billing + acesso console | toda a infra | Bloco 8 |
| Instância n8n (VM) | orquestração | Bloco 6 |
| Decisão **plano Padrão × Premium** + teto por plano | cota, E4 | go-live |
| Decisão de risco **scraping** (E2–E4) por mercado | ligar E2–E4 em prod | go-live |
| **Base legal LGPD** (jurídico) | vender/produção | go-live |

---

## 9. Definition of Done (critério de "pronto")

Marco MVP: criar tenant → login → subir relatório → sistema sugere mercado/perfil → cliente
dispara consulta → pipeline real (n8n) roda dentro do teto de custo → recebe lote de leads
isolado por tenant → exporta XLSX/CSV/PDF → pesquisa fica no histórico. Com os testes do
repo verdes **+** um teste de ponta a ponta contra um mercado real por plano, e observabilidade
e alerta de custo ligados.

---

## 10. Fontes oficiais (consultar ao implementar cada área)

- OpenAI Responses + web_search: https://platform.openai.com/docs/api-reference/responses
- Apify API + actors: https://docs.apify.com/api/v2 · /vortex_data/google-maps · /apify/instagram-profile-scraper · /harvestapi/linkedin-company-employees
- Google Places API (New): https://developers.google.com/maps/documentation/places/web-service
- GCP: https://cloud.google.com/{run,sql,secret-manager,tasks,storage}/docs
- n8n self-hosting: https://docs.n8n.io/hosting/
- LGPD: Lei 13.709/2018
