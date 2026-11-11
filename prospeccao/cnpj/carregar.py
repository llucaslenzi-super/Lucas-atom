"""
Baixa a base pública de CNPJ (Parquet) e carrega no DuckDB.

Fonte: espelho CNPJ Aberto no Hugging Face — a base nacional da Receita
convertida pra Parquet/Zstandard. ~5 GB, 37 arquivos de dados.

Carrega o BRASIL INTEIRO, todos os CNAEs. Filtrar é trabalho da consulta,
não da carga: a base cabe, e assim nenhum estado ou setor fica de fora depois.
"""
from __future__ import annotations

import json
import os
import urllib.request
from pathlib import Path

import duckdb

from . import config

REPO = config.FONTE_ESPELHO_HF
BASE = f"https://huggingface.co/datasets/{REPO}/resolve/main"
API = f"https://huggingface.co/api/datasets/{REPO}"

# Tabelas em ordem de importância: as primeiras bastam pro filtro funcionar.
ESSENCIAIS = ("estabelecimentos", "empresas", "cnaes", "municipios")

# O índice responde UMA pergunta: quais CNPJs existem em tal estado, cidade e
# CNAE. Todo o resto do lead vem da API do EmpresAqui, então carregar as 30
# colunas é guardar em duplicata.
#
# Medido: as 8 colunas abaixo, só de empresas ATIVAS, dão 1,09 GB.
# A base inteira com tudo dá 16,9 GB. Fator de 15.
COLUNAS = {
    "estabelecimentos": ["cnpj_basico", "cnpj_ordem", "cnpj_dv", "uf",
                         "municipio", "cnae_principal", "situacao_cadastral",
                         "matriz_filial"],
    # capital_social fica: e a coluna que ordena quem entra nos primeiros 100.
    "empresas": ["cnpj_basico", "razao_social", "porte", "capital_social"],
}
# 02 = ATIVA. Empresa baixada ou inapta não é lead.
SO_ATIVAS = "situacao_cadastral = '02'"
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
    "porte_empresa": "porte",                  # confirmado no Parquet real
    "porte_da_empresa": "porte",
    "capital_social_da_empresa": "capital_social",
    # confirmados no Parquet real
    "ddd1": "ddd_1",
    "telefone1": "telefone_1",
    "ddd2": "ddd_2",
    "telefone2": "telefone_2",
}


def _ram_mb() -> int:
    """RAM total da máquina, em MB. Sem /proc, assume 2 GB."""
    try:
        for linha in Path("/proc/meminfo").read_text().splitlines():
            if linha.startswith("MemTotal:"):
                return int(linha.split()[1]) // 1024
    except OSError:
        pass
    return 2048


def ajustar(con, leitura=False) -> dict:
    """
    Põe teto de memória no DuckDB e dá a ele um lugar para derramar.

    Sem isso o DuckDB assume que pode usar 80% da RAM FÍSICA. Numa máquina de
    1 GB, onde o Ubuntu já ocupa uns 330 MB, ele pede 800 MB, o kernel não
    tem, e o OOM killer mata o processo no meio da carga — medido na VM:
    `estabelecimentos` passava, `empresas` morria com signal=KILL.

    Com teto e temp_directory ele derrama em disco e fica lento, em vez de
    morrer. Disco é o que sobra; RAM não.
    """
    ram = _ram_mb()
    limite = max(256, int(ram * 0.45))
    fios = 1 if ram < 2048 else min(4, os.cpu_count() or 1)
    tmp = Path(os.environ.get("DUCKDB_TMP", config.DADOS / "tmp"))
    try:
        tmp.mkdir(parents=True, exist_ok=True)
    except OSError:
        tmp = None
    con.execute(f"SET memory_limit='{limite}MB'")
    con.execute(f"SET threads={fios}")
    if tmp is not None:
        con.execute(f"SET temp_directory='{tmp}'")
    if not leitura:
        # Carga em lote não precisa manter a ordem das linhas, e manter custa
        # memória proporcional ao tamanho do lote.
        try:
            con.execute("SET preserve_insertion_order=false")
        except Exception:
            pass
    return {"ram_mb": ram, "memory_limit_mb": limite, "threads": fios}


