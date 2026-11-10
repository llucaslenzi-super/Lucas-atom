# Plano de execução — backend

Documento de execução. Cada passo tem um critério de verificação objetivo.
Nada aqui é decisão em aberto: o que precisava ser decidido já está travado em §0.

Estado atual: o pipeline funciona como CLI, no Mac e em sessão de nuvem.
Base de 73,8 mi carregada, filtro em segundos, EmpresAqui a 1 req/s com cache,
Apify casando, CSV de 86 colunas saindo. Falta virar serviço.

---

## 0. Decisões travadas

| | |
|---|---|
| **Onde a base mora** | VM no Google Cloud (`apontamento-germer`), DuckDB em arquivo |
| **Exposição** | Nenhuma porta aberta — Cloudflare Tunnel, conexão de saída |
| **PDF** | Dossiê: uma página por empresa |
| **Formatos de saída** | XLSX, CSV, PDF |
| **Fila** | SQLite no próprio disco; sem servidor de banco |
| **Telefones e e-mails** | Uma coluna para cada, com **todos** os valores separados por `;`. Sem coluna de "principal" |

### Ordem das colunas (especificação do cliente)

Origem: **R** = base da Receita (local, grátis) · **E** = API EmpresAqui ·
**M** = Apify Google Maps · **I** = Apify Instagram · **C** = calculado em código.

#### Bloco 1 — Identificação (1 a 6)

| # | Coluna | Origem | O que é |
|---|---|---|---|
| 1 | `cnpj` | R | 14 dígitos, gravado como **texto** (senão o Excel come o zero da frente) |
| 2 | `razao_social` | R | Nome registrado |
| 3 | `nome_fantasia` | R | Vem vazio com frequência |
| 4 | `socios` | R·E | **Todos** os nomes, separados por `;` |
| 5 | `cidade` | R | Código do município resolvido na tabela `municipios` |
| 6 | `uf` | R | Sigla |

#### Bloco 2 — Contato (7 a 13)

Um canal por coluna, **todos** os valores dentro dela, separados por `;`.
Nenhuma coluna de "principal" — quem recebe a planilha escolhe qual usar.

| # | Coluna | Origem | Como é montada |
|---|---|---|---|
| 7 | `telefones` | R·E·M | `ddd_1+tel_1`, `ddd_2+tel_2`, `telefone_principal`, `telefones_texto` e o `phone` do Maps — tudo reduzido a dígitos e desduplicado |
| 8 | `whatsapp` | E·M | `whatsapp_principal`, `whatsapps_texto`, `whatsapps[]` do Maps |
| 9 | `emails` | R·E·M | `email` da Receita, `email_principal`, `emails_texto`, `emails[]` do Maps. Minúsculas, desduplicado |
| 10 | `site` | R·E·M | Prefixado com `https://` quando a fonte entrega sem protocolo |
| 11 | `instagram` | E·M·I | Handle normalizado (`@nome`), venha como URL ou handle cru |
| 12 | `linkedin` | E | Página da **empresa**, não de pessoa |
| 13 | `facebook` | E | URL |

#### Bloco 3 — Qualificação (14 a 26)

| # | Coluna | Origem | O que é |
|---|---|---|---|
| 14 | `cnae_codigo` | R | 7 dígitos |
| 15 | `cnae_descricao` | R | Resolvido na tabela `cnaes` |
| 16 | `cnae_secundario` | R·E | CSV de códigos, como a fonte entrega |
| 17 | `porte` | R | MICROEMPRESA · PEQUENO PORTE · MÉDIO/GRANDE · NÃO INFORMADO |
| 18 | `situacao` | R | ATIVA · SUSPENSA · INAPTA · BAIXADA · NULA |
| 19 | `data_situacao` | R | AAAA-MM-DD |
| 20 | `capital_social` | R | Número, com a vírgula decimal convertida |
| 21 | `faturamento` | E | Faixa em texto |
| 22 | `quadro_funcionarios` | E | Faixa em texto |
| 23 | `data_abertura` | R | AAAA-MM-DD |
| 24 | `idade_anos` | C | Anos inteiros desde a abertura |
| 25 | `natureza_juridica` | R | Texto pronto |
| 26 | `matriz_filial` | R | MATRIZ ou FILIAL |

