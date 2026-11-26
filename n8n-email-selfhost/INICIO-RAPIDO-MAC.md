# Início rápido — n8n de e-mail no Mac

Objetivo: subir o n8n no seu Mac e **começar a disparar hoje**, só a parte de e-mail
marketing (não mexe no resto da sua instância Cloud).

---

## Pré-requisito
- **Docker Desktop** instalado e aberto (https://www.docker.com/products/docker-desktop/)

---

## FASE 1 — Subir e testar envio (10 min)

```bash
cd ~/n8n-email-selfhost
cp .env.mac.exemplo .env
openssl rand -hex 32          # copie o resultado
```

1. Abra o `.env` e:
   - cole a chave no `N8N_ENCRYPTION_KEY`
   - troque `POSTGRES_PASSWORD` por uma senha forte
2. Suba:

```bash
docker compose -f docker-compose.mac.yml up -d
```

3. Abra **http://localhost:5678** → crie a conta dona.
4. Importe os 16 workflows de e-mail (lista abaixo) e recrie a credencial do SES.
5. Rode o **"MKT · Teste de Envio (SES)"** pra confirmar que envia.

> Nesta fase o envio já funciona (o n8n chama o SES pela internet de saída).
> O que NÃO funciona ainda: tracking, bounce e descadastro (precisam da Fase 2).

---

## FASE 2 — URL pública com Cloudflare Tunnel (grátis, ~15 min)

Necessária ANTES de um disparo grande: é ela que faz o SES conseguir te avisar
de bounce/reclamação. Sem isso a Amazon pode suspender o envio.

```bash
brew install cloudflared
```

Teste imediato (URL aleatória, só pra validar):
```bash
cloudflared tunnel --url http://localhost:5678
```
Isso devolve uma URL `https://....trycloudflare.com`. Coloque ela no `.env`
(`N8N_HOST` e `WEBHOOK_URL`, Fase 2) e rode `docker compose -f docker-compose.mac.yml up -d`.

Para uma URL FIXA no seu domínio (recomendado p/ produção), use um "named tunnel"
apontando `n8n-mkt.atomtecnologia.com` → localhost:5678 (passo a passo à parte).

---

## Depois do túnel no ar, reaponte no SES/AWS:
- **SNS** (bounce/reclamação): assine o tópico com a nova URL do webhook
- **Tracking** (pixel/clique): atualize a URL base nos templates
- **Descadastro**: atualize o link de unsubscribe pra nova URL

---

## Workflows de e-mail a importar (sua lista)

### Disparo
- tkhg3COmtLuR1qIf — MKT · Disparo (fila)
- vCpQSWxMkrJL4aio — MKT · Disparo SP Tech (mkt)
- 442Sv9XPBcWs3leu — MKT · Disparo Construção Civil SC (mkt2)
- eQphTNynHTUsrfBY — MKT · Disparo Imobiliárias (vendas)
- X3eX9BzcRDx8f4h9 — MKT · Disparo Indústrias EPP (mkt1)
- tLpmHwOcrkfyfVWS — MKT · Motor de Cadência
- OFlW9KOlALO5Hl1A — MKT · Disparo em Massa (Campanha)
- 793jB2Cj9KkSHwqp — MKT · Teste de Envio (SES)

### Apoio
- ifvJZWEWF6eXiO4X — MKT · Tracking Abertura (pixel)
- 6TuyHuVlC9AmjL2I — MKT · Tracking Clique (redirect)
- nswiRhpR0B48gbPP — MKT · Bounce/Reclamação/Entrega (SES SNS)
- loXWRXSJ6F77K9Wu — MKT · Descadastro (unsubscribe)
- 0x2qkjC84dJGfCPM — MKT · Controle (pausar/retomar)
- aYMkJNVVFzGeMesm — MKT · Guardião de Cota SES
- ATLt5WZ4iEZbFKDe — MKT · Inscrever + Importar
- CYr53497NKKPM51e — MKT · Painel (Relatório)
- os6IAkCQr9bYZHmK — MKT · Guardião (corta-circuito)  [estava off]

## Data tables a migrar (dados vão à parte, não vêm no JSON)
mkt_contatos · mkt_envios_log · mkt_suppression · mkt_config · mkt_disparos ·
mkt_disparos_enviados · mkt_templates · mkt_inscricoes · mkt_cadencia_passos

⚠️ Prioridade: **mkt_suppression** e **mkt_contatos** antes de qualquer disparo.