def _colunas(con, caminho: str) -> list[str]:
    """Nomes das colunas do Parquet, lidos do cursor (independe da versão do DuckDB)."""
    cur = con.execute(f"SELECT * FROM read_parquet('{caminho}') LIMIT 0")
    return [d[0] for d in cur.description]


def montar(db: Path | None = None, bruto: Path | None = None,
           apagar_parquet=True) -> dict:
    """
    Baixa, carrega e apaga UM arquivo por vez.

    Baixar os 4,2 GB de Parquet de uma vez só e depois carregar leva o pico de
    disco a ~8,3 GB. Num disco de 10 GB, com o Ubuntu ocupando 3, não sobra
    espaço para o DuckDB derramar e a carga morre no meio.

    Arquivo por arquivo, o pico de Parquet cai para o maior arquivo isolado —
    uns 320 MB — e a instalação cabe folgada.
    """
    db = Path(db or config.DB)
    bruto = Path(bruto or config.BRUTO)
    bruto.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db))
    lim = ajustar(con)
    print(f"  RAM {lim['ram_mb']} MB · teto DuckDB {lim['memory_limit_mb']} MB · "
          f"{lim['threads']} thread(s)", flush=True)
    resumo = {}

    for grupo in ESSENCIAIS:
        arquivos = [a for a in listar_arquivos() if a.split("/")[0] == grupo]
        if not arquivos:
            continue
        tabela = _nome_tabela(grupo)
        primeiro = True
        for i, nome in enumerate(arquivos, 1):
            local = bruto / nome.replace("/", "__")
            if not local.exists():
                print(f"  [{grupo} {i}/{len(arquivos)}] baixando…", end="", flush=True)
                _baixar_um(nome, local)
                print(f" {local.stat().st_size/1e6:.0f} MB", end="", flush=True)
            cols = _colunas(con, str(local))
            rotulo = {c: ALIAS.get(c, c) for c in cols}
            queridas = COLUNAS.get(grupo)
            if queridas:
                cols = [c for c in cols if rotulo[c] in queridas]
            projecao = ", ".join(
                f'"{c}" AS {rotulo[c]}' if rotulo[c] != c else f'"{c}"' for c in cols)
            onde = ""
            if grupo == "estabelecimentos":
                onde = f" WHERE {SO_ATIVAS}"
            elif grupo == "empresas":
                # Filtra na entrada, não depois. O DELETE ... NOT IN montava
                # um anti-join contra 28 mi de linhas depois de já ter
                # materializado as 63 mi — duas vezes o pico de memória, e
                # era onde a carga morria numa máquina de 1 GB.
                # `fonte.` é obrigatório: sem qualificar, o cnpj_basico de
                # dentro do EXISTS resolve para a própria estabelecimentos,
                # a condição vira x = x, sempre verdadeira, e o filtro passa
                # TODAS as linhas — silenciosamente, sem erro.
                onde = (" WHERE EXISTS (SELECT 1 FROM estabelecimentos x "
                        " WHERE x.cnpj_basico = fonte.cnpj_basico)")
            verbo = "CREATE OR REPLACE TABLE" if primeiro else "INSERT INTO"
            alvo = f"{tabela} AS" if primeiro else tabela
            con.execute(f"{verbo} {alvo} SELECT {projecao} "
                        f"FROM read_parquet('{local}') fonte{onde}")
            primeiro = False
            if apagar_parquet:
                local.unlink(missing_ok=True)      # libera antes do próximo
            print(" ok", flush=True)

        n = con.execute(f"SELECT COUNT(*) FROM {tabela}").fetchone()[0]
        resumo[tabela] = n
        print(f"  {tabela}: {n:,} linhas".replace(",", "."), flush=True)

    _indices(con)
    _escrever_base_json(db, resumo)
    con.close()
    return resumo


def _nome_tabela(grupo: str) -> str:
    return {"motivos_situacoes": "motivos", "qualificacoes_socios": "qualificacoes",
            "naturezas_juridicas": "naturezas"}.get(grupo, grupo)