#### Bloco 4 — Fiscal (27 a 31)

| # | Coluna | Origem | O que é |
|---|---|---|---|
| 27 | `regime_tributario` | E | Texto pronto |
| 28 | `opcao_simples` | R·E | S / N |
| 29 | `opcao_mei` | R·E | S / N |
| 30 | `programas_especiais` | E | Lista separada por `;` |
| 31 | `importa_exporta` | C | `SIM`/`NÃO` — verdadeiro quando `programas_especiais` contém IMPORTAÇÃO E EXPORTACAO. **É o sinalizador oficial de importador** |

#### Bloco 5 — Endereço (32 a 36)

| # | Coluna | Origem | O que é |
|---|---|---|---|
| 32 | `logradouro` | R | Tipo + nome já concatenados |
| 33 | `numero` | R | |
| 34 | `complemento` | R | Espaços duplicados colapsados — a fonte entrega `LOJA  01` |
| 35 | `bairro` | R | |
| 36 | `cep` | R | 8 dígitos, sem máscara |

#### Bloco 6 — Decisor (37 a 41)

Quem assina. Vem do quadro societário **oficial**, não de LinkedIn nem de
scraping. Por isso vem preenchido em praticamente todo lead, enquanto o LinkedIn
falha justamente na empresa pequena.

| # | Coluna | Origem | O que é |
|---|---|---|---|
| 37 | `socio_admin` | R·E | Nome de quem decide. **Regra:** o primeiro sócio cuja qualificação contenha ADMINISTRADOR, PRESIDENTE ou DIRETOR; se nenhum tiver, o primeiro da lista |
| 38 | `socio_admin_qualificacao` | R·E | Texto da qualificação (ex.: SÓCIO-ADMINISTRADOR) |
| 39 | `socio_admin_entrada` | R·E | AAAA-MM-DD de entrada na sociedade — diz há quanto tempo essa pessoa manda |
| 40 | `socio_admin_faixa_etaria` | R | Faixa decodificada (ex.: 41 A 50 ANOS) |
| 41 | `qtd_socios` | C | Quantos sócios ao todo. Um sócio é decisão rápida; muitos é conselho |

#### Bloco 7 — Risco (42 a 45)

Sinal de saúde financeira, para não gastar cadência com quem não paga.

| # | Coluna | Origem | O que é |
|---|---|---|---|
| 42 | `qtd_dividas` | E | Quantos trimestres com dívida ativa em `historicoDividasPorTrimestre`. Zero quando todos dizem NAO POSSUI |
| 43 | `divida_ultimo_trimestre` | E | Valor do trimestre mais recente, ou vazio |
| 44 | `recuperacao_judicial` | C | `SIM`/`NÃO` — verdadeiro quando `programas_especiais` contém RECUPERACAO JUDICIAL |
| 45 | `situacao_alerta` | C | `SIM` quando a situação não é ATIVA, **ou** há dívida, **ou** há recuperação judicial. Uma coluna só para filtrar no Excel sem precisar ler as outras três |

#### Bloco 8 — Auditoria (46 a 53)

De onde veio cada dado e quando. Serve para LGPD, para conferir um lead
contestado, e para saber se a base estava velha quando o lote saiu.

