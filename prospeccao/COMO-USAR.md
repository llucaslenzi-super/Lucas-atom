# Agente de Prospecção Missner — como usar

**Endereço:** https://atomtecnologia.app.n8n.cloud/webhook/prospeccao

A senha está fora do repositório. Ela é constante no nó `Roteia` do workflow
`Prospecção · API`, na Atom; para trocar, é uma linha nesse nó.

---

## O que a pessoa faz

1. **Entrar** — uma senha.
2. **Nova pesquisa**, em três passos:
   - **Origem**: filtro na base da Receita, ou uma planilha de CNPJs que ela
     já tem.
   - **Critérios**: para qual cliente é a lista, estados, cidade, até 2 CNAEs,
     quantas empresas e se busca contatos na internet.
   - **Confirmar**: o resumo, e o aviso de que a entrega não volta atrás.
3. **Minhas listas** — cada lista de 100 ganha o botão de baixar assim que
   fica pronta. O arquivo cai no computador dela. Não há link para copiar,
   não há e-mail, não há Drive.
4. **Entregues** — procura um CNPJ e diz se ele já foi para algum cliente,
   quando, e em qual lista.

## As regras que a tela torna visíveis

- **Toda lista tem no máximo 100 empresas.** Pedido de 300 vira três listas.
  Não é configuração, é constante — e é o que permite baixar a primeira
  enquanto as outras rodam.
- **Entregou, não volta** — para aquele cliente. A mesma empresa pode ir para
  outro cliente.
- **A repetida vem marcada, não escondida.** Se o filtro já esgotou, a lista
  vem completa, com as repetidas marcadas na coluna 13 (`ja_entregue`) e a
  data da lista anterior na 14 (`entregue_antes_em`). A tela soma quantas são.
  Entregar 50 caladamente pareceria defeito.
- **Dois CNAEs no máximo**, com o contador "2 de 2" à vista. Pela planilha não
  há teto, porque ali o CNAE é resultado, não critério.
- **O teto de 2 vale no servidor também.** A tela é conveniência; a regra está
  no nó `Roteia` e em `buscar.py`.

## O que está montado na Atom

Projeto **Missner** (`U7PD2iEcNVV1GxIs`). Nada na soultextil.

| workflow | caminho | o que faz |
|---|---|---|
| `Prospecção · App` | `GET /webhook/prospeccao` | serve a página |
| `Prospecção · API` | `POST /webhook/prospeccao-api` | entrar, criar pedido, histórico, busca de entregues |
| `Prospecção · Guardar` | `POST /webhook/prospeccao-guardar` | a VM deposita a lista pronta |
| `Prospecção · Baixar` | `GET /webhook/prospeccao-baixar?c=` | devolve o arquivo ao navegador |
| `Prospecção · Limpar` | diário, 4h | retenção |

| Data Table | para quê |
|---|---|
| `prospeccao_ui` | o HTML da página |
| `prospeccao_pedidos` | a fila que a VM lê |
| `prospeccao_listas` | índice leve das listas prontas |
| `prospeccao_arquivos` | os arquivos em base64 |
| `prospeccao_entregues` | espelho do registro, para a busca por CNPJ |

**Por que arquivo e índice em tabelas separadas:** a tela recarrega o
histórico de 20 em 20 segundos enquanto há pedido em curso. Com o base64 na
mesma tabela, cada atualização arrastaria megabytes. Separados, a atualização
é de alguns kilobytes.

**Retenção:** arquivo e índice são apagados com 7 dias; o espelho de
entregues, com 180. É o que mantém os 50 MB de Data Table da instância sob
controle.

## Para trocar a interface depois

```bash
cd prospeccao/web && python3 montar.py /tmp/app.html
```

e subir o resultado para a linha `slug='app'` da `prospeccao_ui`. Não é
preciso republicar workflow nenhum — a página é dado, não código.

## Uma limitação, dita com todas as letras

O n8n devolve a página com `Content-Security-Policy: sandbox`, sem
`allow-same-origin`. Isso faz o `sessionStorage` do navegador lançar exceção.
Consequência prática: **ao recarregar a página, a pessoa entra de novo**, e o
rascunho do formulário não sobrevive a um recarregamento. Dentro da mesma
visita, ir e voltar entre os passos não perde nada — isso é memória do
próprio script. O código já trata a exceção; não quebra, só não lembra.
