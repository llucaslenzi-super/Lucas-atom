#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VERSAO TURBO (paralela) do preenche_nome_socio.

Mesma regra:
  1) Se o inicio do e-mail for um NOME PROPRIO -> usa esse nome.
  2) Senao -> consulta o CNPJ na API OpenCNPJ e pega o PRIMEIRO NOME do socio principal.
So escreve o primeiro nome.

Diferenca: as consultas de CNPJ sao feitas EM PARALELO (varias ao mesmo tempo),
o que derruba o tempo de ~2h45 pra ~10 min numa base de 40 mil.

----------------------------------------------------------------------
COMO USAR
    python3 -m pip install --user requests pandas openpyxl
    python3 preenche_nome_socio_turbo.py "sua_planilha.csv"
Opcoes:
    --saida saida.xlsx   nome do arquivo de saida (default: <entrada>_com_nome.xlsx)
    --workers 15         quantas consultas em paralelo (baixe p/ 8 se der muito 429)
----------------------------------------------------------------------
"""

import argparse
import os
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from requests.adapters import HTTPAdapter
except ImportError:
    sys.exit("Faltou 'requests'. Rode:  python3 -m pip install --user requests pandas openpyxl")
try:
    import pandas as pd
except ImportError:
    sys.exit("Faltou 'pandas'. Rode:  python3 -m pip install --user requests pandas openpyxl")

API_BASE = "https://api.opencnpj.org"

PALAVRAS_EMPRESA = {
    "sociedade","individual","advocacia","ltda","me","epp","eireli","sa","s/a","empresa",
    "comercio","comercial","industria","servicos","servico","cia","associados","advogados",
    "advogadas","escritorio","consultoria","contabilidade","representacoes","transportes",
    "construtora","incorporadora","participacoes","holding","grupo","clinica","instituto",
    "distribuidora","atacado","varejo","inova","simples","is","do","da","de","dos","das","e",
}
EMAIL_GENERICOS = {
    "contato","contatos","atendimento","adm","administrativo","administracao","financeiro",
    "fiscal","comercial","vendas","compras","juridico","adv","advocacia","escritorio",
    "contabil","contabilidade","meucnpj","cnpj","nfe","notas","nota","rh","sac","diretoria",
    "gerencia","empresa","faleconosco","email","mail","suporte","marketing","recepcao",
    "secretaria","cobranca","pagamentos","pessoal","info","geral","central",
}
NOMES_SEMENTE = {
    "ana","maria","joao","jose","antonio","francisco","carlos","paulo","pedro","lucas","luiz",
    "luis","marcos","marcelo","rafael","daniel","marcio","rodrigo","bruno","eduardo","felipe",
    "raul","gustavo","guilherme","gabriel","andre","fernando","ricardo","sergio","roberto",
    "fabio","leonardo","mateus","matheus","thiago","tiago","vinicius","victor","vitor","renato",
    "renan","alexandre","julio","cesar","diego","caio","igor","henrique","arthur","artur","davi",
    "david","samuel","leandro","wesley","william","anderson","alex","adriano","aline","amanda",
    "adriana","beatriz","bianca","bruna","camila","carla","carolina","caroline","cristina",
    "cristiane","daniela","debora","denise","eliane","elaine","fernanda","flavia","gabriela",
    "giovana","helena","isabela","isabella","jessica","juliana","julia","karina","karol",
    "karoline","larissa","leticia","luana","lucia","luciana","luiza","manuela","mariana","marcia",
    "marina","michele","monica","natalia","patricia","paula","priscila","rafaela","raquel",
    "regina","renata","rita","roberta","rosana","sabrina","sandra","sara","sarah","silvia",
    "simone","sonia","tatiane","taina","vanessa","veronica","vitoria","alessandra","alessandro",
    "alberto","aurea","aurelio","benedito","claudia","claudio","cleber","clayton","dalton",
    "edson","edna","eda","elton","emanuel","emerson","evandro","fabiana","gedson","geovani",
    "gilberto","gilmar","gisele","hamilton","heitor","ivan","jair","jean","joana","jorge",
    "josiane","kelly","laura","leila","lilian","lincoln","lorena","magno","marcela","mauricio",
    "nelson","otavio","pablo","rubens","sidnei","silas","tania","valeria","valter","wagner",
    "wilson","wanderson","yasmin","yuri","zilda","camilla","samara","renam",
}


def nrm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z]", "", s.lower())


def primeiro_token_nome(texto):
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
            n = nrm(primeiro_token_nome(razao))
            if len(n) >= 3:
                nomes.add(n)
    return nomes


def prefixo_email(email):
    e = str(email or "").strip().lower()
    if "@" not in e or not e:
        return ""
    p = e.split("@")[0]
    return re.split(r"[._\-0-9+]", p)[0]


def normaliza_cnpj(valor):
    if valor is None:
        return ""
    txt = re.sub(r"[^A-Z0-9]", "", str(valor).strip().upper())
    if 0 < len(txt) < 14 and txt.isdigit():
        txt = txt.zfill(14)
    return txt if len(txt) == 14 else ""


def consulta_cnpj(session, cnpj, tentativas=4):
    url = f"{API_BASE}/{cnpj}"
    backoff = 1.5
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
    if not d:
        return ""
    qsa = d.get("QSA") or []
    if qsa:
        def score(s):
            q = nrm(s.get("qualificacao_socio") or "")
            if "administrador" in q: return 0
            if "titular" in q: return 1
            if "socio" in q: return 2
            return 3
        melhor = sorted(qsa, key=score)[0]
        tok = primeiro_token_nome(melhor.get("nome_socio") or "")
        if tok:
            return capitaliza(tok)
    return capitaliza(primeiro_token_nome(d.get("razao_social") or ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("entrada")
    ap.add_argument("--saida")
    ap.add_argument("--workers", type=int, default=15, help="consultas em paralelo (default 15)")
    args = ap.parse_args()

    if not os.path.exists(args.entrada):
        sys.exit(f"Arquivo nao encontrado: {args.entrada}")
    ext = os.path.splitext(args.entrada)[1].lower()
    if ext in (".xlsx", ".xlsm", ".xls"):
        df = pd.read_excel(args.entrada, dtype=str)
    else:
        df = pd.read_csv(args.entrada, dtype=str, sep=None, engine="python")
    df.columns = [str(c).strip() for c in df.columns]

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
        col_nome = "NOME"; df[col_nome] = ""
    print(f">> CNPJ='{col_cnpj}' | Email='{col_email}' | Razao='{col_razao}' | Nome='{col_nome}'")

    nomes_dic = monta_dicionario_nomes(df, col_razao)
    print(f">> Dicionario de nomes: {len(nomes_dic)} nomes")

    # ---- Passo 1: classifica cada linha; decide nome do email OU marca p/ consultar CNPJ
    origem_email = [None] * len(df)   # nome final quando veio do email
    cnpj_por_linha = [""] * len(df)
    cnpjs_necessarios = set()
    n_email = 0
    for idx, (_, linha) in enumerate(df.iterrows()):
        pref = prefixo_email(linha[col_email])
        if len(pref) >= 3 and nrm(pref) in nomes_dic and nrm(pref) not in EMAIL_GENERICOS:
            origem_email[idx] = capitaliza(pref)
            n_email += 1
        else:
            cnpj = normaliza_cnpj(linha[col_cnpj])
            cnpj_por_linha[idx] = cnpj
            if cnpj:
                cnpjs_necessarios.add(cnpj)
    print(f">> Nome do email: {n_email} | CNPJs unicos a consultar: {len(cnpjs_necessarios)}")

    # ---- Passo 2: consulta os CNPJs unicos EM PARALELO
    lista = list(cnpjs_necessarios)
    resultado_cnpj = {}
    total_lookup = len(lista)
    feitos = [0]
    lock = threading.Lock()

    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=args.workers, pool_maxsize=args.workers, max_retries=0)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": "preenche-nome-socio-turbo/1.0"})

    def worker(cnpj):
        nome = socio_principal_primeiro_nome(consulta_cnpj(session, cnpj))
        with lock:
            feitos[0] += 1
            if feitos[0] % 200 == 0 or feitos[0] == total_lookup:
                print(f"   CNPJ {feitos[0]}/{total_lookup}...", flush=True)
        return cnpj, nome

    t0 = time.time()
    if total_lookup:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for cnpj, nome in ex.map(worker, lista):
                resultado_cnpj[cnpj] = nome
    dur = time.time() - t0

    # ---- Passo 3: monta a coluna NOME
    nomes_final = []
    achou = 0
    for idx in range(len(df)):
        if origem_email[idx] is not None:
            nome = origem_email[idx]
        else:
            nome = resultado_cnpj.get(cnpj_por_linha[idx], "")
        nomes_final.append(nome)
        if nome:
            achou += 1
    df[col_nome] = nomes_final

    saida = args.saida or (os.path.splitext(args.entrada)[0] + "_com_nome.xlsx")
    df.to_excel(saida, index=False)

    print("\n================ RESUMO ================")
    print(f"  Nome do e-mail   : {n_email}")
    print(f"  CNPJs consultados: {total_lookup}  (em {dur/60:.1f} min)")
    print(f"  Linhas com nome  : {achou} de {len(df)}")
    print(f"  Sem nome         : {len(df) - achou}")
    print(f"\n>> Planilha gerada: {saida}")


if __name__ == "__main__":
    main()