| # | Coluna | Origem | O que é |
|---|---|---|---|
| 46 | `fonte_telefone` | C | Qual camada entregou: `receita` · `empresaqui` · `maps` · vazio |
| 47 | `fonte_email` | C | Idem |
| 48 | `fonte_whatsapp` | C | Idem |
| 49 | `fonte_instagram` | C | Idem |
| 50 | `score_site` | E | 0 a 100 — confiança do EmpresAqui de que aquele site é mesmo daquele CNPJ |
| 51 | `fonte_atualizada_em` | E | Quando o EmpresAqui atualizou o enriquecimento daquela empresa |
| 52 | `base_competencia` | C | Competência da base da Receita usada (ex.: `2026-10`) |
| 53 | `extraido_em` | C | Data e hora em que **este lote** rodou |

**Coluna sem nenhum valor no lote é removida da saída.** Hoje são 86 colunas e a
maioria vem vazia em lote de indústria. Uma coluna com **um único** valor
preenchido permanece: o critério é vazia de verdade, não "quase vazia".

---

## 1. Topologia

```
n8n (nuvem)  ──HTTPS──>  Cloudflare Tunnel  ──>  VM GCP
   painel    ──HTTPS──>        (saída)              │
                                                    ├── api.py        FastAPI
                                                    ├── worker.py     fila 1 req/s
                                                    ├── cnpj.duckdb   16 GB
                                                    ├── jobs.sqlite   fila + log
                                                    ├── empresaqui.sqlite  cache
                                                    └── saida/        xlsx csv pdf
                                                         │
                                            EmpresAqui ──┤ (saída)
                                                 Apify ──┘
```

**Por que o túnel e não porta aberta:** `cloudflared` abre uma conexão **de dentro
para fora**. A VM não escuta em nenhuma porta pública, não entra em varredura de
internet, e não precisa de IP fixo nem de certificado. É a forma de atender ao
requisito "nada exposto" sem abrir mão de o n8n alcançar o serviço.

**Por que a API e o worker são processos separados:** o enriquecimento é 1
requisição por segundo. 300 leads são 5 minutos e nenhuma chamada HTTP espera
isso. A API responde na hora com um `job_id`; o worker trabalha por fora.

---

## 2. Preparar a VM

```
2.1  Python 3.11+ e dependências do sistema
     sudo apt-get update && sudo apt-get install -y python3.11 python3.11-venv
     → verifica: python3.11 --version responde

2.2  Usuário de serviço sem shell, dono de /opt/prospeccao
     sudo useradd -r -s /usr/sbin/nologin prospeccao
     → verifica: id prospeccao responde; o usuário não consegue login

2.3  Clonar e criar o ambiente
     /opt/prospeccao/{app,dados,saida}
     python3.11 -m venv .venv
     .venv/bin/pip install duckdb fastapi uvicorn openpyxl reportlab
     → verifica: .venv/bin/python -c "import duckdb,fastapi,openpyxl,reportlab"

2.4  Disco: a base ocupa 16 GB, os Parquet 4,7 GB
     → verifica: df -h mostra 30 GB livres ANTES da carga
     → se faltar: carregar e apagar dados/bruto (libera 4,7 GB)

2.5  Credenciais em /etc/prospeccao.env, modo 600, dono root
     EMPRESAQUI_TOKEN=... / APIFY_TOKEN=... / API_TOKEN=...
     → verifica: ls -l mostra -rw-------; nenhum token em arquivo versionado

2.6  cloudflared instalado e túnel criado
     → verifica: a URL do túnel responde 200 em /saude a partir de fora da VM
     → verifica: nmap na VM não mostra porta nova aberta
```

---

## 3. Fase 1 — Saída (não depende da VM)

Roda hoje, na CLI, no Mac. É o que o cliente usa amanhã de manhã.

