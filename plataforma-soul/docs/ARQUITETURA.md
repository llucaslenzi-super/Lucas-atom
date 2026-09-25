# Plataforma Soul Inteligência — Arquitetura

Plataforma corporativa de IA da **Soul Têxtil**. Login único → conversar com Claude
com segurança, rastreabilidade e dados internos reais (via Nekt). Duas faces:
**Operacional** e **Admin**. Projeto **independente** dos 69 workflows existentes —
reusa apenas as APIs (Claude, Nekt) e espelha padrões comprovados.

> Decisões travadas com o cliente:
> - **100% dentro do n8n** (webhooks servem o SPA + APIs JSON; Data Tables guardam estado).
> - **Só Claude** (sem GPT/Gemini). Seletor de modelo = Opus/Sonnet/Haiku.
> - **Login real** (pbkdf2 100k + token HMAC 8h) para 3 usuários; MFA/SSO/dispositivos
>   funcionais na tela mas com efeito simulado.
> - **Operacional + Admin juntos.**
> - **Visual Soul** (print de referência): fundo quase-preto, dourado/bronze, títulos
>   em serifa, cards de módulo, cabeçalho "PORTAL SOUL".
> - **Chat = cópia fiel da interface do Claude.** **Sem anexo de documentos.**
> - **3 usuários reais + demais de exibição** (indistinguíveis na interface); 19 no total, incluindo 4 diretores.
> - **Visual = dark mode do claude.ai** (cinza-carvão) com o amarelo/ouro Soul no lugar do laranja.

## Infra n8n
- Instância: `https://soultextil.app.n8n.cloud`
- Projeto: `Barw2Oxcw7p9hUTA` (Soul Textil)
- Credenciais reusadas:
  - `Anthropic account` (`sV5e1poef8MtXEss`) — Claude API
  - `nekt` (`0xR7b3XVYbkfuFVh`, httpHeaderAuth `x-api-key`) — Nekt Data API
- Nekt Data API: `POST https://api.nekt.ai/api/v1/sql-query/`
  body `{ "sql": "...", "mode": "csv", "mode_options": {"header": true, "delimiter": ","} }`
  → `{state:"SUCCEEDED", presigned_urls:[url]}` → **GET** na presigned URL → CSV (expira 1h).

## Data Tables (`plat_*`)
| Tabela | ID | Função |
|---|---|---|
| plat_config | `M9nV4qaH2NsFOA0X` | hmac_secret, modelo_padrao, tetos de custo, flags |
| plat_usuarios | `Ow8JHh7IQiaGhSkl` | usuários (3 reais + 12 mock) |
| plat_sessoes | `u7h0Tmp6N1XVLJuu` | sessões ativas / histórico de acesso |
| plat_interacoes | `GK9rsFAOGuolzaR8` | **log de rastreabilidade** (auditoria) |
| plat_conversas | `bU0a31zFpEE2kOLC` | conversas (agrupamento do histórico) |
| plat_destaques | `5IiRRfX2skRgYnI8` | biblioteca de respostas destacadas |
| plat_governanca | `8PQFWE1zXBd8TvGo` | política, matriz de dados, comitê, incidentes, casos de uso |
| plat_fontes | `Tm9fx22HzH2xsDjZ` | fontes de dado conectadas (por perfil) |
| plat_solicitacoes | `gHGfaN0S9uFkoiCI` | pedidos de novo acesso (→ comitê) |
| plat_assets | `owPD2NsQz7OLHtIS` | SPA em chunks — **legado/ocioso** (o SPA agora é servido via GitHub raw) |

> `id` é reservado pelo n8n; a chave de negócio própria é `uid`.

## Perfis e visibilidade
| Perfil | Face | Vê |
|---|---|---|
| **Diretoria** (`diretoria@soultextil.com.br`) | Admin | **tudo** + tabela de auditoria/rastreabilidade |
| **Industrial** (`industrial@soultextil.com.br`) | Operacional | estoque, clientes, pedidos, PCP, fichas técnicas, produção/OPs/fios — **kg e % apenas, NUNCA R$** (faturamento só como volume/margem %) |
| **Financeiro** (`financeiro@soultextil.com.br`) | Operacional | faturamento (R$), contas a pagar/receber, títulos, estoque, clientes |

