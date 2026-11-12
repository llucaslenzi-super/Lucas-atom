"""
Registro de empresas já entregues — o requisito central.

    pesquisa 1 → 50 empresas
    pesquisa 2 → outras 50, nenhuma repetida
    ...

Arquivo PRÓPRIO, separado da base da Receita. A base é substituída todo mês;
um registro guardado dentro dela seria destruído na troca e o sistema
voltaria a repetir empresa já no mês seguinte.

Exclui por EMPRESA (cnpj_basico), não por estabelecimento: entregue a matriz,
a filial não volta disfarçada de lead novo.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from . import config

ARQUIVO = config.DADOS / "entregues.duckdb"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS entregues (
  cnpj          VARCHAR PRIMARY KEY,
  cnpj_basico   VARCHAR NOT NULL,
  razao_social  VARCHAR,
  lote_id       VARCHAR NOT NULL,
  entregue_em   TIMESTAMP NOT NULL,
  filtro_usado  VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_entregues_basico ON entregues(cnpj_basico);
CREATE INDEX IF NOT EXISTS ix_entregues_lote   ON entregues(lote_id);
"""


def _con(arquivo: Path | None = None, somente_leitura=False):
    alvo = Path(arquivo or ARQUIVO)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if somente_leitura and not alvo.exists():
        duckdb.connect(str(alvo)).execute(_ESQUEMA)
    con = duckdb.connect(str(alvo), read_only=somente_leitura)
    if not somente_leitura:
        con.execute(_ESQUEMA)
    return con


def registrar(leads: list[dict], lote_id: str, filtro: str = "", arquivo=None) -> int:
    """
    Marca como entregues. Chamado SÓ quando a fatia foi gerada com sucesso —
    lote que falha no meio não marca ninguém.
    """
    linhas = [(l["cnpj"], (l.get("cnpj_base") or l["cnpj"][:8]),
               l.get("razao_social"), lote_id, filtro)
              for l in leads if l.get("cnpj")]
    if not linhas:
        return 0
    con = _con(arquivo)
    con.executemany(
        "INSERT OR REPLACE INTO entregues VALUES (?,?,?,?,now(),?)", linhas)
    con.close()
    return len(linhas)


def ja_entregues(arquivo=None) -> set[str]:
    """Os cnpj_basico já entregues, para o anti-join do filtro."""
    con = _con(arquivo, somente_leitura=True)
    r = {x[0] for x in con.execute("SELECT DISTINCT cnpj_basico FROM entregues").fetchall()}
    con.close()
    return r


def total(arquivo=None) -> dict:
    con = _con(arquivo, somente_leitura=True)
    n, lotes, ultimo = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT lote_id), MAX(entregue_em) FROM entregues"
    ).fetchone()
    por_lote = con.execute(
        "SELECT lote_id, COUNT(*) n, MIN(entregue_em) q FROM entregues "
        "GROUP BY lote_id ORDER BY q DESC LIMIT 15").fetchall()
    con.close()
    return {"empresas": n, "lotes": lotes, "ultimo": ultimo, "por_lote": por_lote}


def limpar_lote(lote_id: str, arquivo=None) -> int:
    """Desfaz um lote entregue por engano — as empresas voltam a ser elegíveis."""
    con = _con(arquivo)
    n = con.execute("SELECT COUNT(*) FROM entregues WHERE lote_id=?", [lote_id]).fetchone()[0]
    con.execute("DELETE FROM entregues WHERE lote_id=?", [lote_id])
    con.close()
    return n


# ─────────────────────────────────────────── cópia de segurança

def copiar(pasta: Path | None = None, manter=14,
           arquivo: Path | None = None) -> Path:
    """
    Dump consistente do registro, em CSV comprimido.

    Por que CSV e não uma cópia do .duckdb: copiar o arquivo enquanto alguém
    escreve nele produz cópia rasgada, que abre mas devolve dados pela metade
    — e o estrago só aparece no dia em que alguém precisa restaurar. O `COPY`
    do DuckDB lê numa transação e escreve algo que sempre volta inteiro.

    Por que não manda para fora da VM aqui: a conta de serviço desta máquina
    tem escopo de Storage SOMENTE LEITURA, então gravar em bucket é recusado
    antes de sair.

    Duas coisas levam o dump para fora, e as duas já estão previstas:
      · o snapshot diário do disco, já configurado no projeto — e o papel
        deste dump é garantir que o snapshot carregue um arquivo restaurável
        em vez de um banco possivelmente rasgado;
      · a ponte, que empurra o dump mais recente para o n8n. Cabe: medido em
        10 bytes por empresa comprimida, 250 mil empresas dão 2,4 MB.
    """
    from datetime import datetime, timezone

    pasta = Path(pasta or (config.DADOS / "copias"))
    pasta.mkdir(parents=True, exist_ok=True)
    selo = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    destino = pasta / f"entregues-{selo}.csv.gz"

    con = _con(arquivo, somente_leitura=True)
    try:
        n = con.execute("SELECT COUNT(*) FROM entregues").fetchone()[0]
        con.execute(
            f"COPY (SELECT * FROM entregues ORDER BY entregue_em) "
            f"TO '{destino}' (FORMAT CSV, HEADER, COMPRESSION GZIP)")
    finally:
        con.close()

    # Retenção: sem isto a pasta cresce para sempre num disco de 15 GB.
    copias = sorted(pasta.glob("entregues-*.csv.gz"))
    for velha in copias[:-manter] if manter else []:
        velha.unlink(missing_ok=True)

    print(f"  cópia de {n:,} entregues → {destino}".replace(",", "."))
    return destino


def restaurar(csv_gz: Path, arquivo: Path | None = None) -> int:
    """
    Volta um dump para dentro do registro, sem apagar o que já está lá.

    `INSERT OR IGNORE` de propósito: restaurar não pode desentregar empresa
    que foi entregue depois do dump.
    """
    con = _con(arquivo)
    try:
        con.execute(
            f"INSERT OR IGNORE INTO entregues "
            f"SELECT * FROM read_csv_auto('{Path(csv_gz)}')")
        n = con.execute("SELECT COUNT(*) FROM entregues").fetchone()[0]
    finally:
        con.close()
    return n
