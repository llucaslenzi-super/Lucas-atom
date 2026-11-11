# Agente de Prospecção Misner — organização no n8n

## A instância

```
https://atomtecnologia.app.n8n.cloud
projeto: LUCAS LENZI <lucas@atomwork.com.br>   (pessoal)
```

**Tudo deste produto vive aqui.** A instância `soultextil.app.n8n.cloud` é
outra coisa e não participa deste projeto.

## Slug

```
slug      misner
display   Misner
pasta     Misner        (criada, ao lado de "Agente Internacional" e
                         "Vendas (Agente WhatsApp)")
```

## O padrão, e o que já se pratica na Atom

| Item | Padrão | Neste produto |
|---|---|---|
| Workflow | `Produto · Função` | `Misner · Pedir Lista` · `Misner · Entregar Fatias` |
| **Webhook (path)** | `produto-funcao` | `misner-pedido` · `misner-status` |
| Pasta | nome do produto | `Misner` |
| Credencial | `Produto · Serviço` | `Misner · API` |
| Tag | nome do produto | `Misner` (nasce com o 1º workflow) |

Levantamento da Atom em 11/11/2026: 79 workflows, agrupados por prefixo —
**J2P** (37), **Vendas** (23), sem prefixo (17), **TEMP** (2). Pastas em uso:
Agente Internacional, Vendas (Agente WhatsApp). Nenhuma tag.

O padrão de path mais próximo do documentado é o do Agente Internacional
(`aginternacional-login`, `aginternacional-criar-cliente`). O J2P usa barra
(`pagar/criar`, `auth/login`) e o Vendas é irregular (`app`, `material`).
Misner segue o do Agente Internacional.

## O que de fato protege

**O path do webhook é o único que colide de verdade entre produtos.** Nome de
workflow e de pasta duplicados são confusão humana; path duplicado é falha
técnica. Com `misner-pedido` nada bate com os 52 webhooks que já existem —
verificado um a um.

Regra: **sempre prefixar o path com o slug.**

## Isolamento

Este produto **não reaproveita nada** do que já está na Atom. Nenhum workflow
existente é chamado, alterado ou movido. Nenhuma credencial existente é
reutilizada. O que o Misner precisa, o Misner cria com o próprio prefixo.

## Checklist

```
[x] Pasta "Misner" criada no projeto pessoal
[ ] Credencial  Misner · API         Bearer do serviço
[ ] Workflow    Misner · Pedir Lista       → webhook misner-pedido
[ ] Workflow    Misner · Entregar Fatias   → schedule, sem webhook
[ ] Tag "Misner" aplicada aos dois
```

Os workflows entram **depois** de a VM responder — workflow apontando para
serviço inexistente é sujeira na instância.

## O que não tocar

```
J2P —      37 workflows   (auth, pagar, nf, asaas, cron)
Vendas ·   23 workflows   (app, motor, lead set, material, instâncias)
Agente Internacional ·  ·  Agente Processual WhatsApp
Agente de Pedidos Soul v1/v2/v3   ·   TEMP —
```
