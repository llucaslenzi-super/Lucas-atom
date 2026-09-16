# Operações Safra CNAB 240 — Guia rápido

Homologação aprovada em 15/09/2026. Este documento cobre as 4 operações homologadas + retorno.

**Endpoints (n8n webhook):**
| Operação | Method + URL | action |
|---|---|---|
| Emitir | `POST /webhook/safra-emitir` | `emitir` |
| Baixar | `POST /webhook/safra-baixar` | `baixar` |
| Alterar vencimento | `POST /webhook/safra-alterar` | `alterar_venc` |
| Alterar juros/multa/desconto | `POST /webhook/safra-alterar` | `alterar_dados` |
| Processar retorno | `POST /webhook/safra-processar-retorno` | `processar_retorno` |
| Consultar título | `POST /webhook/safra-consultar` | `consultar` |

Base: `https://soultextil.app.n8n.cloud`
Envio do REM ao banco: portal Safra Empresas → Caixa Postal `SOULINDU`.

---

## 1. Emitir (cod 01)

Cria título de cobrança. Suporta as 3 instruções homologadas: **Juros, Multa, Desconto**.

**Códigos aceitos no título:**
- `juros_codigo`: `1` = valor fixo por dia | `2` = taxa/dia | `3` = isento
- `desconto_codigo`: `0` = sem | `1` = valor fixo até data | `2` = percentual | `3` = por antecipação
- `multa_codigo`: `0` = sem | `1` = valor fixo | `2` = percentual
- `protesto_codigo`: sempre `3` (não homologado)
- `baixa_codigo`: sempre `1` (baixa automática não homologada — use action `baixar`)

**Regra Safra:** se `juros_codigo=3` → `juros_data=null` e `juros_valor=0`. Mesmo pra `desconto_codigo=0`. A lib força isso automaticamente.

Ver `exemplos/payloads/01_emitir_com_juros_multa_desconto.json`.

## 2. Baixar (cod 02)

Cancela um título já emitido. Envia REM com movimento 02.
Precisa: `nosso_numero`, `valor_centavos`, `data_vencimento` (Safra confere).

Ver `exemplos/payloads/02_baixar.json`.

## 3. Alterar vencimento (cod 06)

Prorroga vencimento. Envia o título com o **novo** `data_vencimento`.

Ver `exemplos/payloads/03_alterar_venc.json`.

## 4. Alterar juros/multa/desconto (cod 31)

Muda condições sem mexer no vencimento. Envia o título com os novos valores.

Ver `exemplos/payloads/04_alterar_dados.json`.

## 5. Processar retorno

Recebe conteúdo do arquivo `.RET` que o Safra devolve. Parser extrai eventos, classifica em CONFIRMADO / LIQUIDADO / REJEITADO / BAIXADO / ALTERADO e devolve.

Body: `conteudo_ret` (string) OU `conteudo_base64`.

Ver `exemplos/payloads/07_processar_retorno.json`.

## 6. Consultar

Lê Data Table `fila_remessa_safra` + `safra_retorno_eventos` e devolve `{status, pagou, ultimo_evento, historico_fila, historico_eventos}`.

Ver `exemplos/payloads/08_consultar.json`.

---

## Instruções NÃO homologadas (bloqueadas no código)

- `protestar` (cod 09) — retorna `ACTION_NAO_HOMOLOGADA`
- `sustar` / `sustar_protesto` (cod 10) — retorna `ACTION_NAO_HOMOLOGADA`
- Baixa automática após XX dias — `baixa_codigo` forçado em `1` mesmo se input mandar `2`

## Envio ao banco

Não é SFTP nem API — é upload manual pelo portal:

1. Safra Empresas → menu **OUTROS**
2. **Transferência de Arquivos → Enviar**
3. Escolhe opção **CAIXA POSTAL**
4. Localiza o `.REM` pelo botão **SELECIONAR**
5. Caixa postal: **`SOULINDU`**
6. Selecionar produto/serviço → **ENVIAR**

Central Safra (dúvidas transmissão): 0300 015 7575 / 11 3175-8248.
