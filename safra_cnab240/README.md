# Safra CNAB 240 — Homologação SOUL INDUST 355

Código de suporte à emissão de boletos Safra Cobrança Direta via CNAB 240 layout 103 (agosto/2026).

## Arquivos

**Python (referência + geração offline):**
- `config.py` — constantes Safra Matriz (CNPJ, ag/conta, carteira, layout)
- `titulos.py` — 3 títulos de teste homologação
- `cnab240.py` — gerador REM (entrada 01, baixa 02, alt venc 06, alt dados 31, protesto 09, sustar 10) + Segmentos P/Q/R
- `retorno.py` — parser .RET (Segmentos T + U) + classificador de eventos
- `boleto.py` — gerador PDF do boleto (reportlab, CB44 + LD)
- `main.py` — orquestração local (gera REM + PDFs + valida)
- `retorno_gerar_sample.py` — gera .RET fictício pra testar parser

**JavaScript (embutido no n8n Code node):**
- `safra_cnab240.js` — porta JS do cnab240.py + retorno.py + boleto (CB44/LD só). Usado pelo workflow `Agente Boletos Safra` (n8n id `r9fmhgLvcP58xm0u`)

**Testes:**
- `test_full_bit_a_bit.js` — valida Python↔JS bit-a-bit (6 remessas + parser retorno)
- `test_js_vs_py.js` — teste antigo (só entrada)

**n8n workflow generator:**
- `build_workflow.py` — gera o `.js` do workflow SDK com a lib inline
- `workflow_agente_safra.js` — código do workflow SDK (gerado)

## Workflow n8n

- ID: `r9fmhgLvcP58xm0u`
- Nome: `Agente Boletos Safra`
- 5 webhooks: `/safra-emitir`, `/safra-consultar`, `/safra-alterar`, `/safra-baixar`, `/safra-processar-retorno`
- Base URL: `https://soultextil.app.n8n.cloud/webhook/`
- Prod bloqueado (`env=prod` → `PROD_BLOQUEADO`), sandbox default
- Persistência: 3 Data Tables com flag `simulacao=true` (arquivos_remessa_safra, fila_remessa_safra, safra_retorno_eventos)

## Data Tables

- `arquivos_remessa_safra` — histórico de todo REM gerado
- `fila_remessa_safra` — fila de títulos por status
- `safra_retorno_eventos` — histórico de eventos do retorno
- `controle_nn_safra` — sequencial NN (não usado ainda)

## Homologação

Aprovada pela Mesa Safra em 01/09/2026. Aguardando confirmação sobre política de baixa (60 vs prazo flexível por título) pra concluir.
