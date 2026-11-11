# Padrão de nomenclatura no n8n — Agente de Prospecção Misner

Padrão da casa: cada produto ganha um **slug curto** e usa ele em tudo. Slug
novo = prefixos novos = **zero colisão** com o que já existe na instância.

## Slug deste projeto

```
slug      misner
display   Misner
```

> O n8n já teve um workflow chamado `Missner · SDR WhatsApp (reativo)` (com dois
> **s**), depois renomeado para `MKT ·`. Aqui está grafado **Misner**, como o nome
> do projeto foi passado. Se o certo for `Missner`, trocar antes de criar o
> primeiro workflow — depois de criado, o path do webhook não muda sem quebrar
> integração.

## A tabela

| Item | Padrão | Neste projeto |
|---|---|---|
| Workflow | `Produto · Função` | `Misner · Pedir Lista` · `Misner · Entregar Fatias` · `Misner · Atualizar Base` |
| **Webhook (path)** | `produto-funcao` | `misner-pedido` · `misner-status` · `misner-entrega` |
| Data Table | `produto_tabela` | `misner_pedidos` · `misner_fatias` · `misner_entregues` |
| Credencial | `Produto · Serviço` | `Misner · API` · `Misner · EmpresAqui` · `Misner · Apify` |
| Tag | nome do produto | `Misner` |
| Folder | nome do produto | `Misner` |

## O que de fato protege

**O path do webhook é o único que pode colidir entre produtos.** Com
`misner-pedido` e `vendas-login`, nunca batem. Nome de workflow, tabela e
credencial duplicados são confusão humana; path duplicado é falha técnica.

Regra: **sempre prefixar o path com o slug.**

## Checklist para subir este produto

```
[ ] Folder "Misner" criada
[ ] Tag "Misner" criada
[ ] Credencial  Misner · API         (Bearer do serviço + cabeçalhos do Access)
[ ] Workflow    Misner · Pedir Lista       → webhook misner-pedido
[ ] Workflow    Misner · Entregar Fatias   → schedule, sem webhook
[ ] Workflow    Misner · Atualizar Base    → schedule mensal
[ ] Tudo dentro da Folder e com a Tag
[ ] Nenhum nome ou path sem o prefixo misner
```

## O que NÃO tocar

A instância tem 108 workflows. Estes já rodam em produção e **não são deste
produto**:

```
MKT ·      SDR WhatsApp · Motor de Cadência · Disparo Advogados (fila)
           Guardião (corta-circuito) · Tracking Abertura · Descadastro
           Enriquecimento Nome (Receita)        ← desativado, não reativar
SaaS ·     Material · Serve Material · Salvar Roteiro · Status v2
           Deletar Instância
Soul ·     Pedido por Voz · Pedidos Lucas v3 · Estoque de Fios
Agente de Crédito · Soul Têxtil
```

Seguindo o padrão, nenhum deles é tocado.
