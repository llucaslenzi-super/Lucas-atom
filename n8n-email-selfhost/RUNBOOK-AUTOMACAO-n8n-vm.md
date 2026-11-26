# RUNBOOK — Automatizar n8n de e-mail numa VM do Google Cloud

> **Para quem executa:** este documento é autossuficiente. Execute os passos em
> ordem. Cada passo tem comandos prontos e critério de verificação ("✔ Confirme").
> Pare e reporte se um "✔ Confirme" falhar. Não pule o Passo 8 (SES) nem o Passo 11
> (segurança). Idioma dos comandos: bash.

---

## 0. Objetivo

Tirar **somente o e-mail marketing** da instância n8n Cloud (que está estourando o
limite de 50 mil execuções/mês) e colocá-lo numa VM própria no Google Cloud, onde
**não há limite de execução**. O resto da instância Cloud (financeiro, PCP, SaaS,
etc.) **permanece no Cloud, intocado**. No fim, os disparos rodam da VM nova.

---

## 1. Acessos necessários (garanta antes de começar)

- **Google Cloud** logado no projeto **"My First Project"**
  (id começa com `project-87b83a56-...`). Já existem 3 VMs nele.
- **DNS** do domínio `atomtecnologia.com` (onde criar um registro A).
- **n8n Cloud**: `https://atomtecnologia.app.n8n.cloud` — precisa de uma **API Key**
  (gere em *Settings → n8n API → Create an API key*). **Não reutilize chave que
  tenha circulado em chat; gere uma nova e revogue a antiga.**
- **AWS Console** com acesso ao **SES** e **SNS** (os disparos usam Amazon SES).

## 2. Dados fixos do projeto

| Item | Valor |
|---|---|
| Região | `southamerica-east1` |
| Zona | `southamerica-east1-a` |
| Nome da VM | `n8n-mkt` |
| Máquina | `e2-small` (2 GB) — suficiente só p/ marketing |
| Domínio novo | `n8n-mkt.atomtecnologia.com` |
| Instância origem (Cloud) | `https://atomtecnologia.app.n8n.cloud/api/v1` |
| Header da API n8n | `X-N8N-API-KEY: <sua_api_key>` |
| Remetentes SES | lucas@mkt · lucas@mkt1 · lucas@mkt2 · lucas@contato · lucas@vendas (.atomtecnologia.com) |

### Workflows de e-mail a migrar (16 + 1 off)
```
Disparo:
  tkhg3COmtLuR1qIf  MKT · Disparo (fila)
  vCpQSWxMkrJL4aio  MKT · Disparo SP Tech (mkt)
  442Sv9XPBcWs3leu  MKT · Disparo Construção Civil SC (mkt2)
  eQphTNynHTUsrfBY  MKT · Disparo Imobiliárias (vendas)
  X3eX9BzcRDx8f4h9  MKT · Disparo Indústrias EPP (mkt1)
  tLpmHwOcrkfyfVWS  MKT · Motor de Cadência
  OFlW9KOlALO5Hl1A  MKT · Disparo em Massa (Campanha)
  793jB2Cj9KkSHwqp  MKT · Teste de Envio (SES)
Apoio:
  ifvJZWEWF6eXiO4X  MKT · Tracking Abertura (pixel)
  6TuyHuVlC9AmjL2I  MKT · Tracking Clique (redirect)
  nswiRhpR0B48gbPP  MKT · Bounce/Reclamação/Entrega (SES SNS)
  loXWRXSJ6F77K9Wu  MKT · Descadastro (unsubscribe)
  0x2qkjC84dJGfCPM  MKT · Controle (pausar/retomar)
  aYMkJNVVFzGeMesm  MKT · Guardião de Cota SES
  ATLt5WZ4iEZbFKDe  MKT · Inscrever + Importar
  CYr53497NKKPM51e  MKT · Painel (Relatório)
  os6IAkCQr9bYZHmK  MKT · Guardião (corta-circuito)  [estava off]
```

