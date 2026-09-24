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
> - **3 usuários reais + 12 mocks** (indistinguíveis na interface).

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

## Guardrails (automáticos, backend)
- **PII**: mascara CPF, CNPJ, RG, telefone antes de ir ao Claude. **Nome de cliente
  é mantido** (mascarar tornaria a resposta comercial inútil).
- **Financeiro estrutural**: o perfil Industrial não recebe ferramentas com R$; qualquer
  valor monetário é convertido/removido (kg e % apenas).
- **Bloqueio por palavra-chave**: salário/folha, custo unitário — respondido com
  mensagem explicativa. Ficha técnica/`percfio` = **restrito** (Industrial pode usar;
  configurável na matriz de dados).
- Toda ativação de guardrail é registrada em `plat_interacoes.guardrails` + `alerta`.

## Mapa Nekt por ferramenta (fonte: cliente; confirmar colunas via information_schema)
Camadas: `nekt_raw.mssql_{gaspar|loja_sp|matriz}_dbo_*` (cru por filial) · `nekt_service`/`nekt_trusted` (views curadas).

| Ferramenta (chat) | Fonte principal | Perfil |
|---|---|---|
| consultar_estoque_produto | `mssql_gaspar_dbo_estoque_nr_peca` + `produtos` + `grade_produtos` | Industrial |
| status_op_tinturaria | view `gaspar_pcp_tinturaria_resposta1_nivel_1` | Industrial |
| status_op_tecelagem | `mssql_gaspar_dbo_op_tecelagem` + view `gaspar_pcp_tecelagem_resposta3_nivel_2` | Industrial |
| cobertura_fio | `estoque_local` + `movimentos_estoque` + `op_tecelagem_entrada_fios` | Industrial |
| pedidos_em_aberto | `mssql_{filial}_dbo_pedidos_venda_capa/itens` | Industrial |
| reclamacoes_produto | `atendimento` + `atendimento_itens` + `defeitos` | Industrial |
| faturamento | `nekt_service.faturas_unificadas_completo` | Financeiro (Industrial só kg/%) |
| contas_pagar / titulos_vencidos | `mssql_{filial}_dbo_cp_documentos` | Financeiro |
| contas_receber | `mssql_{filial}_dbo_cr_documentos` | Financeiro |

Armadilhas travadas no SQL: `estoque_nr_peca.situacao=1` (real); Qualidade A `codlocal IN (1,55) AND revisao=1`;
pedidos espelho (`codtipopedido=1 AND codcliente=1` PE; `codtipopedido=2 AND codcliente=3085`) excluídos;
clientes internos `1,157,3085,3377,22745,22748` excluídos; `dataemissao` em UTC (`DATE(SUBSTR(...,1,10))`);
faturas `origem` GASPAR/LOJASP/MATRIZ → exibir **Gaspar (SC) / Filial SP / Filial PE**.

## Workflows (`Plataforma Soul · …`) — publicados e ativos
| # | Workflow | ID | Endpoints (`/webhook/plat/…`) |
|---|---|---|---|
| 1 | **App** | `WEDZSDdlaY9Sp1NP` | `GET /plat` → serve o SPA |
| 2 | **Auth** | `dRRnEVOFNfEbyEI6` | `POST /api/login`, `POST /api/logout`, `GET /api/me` |
| 3 | **Chat** | `xIC5nmRAcGsZ4ba0` | `POST /api/chat` (guardrails → RAG Nekt → Claude → log) |
| 4 | **Dados** | `5chCylZUGBeihSk9` | `GET /api/dashboard`, `/api/historico`, `/api/conversa`, `/api/fontes` · `POST /api/feedback`, `/api/destacar`, `/api/solicitar` |
| 5 | **Admin** | `9bcS5Fm8FlNKXMKT` | `GET /api/admin/kpis`, `/api/admin/rastreabilidade`, `/api/admin/usuarios`, `/api/admin/governanca` |

Fontes-fonte no repositório: `workflows/auth.ts`, `workflows/dados.ts`, `workflows/admin.ts`
(builder do SDK n8n). Chat e App foram construídos direto no editor.

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

## Identidade visual
- Fundo `#0b0906`/`#0e0b07`; dourado `#c9a227`/`#d4af6a`; creme `#e8dcc4`; texto claro.
- Títulos em **serifa** (display); corpo em sans. Cards de módulo com ícone fino dourado.
- Cabeçalho "PORTAL SOUL / Plataforma de Agentes". Badge ADMIN. Botões outline.
- Chat: réplica do claude.ai (composer central, bolhas, ações copiar/regenerar/👍👎). Sem anexo.
- Responsivo tablet/desktop; mobile funcional.
