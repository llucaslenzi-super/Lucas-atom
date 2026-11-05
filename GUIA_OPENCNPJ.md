# Guia OpenCNPJ — consulta de CNPJ e preenchimento de NOME

Guia de bolso pra reusar em **qualquer chat/sessão nova**. Explica a API OpenCNPJ,
os scripts prontos e como rodar tudo no **seu Mac**.

> ⚠️ **Importante:** as sessões do Claude na nuvem **não conseguem** acessar a
> `api.opencnpj.org` (bloqueio de rede da organização). Por isso o fluxo é sempre:
> **o Claude escreve/ajusta o script → VOCÊ roda no seu Mac** (onde a internet
> alcança a API normalmente).

---

## 1. A API OpenCNPJ (o que é)

- API **pública e gratuita** que devolve os dados cadastrais de um CNPJ (base da Receita).
- **Endpoint:** `GET https://api.opencnpj.org/{CNPJ}`
  - CNPJ **sem máscara** (só números): `https://api.opencnpj.org/41132876000179`
  - Também aceita com máscara.
- **Resposta (JSON)** traz, entre outros:
  - `razao_social`, `nome_fantasia`
  - `situacao_cadastral` (Ativa, Baixada, Suspensa, Inapta, Nula)
  - `email`, `telefones[]` (ddd + numero)
  - endereço: `tipo_logradouro`, `logradouro`, `numero`, `bairro`, `cep`, `municipio`, `uf`
  - `cnae_principal`, `cnaes_secundarios`, `natureza_juridica`, `porte_empresa`, `capital_social`
  - `opcao_simples`, `opcao_mei`
  - `QSA` → lista de sócios (nome, qualificação, etc.)
- **Status HTTP:** `200` achou · `404` não existe · `400` CNPJ inválido · `429` limite de uso · `502` instabilidade momentânea.
- **Rate limit:** tem limite. Em consultas em lote, use pausa entre chamadas ou um número controlado de requisições em paralelo + retry no 429/502.

### Exemplo rápido (teste de 1 CNPJ no terminal do Mac)
```bash
curl "https://api.opencnpj.org/41132876000179"
```

---

## 2. Pré-requisitos no Mac (faz 1 vez só)

1. Ter o Python 3:
   ```bash
   python3 --version
   ```
   Se não tiver, instalar em https://www.python.org/downloads/macos/
2. Instalar as bibliotecas:
   ```bash
   python3 -m pip install --user requests pandas openpyxl
   ```

> Obs.: no Mac o comando é **`python3`** (com o 3) e **`python3 -m pip`** pra instalar.
> O aviso `NotOpenSSLWarning ... LibreSSL` que aparece é inofensivo, pode ignorar.

---

## 3. Os scripts prontos (ficam no repositório `Lucas-atom`)

| Script | Pra que serve | Velocidade |
|---|---|---|
| `consulta_cnpj_opencnpj.py` | Pega uma planilha de CNPJs e marca **quem está ATIVO na Receita** + traz todos os dados (situação, contato, endereço, sócios). | serial |
| `preenche_nome_socio.py` | Preenche a coluna **NOME** com o 1º nome do contato (do e-mail se for nome próprio; senão do sócio principal via CNPJ). | serial |
| `preenche_nome_socio_turbo.py` | **Igual ao de cima, mas em paralelo** (bem mais rápido). Use este pra listas grandes (10k, 40k…). | paralelo ⚡ |

Todos:
- aceitam **.csv ou .xlsx**;
- **descobrem sozinhos** as colunas (CNPJ, E-mail, Razão, NOME);
- não consultam o mesmo CNPJ duas vezes;
- geram um `.xlsx` de saída (`<arquivo>_com_nome.xlsx` ou `<arquivo>_opencnpj.xlsx`).

---

## 4. Como rodar (no Terminal do Mac)

Coloque a planilha e o script na **mesma pasta** (ex.: Downloads) e:

```bash
cd ~/Downloads

# A) Marcar quem está ATIVO na Receita + todos os dados:
python3 consulta_cnpj_opencnpj.py "MINHA_LISTA.csv"

# B) Preencher a coluna NOME (lista pequena/média):
python3 preenche_nome_socio.py "MINHA_LISTA.csv"

# C) Preencher a coluna NOME em lista GRANDE (rápido, paralelo):
python3 preenche_nome_socio_turbo.py "MINHA_LISTA.csv"
#   se a API reclamar muito (429), baixe o paralelismo:
python3 preenche_nome_socio_turbo.py "MINHA_LISTA.csv" --workers 8
```

💡 **Dica à prova de erro com o nome do arquivo:** digite o comando até o `.py `
(com espaço no fim) e **arraste o arquivo do Finder** pra dentro do terminal — ele
cola o caminho certinho. Depois Enter.

Saída: aparece o progresso, um RESUMO e o arquivo `..._com_nome.xlsx` na mesma pasta.

---

## 5. A regra de negócio do NOME (como ele decide)

Para cada linha:
1. Olha o **início do e-mail** (antes do `@`). Se for um **nome próprio** (validado
   num dicionário de nomes montado a partir da coluna Razão + lista comum) → usa esse nome.
2. Senão → **consulta o CNPJ** na OpenCNPJ e pega o **primeiro nome do sócio principal**
   (prioriza quem é Administrador/Titular no QSA).
3. Escreve **só o primeiro nome** (ex.: "Raul", "Marcelo", "Alessandra").

---

## 6. Texto pronto pra colar num chat/sessão NOVA

Copie e cole isto numa conversa nova com o Claude (ajuste o nome do arquivo):

> Tenho uma planilha de clientes (CSV/XLSX) com colunas de **CNPJ**, **Razão social**,
> **E-mail** e uma coluna **NOME** (vazia). Quero preencher a coluna NOME com o
> **primeiro nome** do contato, usando a **API pública OpenCNPJ**
> (`GET https://api.opencnpj.org/{CNPJ}`), com esta regra:
> 1) se o início do e-mail for um nome próprio, use esse nome;
> 2) senão, consulte o CNPJ na OpenCNPJ e use o **primeiro nome do sócio principal** (QSA, priorizando Administrador/Titular);
> 3) grave só o primeiro nome.
>
> Observações: a sessão na nuvem **não acessa** a `api.opencnpj.org` (bloqueio de rede),
> então **me entregue um script Python pronto** que eu rodo no meu **Mac**
> (tenho Python 3 + `requests pandas openpyxl`). O script deve: detectar as colunas
> sozinho, aceitar CSV/XLSX, **fazer as consultas de CNPJ em paralelo** (com retry no
> 429/502) pra ser rápido em listas grandes, não repetir CNPJ, e gerar um `.xlsx` de saída.
> Já tenho uma versão chamada `preenche_nome_socio_turbo.py` no meu repositório `Lucas-atom`
> (branch `claude/dreamy-davinci-80xyr7`) — pode partir dela.

---

## 7. Onde estão os arquivos

Repositório **`Lucas-atom`**, branch **`claude/dreamy-davinci-80xyr7`**:
- `consulta_cnpj_opencnpj.py`
- `preenche_nome_socio.py`
- `preenche_nome_socio_turbo.py`
- `GUIA_OPENCNPJ.md` (este guia)

Numa sessão nova, basta pedir ao Claude pra ler esses arquivos do repositório.