**Roster (19 usuários em `plat_usuarios`)** — 3 logins reais + demais de exibição:
- Reais: Lucas Lenzi (diretoria, admin) · **Luiz Fontana** (industrial) · **Max Speroni** (financeiro).
- Diretores: **João Meurer** (Comercial) · **Natasha Wildi** (Operações) · **Thiago Bonetti** (Financeiro) · **Paulo Deschamps** (Industrial).
- Demais por área (Comercial, PCP, Qualidade — **Ivi Constante**, Logística, Compras, TI). Só os 3 reais têm senha; os demais aparecem nas telas de admin e no histórico, mas não autenticam.

## Guardrails (automáticos, backend)
- **PII**: mascara CPF, CNPJ, RG, telefone antes de ir ao Claude. **Nome de cliente
  é mantido** (mascarar tornaria a resposta comercial inútil).
- **Financeiro estrutural**: o perfil Industrial não recebe ferramentas com R$; qualquer
  valor monetário é convertido/removido (kg e % apenas).
- **Bloqueio por palavra-chave**: salário/folha, custo unitário — respondido com
  mensagem explicativa. Ficha técnica/`percfio` = **restrito** (Industrial pode usar;
  configurável na matriz de dados).
- Toda ativação de guardrail é registrada em `plat_interacoes.guardrails` + `alerta`.

## Chat = agente text-to-SQL sobre a Nekt (qualquer pergunta)
Camadas: `nekt_raw.mssql_{gaspar|loja_sp|matriz}_dbo_*` (cru por filial) · `nekt_service`/`nekt_trusted` (views curadas).

O chat **não** usa mais um conjunto fixo de ferramentas. Para qualquer pergunta, o Claude
(Sonnet) gera **uma consulta SQL** (Athena/Trino) sobre as tabelas liberadas para o perfil,
executa via `sql-query` da Nekt e responde a partir dos dados reais. Se o SQL falhar, o
erro do Athena volta ao Claude, que **reescreve a consulta** (auto-correção, 1 tentativa);
persistindo a falha, responde com mensagem amigável. Código e detalhes em
`workflows/chat/` (`01-prep` … `06-falha-dados` + `README.md`).

**Catálogo de tabelas por perfil** (o system prompt do planner só recebe o catálogo do perfil;
`Rotear` valida o SQL contra a mesma lista):

| Perfil | Escopo | Tabelas |
|---|---|---|
| **Industrial / Qualidade** | kg, peças, % — **nunca R$** | produtos, estoque_nr_peca, estoque_local, estoque_local_lote_fios, movimentos_estoque, grade_produtos, ficha_tecnica_produtos_composicao, pedidos_venda_capa/itens, op_tecelagem(+entrada_fios), op_tint_capa/item(+pecas/_separadas/_pedidos), fatura_capa/itens (só quantidades), clientes (só nome/cidade) |
| **Financeiro / Comercial** | R$ e kg | nekt_service.faturas_unificadas_completo, cr_documentos, cp_documentos, cr_lancamentos, cp_lancamentos, credito_cliente, despesas(+subgrupos), cp_documentos_despesas/_centro_custo_conta_contabil/_tributos, baixa_cp_contra_cr(+lancto_cp/_cr), nota_fiscal_capa, nota_fiscal_eletronica_eventos, entradas_itens_lancamentos_saldos, cad_tear, clientes, fornecedores |
| **Diretoria / admin** | tudo (R$ e kg) | catálogo Industrial + Financeiro **e** qualquer tabela de `nekt_raw`/`nekt_service`/`nekt_trusted` |

Tabelas do mapeamento do cliente sem sync no warehouse foram omitidas (nota_fiscal_duplicatas,
apontamento_producao_*, ceps_transportadora, cp/cr_lancamentos_centro_custo_conta_contabil,
despesas_orcamento).

**Segurança do SQL (`Rotear` + `Aplicar Reparo`)**: apenas `SELECT`/`WITH`, uma instrução, sem
DDL/DML, apenas schemas `nekt_*`, apenas tabelas do perfil, bloqueio de colunas monetárias para
perfis sem R$, `LIMIT` obrigatório. **`Parse Dados`** ainda remove colunas de PII (sempre) e de
R$ (perfis sem permissão) antes de os dados chegarem ao Claude.