### Data tables a migrar (9) — nomes exatos
```
mkt_contatos  mkt_envios_log  mkt_suppression  mkt_config  mkt_disparos
mkt_disparos_enviados  mkt_templates  mkt_inscricoes  mkt_cadencia_passos
```
⚠️ Ordem de prioridade: **mkt_suppression** e **mkt_contatos** primeiro.

---

## 3. PASSO 1 — Criar a VM (Google Cloud Shell)

Abra o **Cloud Shell** (ícone `>_` no topo do console) e rode. O Cloud Shell já
aponta pro projeto atual, então não precisa setar project id.

```bash
REGION=southamerica-east1; ZONE=southamerica-east1-a; VM=n8n-mkt
gcloud compute addresses create ${VM}-ip --region $REGION
gcloud compute instances create $VM --zone $ZONE \
  --machine-type e2-small \
  --image-family debian-12 --image-project debian-cloud \
  --boot-disk-size 20GB --boot-disk-type pd-balanced \
  --address ${VM}-ip --tags http-server,https-server
gcloud compute firewall-rules create allow-web \
  --allow tcp:80,tcp:443 --target-tags http-server,https-server \
  --direction INGRESS --network default || true
echo "IP DA VM:"; gcloud compute addresses describe ${VM}-ip --region $REGION --format='value(address)'
```
✔ **Confirme:** anote o **IP** impresso no final. A VM aparece como "em execução"
em Compute Engine → Instâncias.

---

## 4. PASSO 2 — DNS

No painel DNS de `atomtecnologia.com`, crie:
```
Tipo: A   |   Nome: n8n-mkt   |   Valor: <IP da VM>   |   TTL: 300
```
✔ **Confirme:** `dig +short n8n-mkt.atomtecnologia.com` (ou nslookup) retorna o IP.
Pode levar alguns minutos pra propagar.

---

## 5. PASSO 3 — Entrar na VM, instalar Docker e swap

```bash
gcloud compute ssh n8n-mkt --zone southamerica-east1-a
```
Dentro da VM:
```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# swap de 2 GB (colchão p/ 2 GB de RAM)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
exit
```
Reentre pra valer o grupo docker: `gcloud compute ssh n8n-mkt --zone southamerica-east1-a`
✔ **Confirme:** `docker ps` roda sem sudo e sem erro.

---

## 6. PASSO 4 — Criar os arquivos e subir o n8n

Na VM:
```bash
mkdir -p ~/n8n-email && cd ~/n8n-email

cat > docker-compose.yml <<'YAML'
services:
  postgres:
    image: postgres:16-alpine
    restart: always
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}']
      interval: 10s
      timeout: 5s
      retries: 10
  n8n:
    image: n8nio/n8n:latest
    restart: always
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: ${POSTGRES_DB}
      DB_POSTGRESDB_USER: ${POSTGRES_USER}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD}
      N8N_ENCRYPTION_KEY: ${N8N_ENCRYPTION_KEY}
      N8N_HOST: ${N8N_HOST}
      N8N_PROTOCOL: https
      N8N_PORT: 5678
      WEBHOOK_URL: https://${N8N_HOST}/
      N8N_EDITOR_BASE_URL: https://${N8N_HOST}/
      EXECUTIONS_DATA_PRUNE: "true"
      EXECUTIONS_DATA_MAX_AGE: "168"
      EXECUTIONS_DATA_PRUNE_MAX_COUNT: "10000"
      N8N_PUBLIC_API_DISABLED: "false"
      GENERIC_TIMEZONE: America/Sao_Paulo
      TZ: America/Sao_Paulo
      N8N_RUNNERS_ENABLED: "true"
      N8N_DIAGNOSTICS_ENABLED: "false"
      N8N_HIRING_BANNER_ENABLED: "false"
    volumes:
      - n8n_data:/home/node/.n8n
    expose:
      - 5678
  caddy:
    image: caddy:2-alpine
    restart: always
    depends_on:
      - n8n
    environment:
      N8N_HOST: ${N8N_HOST}
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
volumes:
  postgres_data:
  n8n_data:
  caddy_data:
  caddy_config:
YAML

cat > Caddyfile <<'CADDY'
{$N8N_HOST} {
	reverse_proxy n8n:5678
}
CADDY

# .env com senha e chave geradas automaticamente
cat > .env <<EOF
POSTGRES_USER=n8n
POSTGRES_PASSWORD=$(openssl rand -hex 16)
POSTGRES_DB=n8n
N8N_ENCRYPTION_KEY=$(openssl rand -hex 32)
N8N_HOST=n8n-mkt.atomtecnologia.com
EOF

echo ">>> GUARDE ESTA CHAVE (abre as credenciais; se perder, perde as credenciais):"
grep N8N_ENCRYPTION_KEY .env

docker compose up -d
docker compose logs -f caddy   # aguarde o certificado HTTPS; Ctrl+C quando ver 'certificate obtained'
```
✔ **Confirme:** abrir `https://n8n-mkt.atomtecnologia.com` carrega a tela de criação
de conta do n8n (cadeado verde). **Salve a N8N_ENCRYPTION_KEY** num cofre.

