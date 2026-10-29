#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Preenche a coluna NOME de uma planilha de clientes com o PRIMEIRO NOME do contato.

Regra (pedida pelo usuario):
  1) Olha o inicio do e-mail. Se for um NOME PROPRIO -> usa esse nome.
  2) Se NAO for nome proprio (contato@, financeiro@, meucnpj@, etc.)
     -> consulta o CNPJ na API OpenCNPJ e pega o PRIMEIRO NOME do socio principal.

So escreve o primeiro nome (ex.: "Raul", "Marcelo", "Alessandra").

Como decide se o inicio do e-mail "e um nome":
  - monta um dicionario de nomes a partir da propria coluna Razao (muitos registros
    sao "FULANO DE TAL SOCIEDADE INDIVIDUAL DE ADVOCACIA" -> primeiro token = nome real)
  - soma uma lista-semente de nomes comuns brasileiros
  - o pedaco antes do @ (primeiro bloco) tem que bater nesse dicionario e ter >= 3 letras

----------------------------------------------------------------------
COMO USAR
    python3 -m pip install --user requests pandas openpyxl
    python3 preenche_nome_socio.py "sua_planilha.csv"
Opcoes:
    --saida saida.xlsx    nome do arquivo de saida (default: <entrada>_com_nome.xlsx)
    --delay 0.3           pausa (s) entre chamadas na API
