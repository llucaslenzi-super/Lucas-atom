"""
Fila de pedidos, em SQLite.

Um pedido vira N fatias de ~100. Cada fatia é uma unidade completa: gera
sua planilha, é entregue, e só então as empresas entram no registro de
entregues. Nenhuma fatia passa de ~2 minutos.

Fatiar é o que dissolve a dificuldade do projeto. Com job único, 1000
empresas levariam 17 minutos e 10.000 levariam 2h47 — e aí seriam
necessários máquina de estado por item, fila com prioridade e processo
separado para o Apify. Com fatias, nada disso.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ESQUEMA = """
PRAGMA journal_mode=WAL;          -- sem isso a escrita do worker trava a leitura
PRAGMA busy_timeout=5000;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS pedidos (
  id             TEXT PRIMARY KEY,
  chave_idem     TEXT UNIQUE,     -- o n8n repete em timeout; sem isso paga 2x
  filtro         TEXT,
  total_pedido   INTEGER,
  tamanho_fatia  INTEGER,
  formatos       TEXT,
  blocos         TEXT,
  com_apify      INTEGER,
  teto_usd       REAL,
  status         TEXT,            -- pendente|executando|pronto|erro|cancelado|pausado
  motivo         TEXT,
  base_competencia TEXT,
  criado_em      TEXT,
  concluido_em   TEXT
);

CREATE TABLE IF NOT EXISTS fatias (
  pedido_id   TEXT NOT NULL,
  n           INTEGER NOT NULL,
  cnpjs       TEXT NOT NULL,      -- congelado na criação, não recalculado
  status      TEXT NOT NULL,      -- pendente|executando|pronto|erro|cancelado
  leads       INTEGER DEFAULT 0,
  requisicoes INTEGER DEFAULT 0,
  cache_hits  INTEGER DEFAULT 0,
  custo_usd   REAL DEFAULT 0,
  arquivos    TEXT,
  erro        TEXT,
  iniciada_em TEXT,
  concluida_em TEXT,
  PRIMARY KEY (pedido_id, n)
);
CREATE INDEX IF NOT EXISTS ix_fatias_status ON fatias(status);