```
3.1  cnpj/colunas.py — a ordem de §0 numa lista só, em um lugar só
     → verifica: 1ª linha do xlsx é
       cnpj · razao_social · nome_fantasia · socios · cidade · uf

3.2  Consolidar telefones numa coluna só: Receita(ddd_1+tel_1, ddd_2+tel_2)
     + EmpresAqui(telefone_principal, telefones_texto) + Maps(phone)
     normalizar para dígitos, desduplicar, juntar com ;
     → verifica: empresa com 3 números distintos mostra os 3, sem repetição
     → verifica: mesmo número em formatos diferentes conta uma vez
     → verifica: NÃO existe coluna telefone_principal na saída

3.3  Mesmo tratamento para emails, whatsapp e instagram — uma coluna cada,
     com todos os valores
     → verifica: idem, e sem coluna *_principal em nenhum dos três

3.4  Coluna de sócios: todos os nomes, separados por ;
     → verifica: empresa com 2 sócios mostra os 2

3.5  Bloco 6 — DECISOR (colunas 37 a 41)
     Escolher o sócio: primeiro cuja qualificação contenha ADMINISTRADOR,
     PRESIDENTE ou DIRETOR; se nenhum tiver, o primeiro da lista.
     Decodificar a faixa etária (código 4 → "31 A 40 ANOS").
     → verifica: empresa com SÓCIO-ADMINISTRADOR e SÓCIO escolhe o
       administrador, não o primeiro da lista
     → verifica: empresa só com SÓCIO simples preenche mesmo assim,
       com a qualificação que tem
     → verifica: qtd_socios bate com o número de chaves numéricas da resposta

3.6  Bloco 7 — RISCO (colunas 42 a 45)
     qtd_dividas = trimestres em historicoDividasPorTrimestre cujo valor
     NÃO seja "NAO POSSUI". divida_ultimo_trimestre = valor do mais recente.
     recuperacao_judicial e situacao_alerta derivados em código.
     → verifica: empresa com 26 trimestres todos "NAO POSSUI" dá qtd_dividas = 0
     → verifica: empresa BAIXADA marca situacao_alerta = SIM mesmo sem dívida
     → verifica: empresa ATIVA, sem dívida e sem recuperação dá
       situacao_alerta = NÃO

3.7  Bloco 8 — AUDITORIA (colunas 46 a 53)
     fonte_* preenchida na hora em que o valor é escolhido, não depois:
     quem venceu a consolidação é quem assina o campo.
     base_competencia lida de dados/competencia.txt; extraido_em é o
     instante do lote.
     → verifica: lead com telefone só da Receita marca fonte_telefone=receita
     → verifica: lead com whatsapp só do Maps marca fonte_whatsapp=maps
     → verifica: campo vazio tem fonte_* vazia — nunca uma fonte inventada
     → verifica: todos os leads do mesmo lote têm o mesmo extraido_em

3.8  Remover coluna 100% vazia no lote
     → verifica: lote de indústria sai com bem menos que 86 colunas,
       e nenhuma coluna removida tinha valor em alguma linha
     → verifica: coluna com UM único valor preenchido permanece

3.9  XLSX com openpyxl: cabeçalho congelado, autofiltro, largura automática,
     CNPJ como TEXTO (senão o Excel come o zero da frente de novo)
     → verifica: abre sem aviso; filtro funciona; CNPJ 02585301000150
       aparece com o zero

3.10 PDF dossiê com reportlab: uma página por empresa, nesta ordem —
     cabeçalho (razão social · fantasia · CNPJ · cidade/UF)
     bloco CONTATO     telefones, whatsapp, emails, site, redes
     bloco DECISOR     nome, qualificação, desde quando, nº de sócios
     bloco QUALIFICAÇÃO CNAE, porte, capital, faturamento, funcionários,
                        abertura, importa/exporta
     bloco RISCO       só aparece quando situacao_alerta = SIM
     rodapé            fonte de cada contato · competência da base · data do lote
     → verifica: 6 empresas geram 6 páginas
     → verifica: empresa sem whatsapp mostra o campo vazio, não some com o bloco
     → verifica: empresa ATIVA e sem dívida NÃO mostra o bloco de risco
     → verifica: o rodapé de cada página traz a competência da base

3.11 CLI: --formato xlsx,csv,pdf
     → verifica: um comando gera os três
```

