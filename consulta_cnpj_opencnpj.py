#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Consulta CNPJs de uma planilha na API pública OpenCNPJ (https://opencnpj.org)
e gera UMA planilha de saida, uma linha por empresa, com a situacao cadastral
na Receita + todos os dados que a API retorna (contato, endereco, CNAE, porte,
Simples/MEI e socios/QSA numa unica coluna).

O filtro principal pedido e: "esta ATIVA na Receita ou nao".
A coluna ATIVO_RECEITA resume isso em Sim / Nao / Nao encontrado / Erro.

----------------------------------------------------------------------
COMO USAR
----------------------------------------------------------------------
1. Instale as dependencias (uma vez):

       pip install requests pandas openpyxl

2. Rode apontando pra sua planilha (.xlsx ou .csv):

       python consulta_cnpj_opencnpj.py minha_planilha.xlsx

   Opcoes:
       --coluna "CNPJ"      forca o nome da coluna de CNPJ (senao detecta sozinho)
       --saida resultado.xlsx   nome do arquivo de saida (default: <entrada>_opencnpj.xlsx)
       --delay 0.3          pausa em segundos entre chamadas (respeita rate limit)

   Exemplos:
       python consulta_cnpj_opencnpj.py clientes.xlsx
       python consulta_cnpj_opencnpj.py clientes.csv --coluna "Documento" --saida ativos.xlsx

