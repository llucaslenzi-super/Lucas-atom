# Plano — n8n de e-mail na VM do Google Cloud

Objetivo: subir o n8n **só do e-mail marketing** numa VM do Google Cloud, com IP
público e HTTPS automático. Sem limite de execução, sempre ligado, sem túnel.

- **Máquina:** e2-small (2 vCPU burst, 2 GB RAM) — auditado, aguenta o marketing
- **Região:** southamerica-east1 (São Paulo)
- **Custo:** ~US$ 13–15/mês fixo (+ ~US$ 1 de disco)
- **Domínio:** n8n-mkt.atomtecnologia.com (ajuste se quiser outro)

---

## PASSO 1 — Criar a VM (no seu Google Cloud)

Abra o **Cloud Shell** (ícone `>_` no topo do console) e rode. Ajuste `PROJECT`:

```bash
export PROJECT=SEU_PROJECT_ID
export REGION=southamerica-east1
export ZONE=southamerica-east1-a
export VM=n8n-mkt
gcloud config set project $PROJECT

# IP estático (pra o DNS não quebrar se a VM reiniciar)
gcloud compute addresses create ${VM}-ip --region $REGION
gcloud compute addresses describe ${VM}-ip --region $REGION --format='value(address)'
#  >>> ANOTE O IP QUE APARECER <<<

# Criar a VM
gcloud compute instances create $VM \
  --zone $ZONE \
  --machine-type e2-small \
  --image-family debian-12 --image-project debian-cloud \
  --boot-disk-size 20GB --boot-disk-type pd-balanced \
  --address ${VM}-ip \
  --tags http-server,https-server

# Liberar portas 80 e 443
gcloud compute firewall-rules create allow-web \
  --allow tcp:80,tcp:443 \
  --target-tags http-server,https-server \
  --direction INGRESS --network default 2>/dev/null || true
```

---

## PASSO 2 — Apontar o DNS

No painel do seu domínio (onde gerencia `atomtecnologia.com`), crie um registro:

```
Tipo: A
Nome: n8n-mkt
Valor: <IP estático que você anotou>
TTL: 300
```

(O certificado HTTPS é emitido sozinho pelo Caddy depois que o DNS propagar.)

---

## PASSO 3 — Entrar na VM e preparar

```bash
gcloud compute ssh $VM --zone $ZONE
```

Dentro da VM:

```bash
# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# saia (exit) e entre de novo com 'gcloud compute ssh' pra valer o grupo

# Swap de 2 GB (colchão de segurança pra 2 GB de RAM — evita travar no pico)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## PASSO 4 — Subir o n8n

Na VM, crie a pasta e os arquivos (`docker-compose.yml` e `Caddyfile` são os do
repositório / que te enviei):

```bash
mkdir -p ~/n8n-email && cd ~/n8n-email
# cole aqui o docker-compose.yml e o Caddyfile (nano arquivo, cola, Ctrl+O, Ctrl+X)

# cria o .env
cat > .env <<'EOF'
POSTGRES_USER=n8n
POSTGRES_PASSWORD=TROQUE_SENHA_FORTE
POSTGRES_DB=n8n
N8N_ENCRYPTION_KEY=COLE_A_CHAVE
N8N_HOST=n8n-mkt.atomtecnologia.com
EOF

openssl rand -hex 32     # copie e cole no N8N_ENCRYPTION_KEY do .env
nano .env                # ajuste senha + chave

docker compose up -d
docker compose logs -f caddy   # veja o certificado HTTPS ser emitido
```

Abra **https://n8n-mkt.atomtecnologia.com** → crie a conta dona.

---

## PASSO 5 — Ligar a API (pra eu controlar daqui)

Dentro do n8n: **Settings → n8n API → Create an API key**.
Me manda **a URL + a API Key** que eu assumo o controle daqui.

---

## PASSO 6 — Migração (eu faço a maior parte via API)

1. **Workflows (16):** exporto da Cloud e importo na VM
2. **Credenciais SES:** você reinsere (não migram por segurança)
3. **9 data tables:** migro de uma instância pra outra via API
   - ⚠️ `mkt_suppression` e `mkt_contatos` ANTES de qualquer disparo
4. **Reapontar no SES/AWS:**
   - SNS (bounce/reclamação) → novo webhook `https://n8n-mkt.atomtecnologia.com/...`
   - Tracking (pixel/clique) → nova URL base nos templates
   - Descadastro (unsubscribe) → nova URL
5. **Guardião de Cota SES** + kill_switch conferidos antes de ligar os disparos

---

## Manutenção (simples)

```bash
cd ~/n8n-email
docker compose pull && docker compose up -d   # atualizar n8n
docker compose logs -f n8n                     # ver logs
docker exec -t $(docker compose ps -q postgres) pg_dump -U n8n n8n > backup_$(date +%F).sql  # backup
```