**Biblioteca de PDF:** `reportlab`. Instala por pip e não precisa de biblioteca
do sistema. `weasyprint` renderiza melhor, mas puxa cairo e pango — peso
desnecessário numa VM para um dossiê tabular.

---

## 4. Fase 2 — Base na VM

```
4.1  Copiar o código e rodar a carga lá
     cnpj baixar --completo && cnpj carregar && cnpj conferir
     → verifica: 73.809.379 estabelecimentos; SP com 21.369.926

4.2  Abrir o DuckDB em modo somente-leitura na API
     → verifica: duas consultas simultâneas não dão erro de lock

4.3  Gravar a competência da base num arquivo ao lado
     dados/competencia.txt = "2026-10"
     → verifica: aparece na coluna base_competencia de todo lead exportado

4.4  Atualização mensal: systemd timer no dia 5
     baixa, carrega em arquivo novo, troca por renomeação, apaga o antigo
     → verifica: durante a troca a API continua respondendo
     → verifica: rodar duas vezes seguidas não duplica linha
```

**Por que renomear e não recarregar por cima:** a carga leva 15 minutos. Recarregar
no arquivo em uso derruba a API. Carregar ao lado e trocar o nome é instantâneo.

---

## 5. Fase 3 — API e fila

### Endpoints

```
GET  /saude                              → {ok, competencia, linhas}
POST /contar     {ufs,cnaes,porte,...}   → {total}
POST /buscar     {filtros,limite,ordenar}→ {empresas:[...]}
POST /jobs       {cnpjs|filtros,apify}   → {job_id}
GET  /jobs/{id}                          → {status,feitos,total,custo_usd}
GET  /jobs/{id}/arquivo?formato=xlsx     → o arquivo
```

Todos exigem `Authorization: Bearer <API_TOKEN>`, menos `/saude`.

```
5.1  api.py com os 6 endpoints
     → verifica: /contar na VM devolve 14.827 para "SC,PR + CNAE 13 + matriz",
       o mesmo número que o DuckDB local

5.2  jobs.sqlite: id, status, pedido(json), feitos, total, custo, erro,
     criado_em, concluido_em
     → verifica: POST /jobs responde em menos de 1 segundo, sem esperar o lote

5.3  worker.py: pega pendente, roda o pipeline, atualiza progresso a cada lote
     de 10, grava os 3 arquivos, marca pronto
     → verifica: GET /jobs/{id} mostra feitos subindo de 10 em 10

5.4  Retomada: matar o worker no meio e religar
     → verifica: continua do lote onde parou; o cache por CNPJ evita
       reconsultar o que já veio

5.5  Dois serviços systemd, com Restart=always e EnvironmentFile
     prospeccao-api.service · prospeccao-worker.service
     → verifica: systemctl stop/start recupera sozinho
     → verifica: reiniciar a VM sobe os dois

5.6  Autenticação
     → verifica: sem header, 401; com token errado, 401; com token certo, 200

5.7  Teto de gasto por job (--teto-usd já existe no Apify)
     → verifica: job com teto de 1 dólar para e marca o motivo, não estoura
```

### Limites que a API precisa impor

- `limite` máximo por job: **1.000**. Acima disso são mais de 17 minutos a 1 req/s.
- Um job em execução por vez. O segundo espera na fila.
- Job com mais de 2 horas vira `expirado`.

---

## 6. Fase 4 — n8n