O script mantem TODAS as colunas originais da sua planilha e acrescenta as novas.
Nao consulta o mesmo CNPJ duas vezes (cache), pra economizar requisicoes.
----------------------------------------------------------------------
"""

import argparse
import os
import re
import sys
import time

try:
    import requests
except ImportError:
    sys.exit("Faltou a lib 'requests'. Rode:  pip install requests pandas openpyxl")

try:
    import pandas as pd
except ImportError:
    sys.exit("Faltou a lib 'pandas'. Rode:  pip install requests pandas openpyxl")


API_BASE = "https://api.opencnpj.org"
# Situacoes consideradas "ativa" na Receita (normalizadas p/ maiusculas sem acento).
SITUACOES_ATIVAS = {"ATIVA"}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def normaliza_cnpj(valor) -> str:
    """Remove mascara e espacos; mantem letras (CNPJ alfanumerico) em maiusculo.
    Retorna string de 14 chars ou '' se nao der pra aproveitar."""
    if valor is None:
        return ""
    txt = str(valor).strip().upper()
    if txt in ("", "NAN", "NONE"):
        return ""
    # tira tudo que nao for letra ou numero
    txt = re.sub(r"[^A-Z0-9]", "", txt)
    # planilhas as vezes comem o zero a esquerda -> completa ate 14
    if 0 < len(txt) < 14 and txt.isdigit():
        txt = txt.zfill(14)
    return txt if len(txt) == 14 else ""


def detecta_coluna_cnpj(df: pd.DataFrame) -> str:
    """Acha a coluna de CNPJ: 1) pelo nome, 2) pela que tem mais valores
    que parecem CNPJ de 14 digitos."""
    # 1) pelo nome
    for col in df.columns:
        nome = str(col).strip().lower()
        if "cnpj" in nome:
            return col
    for col in df.columns:
        nome = str(col).strip().lower()
        if nome in ("documento", "doc", "cpf/cnpj", "cnpj/cpf"):
            return col
    # 2) pela cara dos dados
    melhor_col, melhor_qtd = None, 0
    for col in df.columns:
        qtd = df[col].map(lambda v: len(normaliza_cnpj(v)) == 14).sum()
        if qtd > melhor_qtd:
            melhor_col, melhor_qtd = col, qtd
    if melhor_col is not None and melhor_qtd > 0:
        return melhor_col
    return None


def sem_acento_maiusc(txt: str) -> str:
    import unicodedata
    txt = unicodedata.normalize("NFKD", str(txt))
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    return txt.strip().upper()


def formata_telefones(lista) -> str:
    if not lista:
        return ""
    partes = []
    for t in lista:
        ddd = (t.get("ddd") or "").strip()
        num = (t.get("numero") or "").strip()
        if not num:
            continue
        fax = " (fax)" if t.get("is_fax") else ""
        partes.append(f"({ddd}) {num}{fax}" if ddd else f"{num}{fax}")
    return "; ".join(partes)


def formata_qsa(lista) -> str:
    if not lista:
        return ""
    partes = []
    for s in lista:
        nome = (s.get("nome_socio") or "").strip()
        qual = (s.get("qualificacao_socio") or "").strip()
        if not nome:
            continue
        partes.append(f"{nome} ({qual})" if qual else nome)
    return "; ".join(partes)


def monta_endereco(d: dict) -> str:
    tipo = (d.get("tipo_logradouro") or "").strip()
    log = (d.get("logradouro") or "").strip()
    num = (d.get("numero") or "").strip()
    comp = (d.get("complemento") or "").strip()
    bairro = (d.get("bairro") or "").strip()
    partes = [p for p in [f"{tipo} {log}".strip(), num, comp, bairro] if p]
    return ", ".join(partes)


# --------------------------------------------------------------------------- #
# Consulta na API
# --------------------------------------------------------------------------- #
def consulta_cnpj(session: requests.Session, cnpj: str, tentativas: int = 4):
    """Retorna (status, dados). status em {'ok','nao_encontrado','invalido','erro'}."""
    url = f"{API_BASE}/{cnpj}"
    backoff = 2
    for i in range(tentativas):
        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException as e:
            if i == tentativas - 1:
                return "erro", f"falha de conexao: {e}"
            time.sleep(backoff)
            backoff *= 2
            continue

        if resp.status_code == 200:
            try:
                return "ok", resp.json()
            except ValueError:
                return "erro", "resposta nao-JSON"
        if resp.status_code == 404:
            return "nao_encontrado", None
        if resp.status_code == 400:
            return "invalido", None
        # 429 (rate limit) ou 5xx -> espera e tenta de novo
        if resp.status_code in (429, 500, 502, 503, 504):
            if i == tentativas - 1:
                return "erro", f"HTTP {resp.status_code} apos {tentativas} tentativas"
            espera = backoff
            ra = resp.headers.get("Retry-After")
            if ra and ra.isdigit():
                espera = max(espera, int(ra))
            time.sleep(espera)
            backoff *= 2
            continue
        return "erro", f"HTTP {resp.status_code}"
    return "erro", "esgotou tentativas"


def extrai_campos(d: dict) -> dict:
    """Transforma o JSON da API nas colunas da planilha de saida."""
    situacao = (d.get("situacao_cadastral") or "").strip()
    ativo = "Sim" if sem_acento_maiusc(situacao) in SITUACOES_ATIVAS else "Nao"
    return {
        "ATIVO_RECEITA": ativo,
        "situacao_cadastral": situacao,
        "data_situacao_cadastral": d.get("data_situacao_cadastral", ""),
        "razao_social": d.get("razao_social", ""),
        "nome_fantasia": d.get("nome_fantasia", ""),
        "matriz_filial": d.get("matriz_filial", ""),
        "data_inicio_atividade": d.get("data_inicio_atividade", ""),
        "email": d.get("email", ""),
        "telefones": formata_telefones(d.get("telefones")),
        "endereco": monta_endereco(d),
        "cep": d.get("cep", ""),
        "municipio": d.get("municipio", ""),
        "uf": d.get("uf", ""),
        "cnae_principal": d.get("cnae_principal", ""),
        "cnaes_secundarios": "; ".join(d.get("cnaes_secundarios") or []),
        "natureza_juridica": d.get("natureza_juridica", ""),
        "porte_empresa": d.get("porte_empresa", ""),
        "capital_social": d.get("capital_social", ""),
        "opcao_simples": d.get("opcao_simples", ""),
        "data_opcao_simples": d.get("data_opcao_simples", ""),
        "opcao_mei": d.get("opcao_mei", ""),
        "data_opcao_mei": d.get("data_opcao_mei", ""),
        "socios_QSA": formata_qsa(d.get("QSA")),
    }


COLUNAS_NOVAS = [
    "ATIVO_RECEITA", "situacao_cadastral", "data_situacao_cadastral",
    "razao_social", "nome_fantasia", "matriz_filial", "data_inicio_atividade",
    "email", "telefones", "endereco", "cep", "municipio", "uf",
    "cnae_principal", "cnaes_secundarios", "natureza_juridica",
    "porte_empresa", "capital_social", "opcao_simples", "data_opcao_simples",
    "opcao_mei", "data_opcao_mei", "socios_QSA",
]


def vazio(ativo_receita: str) -> dict:
    """Linha de colunas novas vazias, com o rotulo de status no ATIVO_RECEITA."""
    base = {c: "" for c in COLUNAS_NOVAS}
    base["ATIVO_RECEITA"] = ativo_receita
    return base


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def le_planilha(caminho: str) -> pd.DataFrame:
    ext = os.path.splitext(caminho)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        return pd.read_excel(caminho, dtype=str)
    if ext in (".csv", ".txt"):
        # sep=None + engine python => detecta , ou ; automaticamente
        return pd.read_csv(caminho, dtype=str, sep=None, engine="python")
    sys.exit(f"Extensao nao suportada: {ext}. Use .xlsx ou .csv")


def main():
    ap = argparse.ArgumentParser(
        description="Consulta CNPJs de uma planilha na OpenCNPJ e marca quem esta ATIVO na Receita."
    )
    ap.add_argument("entrada", help="Planilha de entrada (.xlsx ou .csv)")
    ap.add_argument("--coluna", help="Nome da coluna de CNPJ (senao detecta sozinho)")
    ap.add_argument("--saida", help="Arquivo .xlsx de saida")
    ap.add_argument("--delay", type=float, default=0.3,
                    help="Pausa (s) entre chamadas (default 0.3)")
    args = ap.parse_args()

    if not os.path.exists(args.entrada):
        sys.exit(f"Arquivo nao encontrado: {args.entrada}")

    df = le_planilha(args.entrada)
    if df.empty:
        sys.exit("A planilha esta vazia.")

    col = args.coluna if args.coluna else detecta_coluna_cnpj(df)
    if not col or col not in df.columns:
        sys.exit(
            "Nao consegui identificar a coluna de CNPJ. "
            "Use --coluna \"NOME_DA_COLUNA\". Colunas disponiveis: "
            + ", ".join(map(str, df.columns))
        )
    print(f">> Coluna de CNPJ: '{col}'")

    # planilha so com a coluna de CNPJ e sem cabecalho vira "Unnamed: 0" -> renomeia
    if str(col).startswith("Unnamed"):
        df = df.rename(columns={col: "CNPJ"})
        col = "CNPJ"
        print(">> (coluna sem nome renomeada para 'CNPJ' na saida)")

    saida = args.saida or (os.path.splitext(args.entrada)[0] + "_opencnpj.xlsx")

    session = requests.Session()
    session.headers.update({"User-Agent": "consulta-cnpj-opencnpj/1.0"})

    cache = {}          # cnpj -> dict de colunas novas
    novas_linhas = []   # alinhado com df
    total = len(df)
    contagem = {"Sim": 0, "Nao": 0, "Nao encontrado": 0, "Invalido": 0, "Erro": 0, "Sem CNPJ": 0}

    for i, (_, linha) in enumerate(df.iterrows(), start=1):
        cnpj = normaliza_cnpj(linha[col])
        if not cnpj:
            novas_linhas.append(vazio("Sem CNPJ"))
            contagem["Sem CNPJ"] += 1
            continue

        if cnpj in cache:
            resultado = cache[cnpj]
        else:
            status, dados = consulta_cnpj(session, cnpj)
            if status == "ok":
                resultado = extrai_campos(dados)
            elif status == "nao_encontrado":
                resultado = vazio("Nao encontrado")
            elif status == "invalido":
                resultado = vazio("Invalido")
            else:
                resultado = vazio("Erro")
                resultado["situacao_cadastral"] = str(dados) if dados else ""
            cache[cnpj] = resultado
            time.sleep(args.delay)  # so pausa em chamada real

        novas_linhas.append(resultado)
        rotulo = resultado["ATIVO_RECEITA"]
        contagem[rotulo] = contagem.get(rotulo, 0) + 1

        if i % 25 == 0 or i == total:
            print(f"   {i}/{total} consultados...", flush=True)

    novas_df = pd.DataFrame(novas_linhas, columns=COLUNAS_NOVAS).reset_index(drop=True)
    df = df.reset_index(drop=True)
    # evita colisao de nomes: se a planilha ja tem uma coluna igual, prefixa a nova
    for c in COLUNAS_NOVAS:
        if c in df.columns:
            novas_df = novas_df.rename(columns={c: f"{c}_opencnpj"})
    final = pd.concat([df, novas_df], axis=1)

    # ordena deixando os ATIVOS no topo
    ordem = {"Sim": 0, "Nao": 1, "Nao encontrado": 2, "Invalido": 3, "Erro": 4, "Sem CNPJ": 5}
    col_ativo = "ATIVO_RECEITA" if "ATIVO_RECEITA" in final.columns else "ATIVO_RECEITA_opencnpj"
    final["_ordem"] = final[col_ativo].map(lambda v: ordem.get(v, 9))
    final = final.sort_values("_ordem", kind="stable").drop(columns="_ordem")

    final.to_excel(saida, index=False)

    print("\n================ RESUMO ================")
    for k, v in contagem.items():
        if v:
            print(f"  {k:>16}: {v}")
    print(f"  {'TOTAL linhas':>16}: {total}")
    print(f"  {'CNPJs unicos':>16}: {len(cache)}")
    print(f"\n>> Planilha gerada: {saida}")


if __name__ == "__main__":
    main()