CREATE TABLE IF NOT EXISTS servico (chave TEXT PRIMARY KEY, valor TEXT);
"""


# O tamanho da lista é CONSTANTE, não parâmetro. Era configurável pelo cliente
# e isso derrubava o desenho: tamanho_fatia=100000 produzia uma fatia única de
# horas, sem entrega parcial, sem retomada barata, e sem caber no n8n.
#
# Cem é o número que faz tudo funcionar: dois minutos a 1 req/s, 473 KB em
# xlsx+csv depois do base64, e refazer uma que falhe custa dois minutos.
TAMANHO_LISTA = 100


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Fila:
    def __init__(self, arquivo: Path):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.arquivo), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(ESQUEMA)
        self.db.commit()

    # ---------------------------------------------------------- criar
    def criar(self, cnpjs: list[str], *, filtro="", formatos=("xlsx",), blocos=None,
              com_apify=True, teto_usd=2.0, chave_idem=None,
              base_competencia=None) -> dict:
        """
        A lista de CNPJs é CONGELADA aqui. Se o pedido fosse só o filtro, uma
        retomada depois da troca mensal da base processaria outro conjunto e o
        pedido viraria irreproduzível.
        """
        if chave_idem:
            ja = self.db.execute("SELECT id FROM pedidos WHERE chave_idem=?",
                                 [chave_idem]).fetchone()
            if ja:
                return {"id": ja["id"], "repetido": True}

        pid = "p_" + uuid.uuid4().hex[:12]
        fatias = [cnpjs[i:i + TAMANHO_LISTA]
                  for i in range(0, len(cnpjs), TAMANHO_LISTA)] or [[]]
        self.db.execute(
            "INSERT INTO pedidos VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, chave_idem, filtro, len(cnpjs), TAMANHO_LISTA,
             json.dumps(list(formatos)), json.dumps(blocos), int(com_apify),
             teto_usd, "pendente", None, base_competencia, _agora(), None))
        self.db.executemany(
            "INSERT INTO fatias (pedido_id,n,cnpjs,status) VALUES (?,?,?,'pendente')",
            [(pid, i, json.dumps(f)) for i, f in enumerate(fatias, 1)])
        self.db.commit()
        return {"id": pid, "fatias": len(fatias), "total": len(cnpjs),
                "eta_seg": round(len(cnpjs) * 1.05), "repetido": False}

    # ---------------------------------------------------------- worker
    def proxima_fatia(self) -> sqlite3.Row | None:
        """FIFO. Todas as fatias têm o mesmo tamanho, então não há prioridade."""
        cur = self.db.execute("""
            UPDATE fatias SET status='executando', iniciada_em=?
            WHERE (pedido_id, n) = (
              SELECT f.pedido_id, f.n FROM fatias f JOIN pedidos p ON p.id=f.pedido_id
              WHERE f.status='pendente' AND p.status IN ('pendente','executando')
              ORDER BY p.criado_em, f.n LIMIT 1)
            RETURNING *""", [_agora()])
        r = cur.fetchone()
        if r:
            self.db.execute(
                "UPDATE pedidos SET status='executando' WHERE id=? AND status='pendente'",
                [r["pedido_id"]])
            self.db.commit()
        return r

    def concluir_fatia(self, pid: str, n: int, *, leads=0, requisicoes=0,
                       cache_hits=0, custo=0.0, arquivos=None, erro=None):
        self.db.execute("""
            UPDATE fatias SET status=?, leads=?, requisicoes=?, cache_hits=?,
                   custo_usd=?, arquivos=?, erro=?, concluida_em=?
            WHERE pedido_id=? AND n=?""",
            ("erro" if erro else "pronto", leads, requisicoes, cache_hits, custo,
             json.dumps(arquivos or {}), erro, _agora(), pid, n))
        pend = self.db.execute(
            "SELECT COUNT(*) c FROM fatias WHERE pedido_id=? AND status IN "
            "('pendente','executando')", [pid]).fetchone()["c"]
        if not pend:
            self.db.execute(
                "UPDATE pedidos SET status='pronto', concluido_em=? WHERE id=?",
                [_agora(), pid])
        self.db.commit()

    def devolver_fatia(self, pid: str, n: int, motivo: str):
        """Token inválido ou teto batido: a fatia volta para a fila, não some."""
        self.db.execute(
            "UPDATE fatias SET status='pendente', iniciada_em=NULL WHERE pedido_id=? AND n=?",
            [pid, n])
        self.db.execute("UPDATE pedidos SET status='pausado', motivo=? WHERE id=?",
                        [motivo, pid])
        self.db.commit()

    def retomar_orfas(self) -> int:
        """Na partida: o que ficou 'executando' numa queda volta para 'pendente'."""
        cur = self.db.execute(
            "UPDATE fatias SET status='pendente', iniciada_em=NULL WHERE status='executando'")
        self.db.commit()
        return cur.rowcount

    # ---------------------------------------------------------- consulta
    def pedido(self, pid: str) -> dict | None:
        p = self.db.execute("SELECT * FROM pedidos WHERE id=?", [pid]).fetchone()
        if not p:
            return None
        fs = self.db.execute(
            "SELECT * FROM fatias WHERE pedido_id=? ORDER BY n", [pid]).fetchall()
        prontas = [f for f in fs if f["status"] == "pronto"]
        pend = sum(len(json.loads(f["cnpjs"])) for f in fs
                   if f["status"] in ("pendente", "executando"))
        return {
            "id": p["id"], "status": p["status"], "motivo": p["motivo"],
            "filtro": p["filtro"], "total": p["total_pedido"],
            "base_competencia": p["base_competencia"],
            "fatias_total": len(fs), "fatias_prontas": len(prontas),
            "leads": sum(f["leads"] for f in fs),
            "requisicoes": sum(f["requisicoes"] for f in fs),
            "cache_hits": sum(f["cache_hits"] for f in fs),
            "custo_usd": round(sum(f["custo_usd"] for f in fs), 4),
            "eta_seg": round(pend * 1.05),
            "criado_em": p["criado_em"], "concluido_em": p["concluido_em"],
            "fatias": [{"n": f["n"], "status": f["status"], "leads": f["leads"],
                        "arquivos": json.loads(f["arquivos"] or "{}"),
                        "erro": f["erro"]} for f in fs],
        }

    def cancelar(self, pid: str) -> int:
        """Para depois da fatia corrente. O que já ficou pronto é preservado."""
        cur = self.db.execute(
            "UPDATE fatias SET status='cancelado' WHERE pedido_id=? AND status='pendente'",
            [pid])
        self.db.execute(
            "UPDATE pedidos SET status='cancelado', concluido_em=? WHERE id=?",
            [_agora(), pid])
        self.db.commit()
        return cur.rowcount

    def estado(self) -> dict:
        q = lambda s, *a: self.db.execute(s, a).fetchone()[0]
        return {
            "pedidos_ativos": q("SELECT COUNT(*) FROM pedidos WHERE status IN "
                                "('pendente','executando')"),
            "fatias_na_fila": q("SELECT COUNT(*) FROM fatias WHERE status='pendente'"),
            "fatias_executando": q("SELECT COUNT(*) FROM fatias WHERE status='executando'"),
        }

    def marcar(self, chave: str, valor: str):
        self.db.execute("INSERT OR REPLACE INTO servico VALUES (?,?)", [chave, valor])
        self.db.commit()

    def ler(self, chave: str):
        r = self.db.execute("SELECT valor FROM servico WHERE chave=?", [chave]).fetchone()
        return r["valor"] if r else None