---

## 7. PASSO 5 — Conta dona + API Key da VM

1. Na URL acima, crie a conta **owner** (e-mail + senha fortes).
2. *Settings → n8n API → Create an API key* → guarde a key da **VM nova**.
   - Base da API da VM: `https://n8n-mkt.atomtecnologia.com/api/v1`

---

## 8. PASSO 6 — Migrar os 16 workflows (via API)

Para cada ID da lista do Passo 2, exporte da origem e importe no destino.
Defina as variáveis e rode o laço (no Cloud Shell ou em qualquer máquina com `curl`+`jq`):

```bash
SRC="https://atomtecnologia.app.n8n.cloud/api/v1"
DST="https://n8n-mkt.atomtecnologia.com/api/v1"
SRC_KEY="<API_KEY_DO_CLOUD>"      # gere nova; não use chave vazada
DST_KEY="<API_KEY_DA_VM>"

IDS="tkhg3COmtLuR1qIf vCpQSWxMkrJL4aio 442Sv9XPBcWs3leu eQphTNynHTUsrfBY X3eX9BzcRDx8f4h9 tLpmHwOcrkfyfVWS OFlW9KOlALO5Hl1A 793jB2Cj9KkSHwqp ifvJZWEWF6eXiO4X 6TuyHuVlC9AmjL2I nswiRhpR0B48gbPP loXWRXSJ6F77K9Wu 0x2qkjC84dJGfCPM aYMkJNVVFzGeMesm ATLt5WZ4iEZbFKDe CYr53497NKKPM51e os6IAkCQr9bYZHmK"

mkdir -p wf && cd wf
for id in $IDS; do
  curl -s -H "X-N8N-API-KEY: $SRC_KEY" "$SRC/workflows/$id" -o "$id.json"
  # limpa campos que não devem ir no POST (id, tags, active, metadados)
  jq '{name, nodes, connections, settings, staticData}' "$id.json" > "$id.clean.json"
  curl -s -X POST -H "X-N8N-API-KEY: $DST_KEY" -H "Content-Type: application/json" \
       --data @"$id.clean.json" "$DST/workflows" | jq '.id, .name'
done
```
> Observação: campos aceitos pelo POST /workflows podem variar por versão do n8n.
> Se a API recusar algum campo, ajuste o `jq` (mantenha ao menos name/nodes/connections/settings).
> Alternativa manual: no n8n origem, *⋯ → Download* de cada workflow e *Import from File*
> no n8n da VM.

✔ **Confirme:** os 17 workflows aparecem no n8n da VM (deixe-os **desativados** por ora).

---

## 9. PASSO 7 — Migrar as 9 data tables (dados)

Os dados das Data Tables **não vêm** no JSON do workflow. Migre à parte.
Método recomendado: para cada tabela, (a) crie a tabela no destino com as mesmas
colunas, (b) leia as linhas da origem, (c) insira no destino.

