#!/bin/bash
# Agente de Prospecção Misner — instalação da VM.
#
# Vai no campo "Script de inicialização" (Automação) ao criar a VM.
# Roda como root, uma vez, no primeiro boot. Nenhum SSH é necessário.
#
# Metadata esperada na instância:
#   empresaqui-token · apify-token · api-token · cloudflare-tunnel-token (opcional)
set -euo pipefail
exec > >(tee -a /var/log/misner-install.log) 2>&1
echo "=== instalação Misner — $(date -Is) ==="

SLUG=misner
RAIZ=/opt/$SLUG
APP=$RAIZ/repo/prospeccao
REPO=https://github.com/llucaslenzi-super/Lucas-atom
BRANCH=claude/relaxed-bardeen-lukpvm

# 1 ─ sistema
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git curl

# 2 ─ usuário de serviço, sem shell
id -u $SLUG &>/dev/null || useradd -r -s /usr/sbin/nologin -d $RAIZ $SLUG

# 3 ─ código (repositório público: sem credencial)
mkdir -p $RAIZ
if [ -d $RAIZ/repo/.git ]; then
  git -C $RAIZ/repo fetch --depth 1 origin $BRANCH
  git -C $RAIZ/repo reset --hard FETCH_HEAD
else
  git clone --depth 1 -b $BRANCH $REPO $RAIZ/repo
fi

# 4 ─ ambiente Python
python3 -m venv $RAIZ/venv
$RAIZ/venv/bin/pip install -q --upgrade pip
$RAIZ/venv/bin/pip install -q -r $APP/requirements.txt

# 5 ─ segredos, vindos da metadata da instância
META=http://metadata.google.internal/computeMetadata/v1/instance/attributes
meta() { curl -sf -H "Metadata-Flavor: Google" "$META/$1" || true; }
umask 077
cat > /etc/$SLUG.env <<EOF
EMPRESAQUI_TOKEN=$(meta empresaqui-token)
APIFY_TOKEN=$(meta apify-token)
API_TOKEN=$(meta api-token)
CNPJ_DADOS=$RAIZ/dados
CNPJ_SAIDA=$RAIZ/saida
EOF
chmod 600 /etc/$SLUG.env
# Restaura o umask: sem isto ele vaza para o resto do script e os arquivos de
# unidade nascem com modo 600. O systemd le (e root), mas quem for depurar
# leva "Permission denied" num `grep` e perde tempo atras de um problema que
# nao existe.
umask 022
# Dono root de propósito: o systemd lê o arquivo ANTES de descer para User=,
# então o usuário de serviço não precisa — e não deve — conseguir lê-lo.

# 6 ─ diretórios de trabalho
mkdir -p $RAIZ/dados $RAIZ/saida $RAIZ/tmp
chown -R $SLUG:$SLUG $RAIZ/dados $RAIZ/saida $RAIZ/tmp

# 7 ─ unidades systemd
_comum() { cat <<EOF
User=$SLUG
Group=$SLUG
EnvironmentFile=/etc/$SLUG.env
WorkingDirectory=$APP
NoNewPrivileges=yes
ProtectSystem=strict
ProtectHome=yes
PrivateTmp=yes
ReadWritePaths=$RAIZ/dados $RAIZ/saida $RAIZ/tmp
EOF
}

cat > /etc/systemd/system/$SLUG-base.service <<EOF
[Unit]
Description=Misner · carga da base da Receita
After=network-online.target
Wants=network-online.target
[Service]
Type=oneshot
RemainAfterExit=yes
TimeoutStartSec=7200
$(_comum)
# montar, nao baixar+carregar: baixa, carrega e apaga UM arquivo por vez.
# Carregar os 10 arquivos de uma vez levou o pico de memoria alem do 1 GB da
# maquina e o kernel matou a carga (oom-kill, medido na VM em 11/11).
ExecStart=$RAIZ/venv/bin/python -m cnpj montar
ExecStart=$RAIZ/venv/bin/python -m cnpj conferir
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/$SLUG-api.service <<EOF
[Unit]
Description=Misner · API
After=network-online.target
[Service]
Restart=always
RestartSec=5
$(_comum)
ExecStart=$RAIZ/venv/bin/uvicorn servico.api:app --host 127.0.0.1 --port 8080 --workers 1
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/$SLUG-worker.service <<EOF
[Unit]
Description=Misner · worker de enriquecimento
After=$SLUG-api.service
[Service]
Restart=always
RestartSec=10
$(_comum)
ExecStart=$RAIZ/venv/bin/python servico/worker.py
[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/$SLUG-base.timer <<EOF
[Unit]
Description=Misner · atualização mensal da base
[Timer]
OnCalendar=*-*-05 03:00:00
Persistent=true
[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl enable --now $SLUG-api $SLUG-worker
systemctl enable $SLUG-base.timer
systemctl start --no-block $SLUG-base    # ~40 min; não bloqueia o boot

# 8 ─ túnel Cloudflare, se houver token
TUNEL=$(meta cloudflare-tunnel-token)
if [ -n "$TUNEL" ]; then
  mkdir -p /usr/share/keyrings
  curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg \
    -o /usr/share/keyrings/cloudflare-main.gpg
  echo "deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main" \
    > /etc/apt/sources.list.d/cloudflared.list
  apt-get update -qq && apt-get install -y -qq cloudflared
  cloudflared service install "$TUNEL"
  echo "túnel instalado"
else
  echo "sem token de túnel — a API escuta só em 127.0.0.1:8080"
fi

echo "=== concluído — $(date -Is) ==="
echo "acompanhe a base:  journalctl -u $SLUG-base -f     (~40 min)"
echo "estado:            systemctl status $SLUG-api $SLUG-worker"