----------------------------------------------------------------------
"""

import argparse
import os
import re
import sys
import time
import unicodedata

try:
    import requests
except ImportError:
    sys.exit("Faltou 'requests'. Rode:  python3 -m pip install --user requests pandas openpyxl")
try:
    import pandas as pd
except ImportError:
    sys.exit("Faltou 'pandas'. Rode:  python3 -m pip install --user requests pandas openpyxl")

API_BASE = "https://api.opencnpj.org"

# Palavras que aparecem em Razao mas NAO sao nome de pessoa (pra nao poluir o dicionario)
PALAVRAS_EMPRESA = {
    "sociedade", "individual", "advocacia", "ltda", "me", "epp", "eireli", "sa", "s/a",
    "empresa", "comercio", "comercial", "industria", "servicos", "servico", "cia",
    "associados", "advogados", "advogadas", "escritorio", "consultoria", "contabilidade",
    "representacoes", "transportes", "construtora", "incorporadora", "participacoes",
    "holding", "grupo", "clinica", "instituto", "distribuidora", "atacado", "varejo",
    "do", "da", "de", "dos", "das", "e",
}

# Pedacos genericos de e-mail que NUNCA sao nome de pessoa
EMAIL_GENERICOS = {
    "contato", "contatos", "atendimento", "adm", "administrativo", "administracao",
    "financeiro", "fiscal", "comercial", "vendas", "compras", "juridico", "adv",
    "advocacia", "escritorio", "contabil", "contabilidade", "meucnpj", "cnpj", "nfe",
    "notas", "nota", "rh", "sac", "diretoria", "gerencia", "empresa", "faleconosco",
    "email", "mail", "suporte", "marketing", "recepcao", "secretaria", "cobranca",
    "pagamentos", "pessoal", "info", "atendimento1", "atendimento2", "geral", "central",
}

# Semente de nomes comuns brasileiros (reforca o dicionario montado a partir da Razao)
NOMES_SEMENTE = {
    "ana","maria","joao","jose","antonio","francisco","carlos","paulo","pedro","lucas",
    "luiz","luis","marcos","marcelo","rafael","daniel","marcio","rodrigo","bruno","eduardo",
    "felipe","raul","gustavo","guilherme","gabriel","andre","fernando","ricardo","sergio",
    "roberto","fabio","leonardo","mateus","matheus","thiago","tiago","vinicius","victor",
    "vitor","renato","renan","alexandre","julio","cesar","diego","caio","igor","henrique",
    "arthur","artur","davi","david","samuel","leandro","wesley","william","anderson",
    "alex","adriano","aline","amanda","adriana","beatriz","bianca","bruna","camila","carla",
    "carolina","caroline","cristina","cristiane","daniela","debora","denise","eliane","elaine",
    "fernanda","flavia","gabriela","giovana","helena","isabela","isabella","jessica","juliana",
    "julia","karina","karol","karoline","larissa","leticia","luana","lucia","luciana","luiza",
    "manuela","mariana","marcia","marina","michele","monica","natalia","patricia","paula",
    "priscila","rafaela","raquel","regina","renata","rita","roberta","rosana","sabrina","sandra",
    "sara","sarah","silvia","simone","sonia","tatiane","taina","vanessa","veronica","vitoria",
    "alessandra","alessandro","alberto","aurea","aurelio","benedito","claudia","claudio",
    "cleber","clayton","dalton","edson","edna","eda","elton","emanuel","emerson","evandro",
    "fabiana","gedson","geovani","gilberto","gilmar","gisele","hamilton","heitor","ivan",
    "jair","jean","joana","jorge","josiane","kelly","laura","leila","lilian","lincoln",
    "lorena","magno","marcela","mauricio","nelson","otavio","pablo","rubens","sidnei",
    "silas","tania","valeria","valter","wagner","wilson","wanderson","yasmin","yuri","zilda",
    "camilla","samara","renam","karol",
}


def nrm(s):
    """minusculo, sem acento, so letras."""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def primeiro_token_nome(texto):
    """Primeiro token 'de pessoa' de um texto (pula palavras de empresa)."""
    if not texto:
        return ""
    for tok in re.split(r"\s+", str(texto).strip()):
        n = nrm(tok)
        if len(n) >= 2 and n not in PALAVRAS_EMPRESA:
            return tok
    return ""


def capitaliza(nome):
    n = str(nome).strip()
    return n[:1].upper() + n[1:].lower() if n else n


def monta_dicionario_nomes(df, col_razao):
    nomes = set(NOMES_SEMENTE)
    if col_razao and col_razao in df.columns:
        for razao in df[col_razao].fillna(""):
            tok = primeiro_token_nome(razao)
            n = nrm(tok)
            if len(n) >= 3:
                nomes.add(n)
    return nomes


def prefixo_email(email):
    """Primeiro bloco antes do @ (quebra em . _ - e digitos)."""
    e = str(email or "").strip().lower()
    if "@" not in e or not e:
        return ""
    p = e.split("@")[0]
    p = re.split(r"[._\-0-9+]", p)[0]
    return p


def normaliza_cnpj(valor):
    if valor is None:
        return ""
    txt = re.sub(r"[^A-Z0-9]", "", str(valor).strip().upper())
    if 0 < len(txt) < 14 and txt.isdigit():
        txt = txt.zfill(14)
    return txt if len(txt) == 14 else ""


def consulta_cnpj(session, cnpj, tentativas=4):
    url = f"{API_BASE}/{cnpj}"
    backoff = 2
    for i in range(tentativas):
        try:
            resp = session.get(url, timeout=30)
        except requests.RequestException:
            if i == tentativas - 1:
                return None
            time.sleep(backoff); backoff *= 2; continue
        if resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                return None
        if resp.status_code in (404, 400):
            return None
        if resp.status_code in (429, 500, 502, 503, 504):
            if i == tentativas - 1:
                return None
            espera = backoff
            ra = resp.headers.get("Retry-After")
            if ra and ra.isdigit():
                espera = max(espera, int(ra))
            time.sleep(espera); backoff *= 2; continue
        return None
    return None


def socio_principal_primeiro_nome(d):
    """Primeiro nome do socio principal (prioriza administrador/titular)."""
    if not d:
        return ""
    qsa = d.get("QSA") or []
    if qsa:
        def score(s):
            q = nrm(s.get("qualificacao_socio") or "")
            if "administrador" in q:
                return 0
            if "titular" in q:
                return 1
            if "socio" in q:
                return 2
            return 3
        melhor = sorted(qsa, key=score)[0]
        tok = primeiro_token_nome(melhor.get("nome_socio") or "")
        if tok:
            return capitaliza(tok)
    # fallback: razao social da propria consulta
    tok = primeiro_token_nome(d.get("razao_social") or "")
    return capitaliza(tok)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada", help="Planilha .csv ou .xlsx")
    ap.add_argument("--saida")
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    if not os.path.exists(args.entrada):
        sys.exit(f"Arquivo nao encontrado: {args.entrada}")

    ext = os.path.splitext(args.entrada)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(args.entrada, dtype=str)
    else:
        df = pd.read_csv(args.entrada, dtype=str, sep=None, engine="python")
    df.columns = [str(c).strip() for c in df.columns]

    # localiza colunas
    def acha(cands):
        for c in df.columns:
            if nrm(c) in cands:
                return c
        return None
    col_cnpj = acha({"cnpj"}) or df.columns[0]
    col_email = acha({"email", "emails"})
    col_razao = acha({"razao", "razaosocial"})
    col_nome = acha({"nome"})
    if not col_email:
        sys.exit("Nao achei a coluna de e-mail. Colunas: " + ", ".join(df.columns))
    if not col_nome:
        col_nome = "NOME"
        df[col_nome] = ""
    print(f">> CNPJ='{col_cnpj}' | Email='{col_email}' | Razao='{col_razao}' | Nome='{col_nome}'")

    nomes_dic = monta_dicionario_nomes(df, col_razao)
    print(f">> Dicionario de nomes montado: {len(nomes_dic)} nomes")

    saida = args.saida or (os.path.splitext(args.entrada)[0] + "_com_nome.xlsx")
    session = requests.Session()
    session.headers.update({"User-Agent": "preenche-nome-socio/1.0"})

    cache = {}
    resultados = []
    total = len(df)
    cont = {"email": 0, "cnpj": 0, "nao_achou": 0}

    for i, (_, linha) in enumerate(df.iterrows(), start=1):
        pref = prefixo_email(linha[col_email])
        nome_final = ""
        origem = ""
        if len(pref) >= 3 and nrm(pref) in nomes_dic and nrm(pref) not in EMAIL_GENERICOS:
            nome_final = capitaliza(pref)
            origem = "email"
        else:
            cnpj = normaliza_cnpj(linha[col_cnpj])
            if cnpj:
                if cnpj in cache:
                    nome_final = cache[cnpj]
                else:
                    nome_final = socio_principal_primeiro_nome(consulta_cnpj(session, cnpj))
                    cache[cnpj] = nome_final
                    time.sleep(args.delay)
                origem = "cnpj" if nome_final else "nao_achou"
            else:
                origem = "nao_achou"
        resultados.append(nome_final)
        cont[origem if origem in cont else "nao_achou"] += 1
        if i % 25 == 0 or i == total:
            print(f"   {i}/{total}  (email={cont['email']} cnpj={cont['cnpj']} sem={cont['nao_achou']})", flush=True)

    df[col_nome] = resultados
    df.to_excel(saida, index=False)

    print("\n================ RESUMO ================")
    print(f"  Nome veio do e-mail : {cont['email']}")
    print(f"  Nome veio do CNPJ   : {cont['cnpj']}")
    print(f"  Nao encontrado      : {cont['nao_achou']}")
    print(f"  TOTAL linhas        : {total}")
    print(f"  Consultas na API    : {len(cache)}")
    print(f"\n>> Planilha gerada: {saida}")


if __name__ == "__main__":
    main()