Faça **mkt_suppression** e **mkt_contatos** primeiro. Use a API de Data Tables do n8n
(ou as ferramentas MCP do n8n, se o executor tiver: `get_data_table_rows` na origem →
`create_data_table` + `add_data_table_rows` no destino).

Esboço com API (confirme os endpoints na versão do n8n; a API de Data Tables é recente):
```bash
# Listar tabelas da origem e achar os IDs das mkt_*
curl -s -H "X-N8N-API-KEY: $SRC_KEY" "$SRC/data-tables" | jq '.data[] | select(.name|startswith("mkt_")) | {id,name}'
# Para cada tabela: puxar linhas paginando e inserir no destino em lotes
```
> Se a API de Data Tables não estiver disponível na versão, use a rota MCP do n8n
> (ferramentas `*_data_table_*`) que o executor pode ter, ou exporte via um workflow
> temporário (nó "Data Table → Get rows" → "HTTP Request → destino").

✔ **Confirme:** contagem de linhas igual origem↔destino em cada mkt_*, com
`mkt_suppression` idêntica (zero e-mails perdidos).

---

## 10. PASSO 8 — Recriar credenciais SES e reapontar AWS

1. **Credenciais SES no n8n da VM:** recrie a credencial do Amazon SES/SMTP
   (chaves IAM) — credenciais **não migram** por segurança. Teste com um envio.
2. **SNS (bounce/reclamação/entrega):** no AWS SNS, troque (ou adicione) a assinatura
   HTTPS do tópico para o webhook do workflow *Bounce/Reclamação* na nova URL:
   `https://n8n-mkt.atomtecnologia.com/webhook/<path-do-workflow>`. Confirme a
   subscrição (o n8n precisa responder ao `SubscriptionConfirmation`).
3. **Tracking (pixel/clique):** atualize a URL base nos templates/HTML para a nova URL
   (`https://n8n-mkt.atomtecnologia.com/...`). E-mails já enviados continuam batendo
   na URL antiga — normal; vale só pra novos envios.
4. **Descadastro (unsubscribe):** atualize o link de opt-out para a nova URL.
5. **Guardião de Cota SES** e **kill_switch** (`mkt_config`): confirme que leem as
   tabelas migradas e começam **destravados/na contagem certa**.

✔ **Confirme:** um e-mail de teste (workflow *Teste de Envio*) chega; um bounce de
teste (endereço `bounce@simulator.amazonses.com`) é registrado em `mkt_envios_log`
via SNS; abrir o e-mail registra em tracking.

---

## 11. PASSO 9 — Go-live

1. Na instância **Cloud antiga**, mantenha os disparos **desligados** (já estão).
2. No n8n da **VM**, **ative** primeiro os de apoio (tracking, SNS, unsubscribe,
   controle, guardião) e depois os de disparo.
3. Faça um disparo **pequeno de teste** (poucos contatos) e verifique envio, tracking,
   bounce e unsubscribe ponta a ponta antes de soltar campanha grande.

## 12. Manutenção
```bash
cd ~/n8n-email
docker compose pull && docker compose up -d           # atualizar
docker compose logs -f n8n                             # logs
docker exec -t $(docker compose ps -q postgres) pg_dump -U n8n n8n > ~/backup_$(date +%F).sql  # backup
```

## 13. Segurança (NÃO PULE)
- **Rotacione** qualquer API Key do n8n que tenha aparecido em chat/documento
  (gere nova em Settings → API e revogue a antiga), na origem **e** no destino.
- Guarde `N8N_ENCRYPTION_KEY` e a senha do Postgres num cofre; sem a encryption key
  você perde as credenciais salvas.
- Não deixe a porta 5678 exposta direto (o Caddy já cuida; só 80/443 abertos).

---

### Resumo do fluxo
Criar VM → DNS → Docker+swap → subir n8n/Postgres/Caddy → conta+API → migrar 16
workflows → migrar 9 tabelas → recriar SES + reapontar SNS/tracking/unsubscribe →
testar → go-live. Resultado: disparos rodando da VM, **sem limite de execução**,
o resto da empresa intocado no Cloud.