```
6.1  Credencial httpHeaderAuth com o API_TOKEN
     → verifica: chamada de teste ao /saude volta 200

6.2  Workflow "Prospecção · Buscar" → POST /buscar
     → verifica: executa e devolve a lista

6.3  Workflow "Prospecção · Enriquecer"
     cria job → agenda a cada 1 min → verifica status → baixa quando pronto
     → verifica: 50 leads do início ao fim sem intervenção

6.4  Gravar na tabela de contatos com origem nova (ex.: industria-sc-tex)
     → verifica: Motor de Cadência enxerga e dispara
     (mesmo encaixe que o workflow "Enriquecimento Nome (Receita)" já usa)

6.5  Agent com as ferramentas buscar / enriquecer / status / baixar
     → verifica: "indústrias têxteis de SC, 200 empresas" roda ponta a ponta
```

**Observação:** o workflow `MKT · Enriquecimento Nome (Receita)` consulta a
BrasilAPI um CNPJ por vez só para pegar o nome do sócio. Com a base local isso
vem junto, de graça e em massa. Ele fica obsoleto — está desativado, não mexer
sem combinar.

---

## 7. Fase 5 — Auditoria e testes

```
7.1  Log por lote em jobs.sqlite:
     filtro usado · nº de CNPJs · requisições gastas · acertos de cache ·
     custo Apify · duração · competência da base · versão do código
     → verifica: dado um lead, reconstruir de qual lote e filtro ele veio

7.2  Procedência por campo, cobrindo também Maps e Instagram
     → verifica: toda célula de contato preenchida tem fonte_* correspondente

7.3  Suíte de testes (pytest) nos pontos que falham em silêncio:
     - dígito verificador: válido, inválido, zero comido, pontuado, repetido
     - leitura de .xlsx nos 4 formatos do Excel (texto, número, número sem
       zero, com pontuação) — foi onde achamos o bug de 2 em 6
     - casamento por nome: WEG casa a 0,93; "Lazos" NÃO casa com
       "Frigorífico Los Lazos"
     - desduplicação por CNPJ
     - ordem das colunas bate com §0
     - coluna vazia é removida, coluna com um único valor NÃO é
     → verifica: suíte passa; quebrar o parser de propósito faz falhar

7.4  Teste ponta a ponta contra a VM
     filtro → job → 3 formatos
     → verifica: um comando só, do filtro ao PDF

7.5  Teste de carga mínimo: 3 jobs enfileirados
     → verifica: processa em ordem, nenhum perde resultado
```

---

## 8. Ordem de execução

```
FASE 1 (saída)        ───────────────────  não depende da VM, entrega valor hoje
FASE 5.3 (testes)     ───────────────────  pode vir junto
         │
         ▼
FASE 2 (base na VM)   ───────────────────  2.1 … 2.6 antes de qualquer coisa
         │
         ▼
FASE 3 (API e fila)
         │
         ▼
FASE 4 (n8n)
         │
         ▼
FASE 5 (auditoria, 7.4 e 7.5)
```

---

## 9. Riscos conhecidos

| Risco | Impacto | O que fazer |
|---|---|---|
| Teto do Apify no plano FREE (US$5/mês) | Para de enriquecer no meio | Monitorar em /jobs; subir de plano ou cortar Apify por lote |
| Troca mensal da base muda nome de coluna | Carrega sem erro e fica trocado | `conferir` é obrigatório após toda carga; comparar contagem por UF |
| Token do EmpresAqui rotacionado | 401 em todo job | O worker aborta no 401 e marca o motivo; não tenta de novo |
| Disco cheio na VM durante a troca mensal | Carga falha | Checar 30 GB livres antes; apagar `dados/bruto` após conferir |
| VM reiniciada | Serviço fora do ar | `Restart=always` + habilitar no boot (5.5) |
| LinkedIn nunca foi executado | Desconhecido | Fora do escopo deste plano; só entra depois de um teste real |

---

## 10. Fora de escopo, de propósito

- LLM em qualquer ponto do caminho do dado
- Google Places (a Receita já é a fonte oficial)
- Interface web própria (o painel publicado e o n8n cobrem)
- Multi-usuário, cotas por cliente, cobrança
- Postgres ou qualquer servidor de banco