Convenções de dado no catálogo: estoque de peças acabadas `situacao=1 AND revisao=1 AND codlocal IN (1,55)`;
nome limpo do produto `TRIM(SPLIT_PART(descricao,'#',1))`; faturas `origem` GASPAR/LOJASP/MATRIZ →
exibir **Gaspar (SC) / Filial SP / Filial PE**; joins com `CAST(chave AS VARCHAR)`.

## Workflows (`Plataforma Soul · …`) — publicados e ativos
| # | Workflow | ID | Endpoints (`/webhook/plat/…`) |
|---|---|---|---|
| 1 | **App** | `WEDZSDdlaY9Sp1NP` | `GET /plat` → serve o SPA |
| 2 | **Auth** | `dRRnEVOFNfEbyEI6` | `POST /api/login`, `POST /api/logout`, `GET /api/me` |
| 3 | **Chat** | `xIC5nmRAcGsZ4ba0` | `POST /api/chat` (guardrails → **agente text-to-SQL** na Nekt c/ auto-correção → Claude → log) |
| 4 | **Dados** | `5chCylZUGBeihSk9` | `GET /api/dashboard`, `/api/historico`, `/api/conversa`, `/api/fontes` · `POST /api/feedback`, `/api/destacar`, `/api/solicitar` |
| 5 | **Admin** | `9bcS5Fm8FlNKXMKT` | `GET /api/admin/kpis`, `/api/admin/rastreabilidade`, `/api/admin/usuarios`, `/api/admin/governanca` |

Fontes-fonte no repositório: `workflows/auth.ts`, `workflows/dados.ts`, `workflows/admin.ts`
(builder do SDK n8n) e `workflows/chat/` (código dos nós Code do agente text-to-SQL +
README do grafo). App foi construído direto no editor.

### Serviço do SPA
O workflow **App** faz `fetch` do `index.html` publicado no GitHub
(`raw.githubusercontent.com/.../plataforma-soul/frontend/index.html`, branch de trabalho)
e responde `text/html`. Um `git push` do front-end atualiza a plataforma na hora — sem
recolar HTML no n8n. (`plat_assets` era a abordagem antiga em chunks e está ociosa.)

### Autenticação
- **Login/Chat**: verificação HMAC-SHA256 completa do token (assinatura + `exp`).
- **Endpoints de dados/admin**: auth leve — decodifica o payload base64url do token,
  valida `exp` e `is_admin` (para `/admin/*`), sem reconferir a assinatura HMAC.
  Trade-off conhecido de performance; endurecer com verificação HMAC é o próximo passo.
- Token = `{usuario, nome, perfil, nivel, area, is_admin, exp}`; sessão de 8h.
- **Isolamento por usuário**: os endpoints `/dashboard`, `/historico` e `/conversa` filtram
  por `usuario` do token (um usuário só vê as próprias conversas; admin usa o toggle
  global do Histórico). No front, `resetSessionState()` limpa `state.messages`/`convId`
  e caches de histórico no login e no logout — evita que a conversa de um usuário
  apareça para outro ao trocar de login na mesma aba.

### Histórico global (admin)
Na aba **Histórico**, um usuário admin alterna entre "Minhas conversas" e
**"Todos os usuários"** — a visão global agrupa por data as conversas de toda a
organização (busca + filtro por área), reaproveitando `/api/admin/rastreabilidade`.

### Seed do histórico (`seeds/interacoes_seed.json`)
`plat_interacoes` é populada com ~190 interações realistas cobrindo ~4,5 meses
(mai–set), para os 3 reais, diretores e demais usuários: consultas de estoque
(kg), faturamento/títulos (R$), PCP, qualidade (%), pedidos e expedição, com
tokens, custo e alguns bloqueios de escopo. O arquivo é carregado por um
workflow de manutenção (Code → `fetch` do GitHub → `dataTable upsert` por `uid`);
o gerador está em `seeds/gerar_interacoes.js`. Workflows de manutenção ficam
arquivados após o uso.

## Identidade visual
- Fundo `#0b0906`/`#0e0b07`; dourado `#c9a227`/`#d4af6a`; creme `#e8dcc4`; texto claro.
- Títulos em **serifa** (display); corpo em sans. Cards de módulo com ícone fino dourado.
- Cabeçalho "PORTAL SOUL / Plataforma de Agentes". Badge ADMIN. Botões outline.
- Chat: réplica do claude.ai (composer central, bolhas, ações copiar/regenerar/👍👎). Sem anexo.
- Responsivo tablet/desktop; mobile funcional.
