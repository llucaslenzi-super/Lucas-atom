"""
Baixa a base pública de CNPJ (Parquet) e carrega no DuckDB.

Fonte: espelho CNPJ Aberto no Hugging Face — a base nacional da Receita
convertida pra Parquet/Zstandard. ~5 GB, 37 arquivos de dados.

Carrega o BRASIL INTEIRO, todos os CNAEs. Filtrar é trabalho da consulta,
não da carga: a base cabe, e assim nenhum estado ou setor fica de fora depois.
"""
from __future__ import annotations

import json
import urllib.request
from pathlib import Path

import duckdb

from . import config

REPO = config.FONTE_ESPELHO_HF
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main"
API = f"https://huggingface.co/api/datasets/{REPO}"

# Tabelas em ordem de importância: as primeiras bastam pro filtro funcionar.
ESSENCIAIS = ("estabelecimentos", "empresas", "cnaes", "municipios")
COMPLEMENTARES = ("socios", "simples", "naturezas_juridicas",
                  "qualificacoes_socios", "motivos_situacoes", "paises")


def listar_arquivos() -> list[str]:
    with urllib.request.urlopen(API, timeout=60) as r:
        d = json.load(r)
    return sorted(
        f["rfilename"] for f in d.get("siblings", [])
        if f["rfilename"].endswith(".parquet")
    )


def baixar(apenas_essenciais=True, destino: Path | None = None) -> list[Path]:
    """Baixa com retomada. Arquivo já completo é pulado."""
    destino = destino or config.BRUTO
    grupos = ESSENCIAIS if apenas_essenciais else ESSENCIAIS + COMPLEMENTARES
    alvos = [a for a in listar_arquivos() if a.split("/")[0] in grupos]

    baixados = []
    for i, nome in enumerate(alvos, 1):
        local = destino / nome.replace("/", "__")
        if local.exists() and local.stat().st_size > 0:
            print(f"  [{i:2}/{len(alvos)}] {nome}  (já existe, pulando)")
            baixados.append(local)
            continue
        print(f"  [{i:2}/{len(alvos)}] {nome} ...", end="", flush=True)
        tmp = local.with_suffix(".parcial")
        req = urllib.request.Request(f"{BASE}/{nome}", headers={"User-Agent": "cnpj-pipeline"})
        with urllib.request.urlopen(req, timeout=300) as resp, open(tmp, "wb") as f:
            total = 0
            while chunk := resp.read(1 << 20):
                f.write(chunk)
                total += len(chunk)
        tmp.rename(local)
        print(f" {total/1e6:.0f} MB")
        baixados.append(local)
    return baixados


# ───────────────────────────────────────────────────── carga

# O espelho pode nomear colunas diferente do layout cru da Receita.
# Mapeamos pro nome canônico; o que não bater fica como veio.
ALIAS = {
    "cnpj_cpf_do_socio": "cnpj_cpf_socio",
    "identificador_de_socio": "identificador_socio",
    "nome_do_socio": "nome_socio",
    "cnae_fiscal_principal": "cnae_principal",
    "cnae_fiscal_secundaria": "cnae_secundario",
    "identificador_matriz_filial": "matriz_filial",
    "correio_eletronico": "email",
    "data_inicio_atividade": "data_abertura",
    "porte_da_empresa": "porte",
    "capital_social_da_empresa": "capital_social",
    "descricao": "descricao",
}


def _colunas(con, caminho: str) -> list[str]:
    return [r[0] for r in con.execute(
        f"SELECT name FROM (DESCRIBE SELECT * FROM read_parquet('{caminho}') LIMIT 0)"
    ).fetchall()]


def carregar(db: Path | None = None, bruto: Path | None = None) -> dict:
    """Cria as tabelas no DuckDB a partir dos Parquet baixados."""
    db = db or config.DB
    bruto = bruto or config.BRUTO
    con = duckdb.connect(str(db))
    resumo = {}

    for grupo in ESSENCIAIS + COMPLEMENTARES:
        arquivos = sorted(bruto.glob(f"{grupo}__*.parquet"))
        if not arquivos:
            continue
        padrao = str(bruto / f"{grupo}__*.parquet")
        cols = _colunas(con, padrao)
        projecao = ", ".join(
            f'"{c}" AS {ALIAS[c]}' if c in ALIAS and ALIAS[c] != c else f'"{c}"'
            for c in cols
        )
        tabela = {"motivos_situacoes": "motivos",
                  "qualificacoes_socios": "qualificacoes",
                  "naturezas_juridicas": "naturezas"}.get(grupo, grupo)
        print(f"  carregando {tabela} ({len(arquivos)} arquivo(s)) ...", end="", flush=True)
        con.execute(f"CREATE OR REPLACE TABLE {tabela} AS "
                    f"SELECT {projecao} FROM read_parquet('{padrao}')")
        n = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        resumo[tabela] = n
        print(f" {n:,} linhas".replace(",", "."))

    # Índices nos campos de filtro — é o que faz a consulta ser instantânea.
    for tabela, coluna in (("estabelecimentos", "uf"),
                           ("estabelecimentos", "cnae_principal"),
                           ("estabelecimentos", "situacao_cadastral"),
                           ("estabelecimentos", "cnpj_basico"),
                           ("empresas", "cnpj_basico")):
        try:
            con.execute(f"CREATE INDEX IF NOT EXISTS ix_{tabela}_{coluna} "
                        f"ON {tabela}({coluna})")
        except Exception as e:
            print(f"  (índice {tabela}.{coluna} não criado: {e})")

    con.close()
    return resumo


def conferir(db: Path | None = None) -> None:
    """
    Verificação obrigatória antes de confiar na base.
    Se a ordem das colunas estiver trocada, os dados carregam sem erro
    nenhum e ficam silenciosamente errados.
    """
    con = duckdb.connect(str(db or config.DB), read_only=True)
    print("\n=== LINHAS POR TABELA ===")
    for (t,) in con.execute("SHOW TABLES").fetchall():
        print(f"  {t:18} {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]:>12,}".replace(",", "."))

    print("\n=== ESTABELECIMENTOS POR UF (os 10 maiores) ===")
    for uf, n in con.execute(
        "SELECT uf, COUNT(*) n FROM estabelecimentos "
        "GROUP BY uf ORDER BY n DESC LIMIT 10"
    ).fetchall():
        print(f"  {uf}  {n:>12,}".replace(",", "."))

    print("\n=== AMOSTRA — os campos caíram no lugar certo? ===")
    cols = "cnpj_basico, nome_fantasia, uf, municipio, cnae_principal, situacao_cadastral"
    for r in con.execute(f"SELECT {cols} FROM estabelecimentos WHERE uf='SC' LIMIT 3").fetchall():
        print("  ", r)
    con.close()
