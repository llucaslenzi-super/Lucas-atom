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

```
1  cnpj
2  razao_social
3  nome_fantasia
4  socios                 todos os nomes, separados por ;
5  cidade
6  uf
7  telefones              TODOS os números numa coluna só, separados por ;
8  whatsapp               TODOS, separados por ;
9  emails                 TODOS numa coluna só, separados por ;
10 site
11 instagram
12 linkedin
13 facebook
-- daqui em diante, o resto do pipeline, agrupado:
   QUALIFICAÇÃO  cnae_codigo · cnae_descricao · porte · situacao · capital_social
                 faturamento · quadro_funcionarios · data_abertura · idade_anos
                 natureza_juridica · regime_tributario · opcao_simples · opcao_mei
                 importa_exporta · programas_especiais
   ENDEREÇO      logradouro · numero · complemento · bairro · cep
   DECISOR       socio_admin · socio_admin_qualificacao · socio_admin_entrada · qtd_socios
   RISCO         qtd_dividas
   AUDITORIA     fonte_telefone · fonte_email · fonte_whatsapp
                 score_site · fonte_atualizada_em · base_competencia
```

**Coluna sem nenhum valor no lote é removida da saída.** Hoje são 86 colunas e a
maioria vem vazia em lote de indústria.

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

3.5  Remover coluna 100% vazia no lote
     → verifica: lote de indústria sai com bem menos que 86 colunas,
       e nenhuma coluna removida tinha valor em alguma linha

3.6  XLSX com openpyxl: cabeçalho congelado, autofiltro, largura automática,
     CNPJ como TEXTO (senão o Excel come o zero da frente de novo)
     → verifica: abre sem aviso; filtro funciona; CNPJ 02585301000150
       aparece com o zero

3.7  PDF dossiê com reportlab: uma página por empresa
     cabeçalho (razão social, fantasia, CNPJ) · bloco contatos ·
     bloco decisor · bloco qualificação · rodapé com procedência e data
     → verifica: 6 empresas geram 6 páginas; empresa sem whatsapp mostra
       o campo vazio, não some com o bloco

3.8  CLI: --formato xlsx,csv,pdf
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