def _baixar_um(nome: str, local: Path) -> None:
    tmp = local.with_suffix(".parcial")
    req = urllib.request.Request(f"{BASE}/{nome}", headers={"User-Agent": "misner"})
    with urllib.request.urlopen(req, timeout=600) as resp, open(tmp, "wb") as f:
        while chunk := resp.read(1 << 20):
            f.write(chunk)
    tmp.rename(local)


def _indices(con) -> None:
    for tabela, coluna in (("estabelecimentos", "uf"),
                           ("estabelecimentos", "cnae_principal"),
                           ("estabelecimentos", "cnpj_basico"),
                           ("empresas", "cnpj_basico")):
        try:
            con.execute(f"CREATE INDEX IF NOT EXISTS ix_{tabela}_{coluna} "
                        f"ON {tabela}({coluna})")
        except Exception as e:
            print(f"  (índice {tabela}.{coluna} não criado: {e})")


def _escrever_base_json(db: Path, resumo: dict) -> None:
    import json as _json
    from datetime import datetime, timezone
    comp = config.FONTE_ESPELHO_HF.rsplit("-", 2)[-2:]
    (config.DADOS / "base.json").write_text(_json.dumps({
        "arquivo": Path(db).name,
        "competencia": "-".join(comp),
        "estabelecimentos": resumo.get("estabelecimentos", 0),
        "tabelas": resumo,
        "carregado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def carregar(db: Path | None = None, bruto: Path | None = None) -> dict:
    """Cria as tabelas no DuckDB a partir dos Parquet baixados."""
    db = db or config.DB
    bruto = bruto or config.BRUTO
    con = duckdb.connect(str(db))
    ajustar(con)
    resumo = {}

    for grupo in ESSENCIAIS + COMPLEMENTARES:
        arquivos = sorted(bruto.glob(f"{grupo}__*.parquet"))
        if not arquivos:
            continue
        padrao = str(bruto / f"{grupo}__*.parquet")
        cols = _colunas(con, padrao)
        rotulo = {c: (ALIAS.get(c, c)) for c in cols}
        queridas = COLUNAS.get(grupo)
        if queridas:
            cols = [c for c in cols if rotulo[c] in queridas]
        projecao = ", ".join(
            f'"{c}" AS {rotulo[c]}' if rotulo[c] != c else f'"{c}"' for c in cols
        )
        onde = ""
        if grupo == "estabelecimentos":
            onde = f" WHERE {SO_ATIVAS}"
        elif grupo == "empresas":
            onde = (" WHERE EXISTS (SELECT 1 FROM estabelecimentos x "
                    " WHERE x.cnpj_basico = fonte.cnpj_basico)")
        tabela = {"motivos_situacoes": "motivos",
                  "qualificacoes_socios": "qualificacoes",
                  "naturezas_juridicas": "naturezas"}.get(grupo, grupo)
        print(f"  carregando {tabela} ({len(arquivos)} arquivo(s)) ...", end="", flush=True)
        con.execute(f"CREATE OR REPLACE TABLE {tabela} AS "
                    f"SELECT {projecao} FROM read_parquet('{padrao}') fonte{onde}")
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

    # A API lê este arquivo para reportar a competência em /v1/saude e para
    # carimbar base_competencia em cada lead. Sem ele a competência mente.
    import json as _json
    from datetime import datetime, timezone
    comp = (config.FONTE_ESPELHO_HF.rsplit("-", 2)[-2:] or ["", ""])
    (config.DADOS / "base.json").write_text(_json.dumps({
        "arquivo": Path(db).name,
        "competencia": "-".join(comp),
        "estabelecimentos": resumo.get("estabelecimentos", 0),
        "tabelas": resumo,
        "carregado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    con.close()
    return resumo


def verificar(db: Path | None = None) -> tuple[bool, list[str]]:
    """
    Portão, não relatório. Num timer às 3h da manhã ninguém lê `print`:
    sem código de saída, a unidade passaria como sucesso com a base errada.

    Cada checagem pega um modo de falha SILENCIOSO — carga parcial, coluna
    deslocada, arquivo com WAL pendente. Nenhum deles levanta exceção sozinho.
    """
    con = duckdb.connect(str(db or config.DB), read_only=True)
    ajustar(con, leitura=True)
    falhas = []
    try:
        tabelas = {t for (t,) in con.execute("SHOW TABLES").fetchall()}
        for obrigatoria in ("estabelecimentos", "empresas", "cnaes", "municipios"):
            if obrigatoria not in tabelas:
                falhas.append(f"tabela ausente: {obrigatoria}")
        if falhas:
            return False, falhas

        # A lista COLUNAS e um pedido, nao uma garantia: o que o espelho nao
        # trouxer simplesmente nao carrega, e a consulta so quebra depois, em
        # producao. Conferir aqui transforma isso em falha do portao.
        for tabela, queridas in COLUNAS.items():
            tem = {d[0] for d in con.execute(
                f"SELECT * FROM {tabela} LIMIT 0").description}
            faltando = [c for c in queridas if c not in tem]
            if faltando:
                falhas.append(f"{tabela} sem as colunas {faltando} — "
                              "o espelho mudou de layout?")

        n = con.execute("SELECT COUNT(*) FROM estabelecimentos").fetchone()[0]
        # O índice guarda só estabelecimentos ATIVOS: ~28,4 mi dos 73,8 mi
        # totais. O piso tem de refletir isso, senão o portão reprova uma
        # carga correta e a instalação morre no fim.
        if n < 20_000_000:
            falhas.append(f"estabelecimentos com {n:,} linhas — carga parcial?")

        ufs = con.execute("SELECT uf, COUNT(*) c FROM estabelecimentos "
                          "GROUP BY uf ORDER BY c DESC LIMIT 3").fetchall()
        if not ufs or ufs[0][0] != "SP":
            falhas.append(f"SP não é a maior UF (veio {ufs[0][0] if ufs else '—'}) "
                          "— colunas podem estar deslocadas")

        # Não-nulo nos campos que o filtro usa.
        for col in ("uf", "cnae_principal", "situacao_cadastral", "cnpj_basico"):
            vazios = con.execute(
                f"SELECT COUNT(*) FROM estabelecimentos WHERE {col} IS NULL "
                f"OR TRIM({col})=''").fetchone()[0]
            if vazios > n * 0.01:
                falhas.append(f"{col} vazio em {vazios:,} linhas (>1%)")

        # CNAE tem de casar com a tabela de domínio: pega truncamento e troca
        # de coluna, que carregam sem erro nenhum.
        casam = con.execute(
            "SELECT COUNT(*) FROM estabelecimentos e JOIN cnaes c "
            "ON c.codigo = e.cnae_principal").fetchone()[0]
        if casam < n * 0.95:
            falhas.append(f"só {casam:,} de {n:,} CNAEs casam com a tabela cnaes")
    finally:
        con.close()
    return not falhas, falhas


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
    # Lista derivada da tabela, não escrita à mão: uma coluna fixa que o
    # índice deixou de carregar fazia o conferir morrer no último passo,
    # depois de a carga inteira já ter dado certo.
    tem = [d[0] for d in con.execute(
        "SELECT * FROM estabelecimentos LIMIT 0").description]
    cols = [c for c in ("cnpj_basico", "uf", "municipio", "cnae_principal",
                        "situacao_cadastral", "matriz_filial") if c in tem]
    for r in con.execute(f"SELECT {', '.join(cols)} FROM estabelecimentos "
                         f"WHERE uf='SC' LIMIT 3").fetchall():
        print("  ", dict(zip(cols, r)))
    con.close()

    ok, falhas = verificar(db)
    print("\n=== VERIFICAÇÃO ===")
    for f in falhas:
        print(f"  \033[31m✗\033[0m {f}")
    print("  \033[32m✓\033[0m tudo certo" if ok else
          f"  \033[31m{len(falhas)} falha(s) — a base NÃO deve entrar em uso\033[0m")
    if not ok:
        raise SystemExit(1)
