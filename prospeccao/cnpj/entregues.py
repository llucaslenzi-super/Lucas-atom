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
