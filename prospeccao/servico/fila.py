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
from datetime import datetime, timedelta, timezone
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
  cliente        TEXT,
  criado_em      TEXT,
  concluido_em   TEXT
);

CREATE TABLE IF NOT EXISTS fatias (
  pedido_id   TEXT NOT NULL,
  n           INTEGER NOT NULL,
  cnpjs       TEXT NOT NULL,      -- congelado na criação, não recalculado
  status      TEXT NOT NULL,      -- pendente|executando|pronto|erro|cancelado
  leads       INTEGER DEFAULT 0,
  repetidas   INTEGER DEFAULT 0,  -- já entregues antes a ESTE cliente
  processadas INTEGER DEFAULT 0,  -- quantas já foram consultadas, ao vivo
  requisicoes INTEGER DEFAULT 0,
  cache_hits  INTEGER DEFAULT 0,
  custo_usd   REAL,               -- NULL = não se sabe; 0 = foi de graça
  apify_erro  TEXT,               -- enriquecimento falhou ou foi pulado
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

# Fatia que ficou em 'executando' por mais tempo que isto é considerada órfã:
# worker morto, travado, ou máquina reiniciada. Uma fatia de 100 leva uns dois
# minutos a 1 req/s, então quinze é folga de sete vezes.
MINUTOS_ORFA = 15


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _agora_menos(minutos: int) -> str:
    return (datetime.now(timezone.utc)
            - timedelta(minutes=minutos)).isoformat(timespec="seconds")


class Fila:
    def __init__(self, arquivo: Path):
        self.arquivo = Path(arquivo)
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.arquivo), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(ESQUEMA)
        self._migrar()
        self.db.commit()

    def _migrar(self) -> None:
        """
        Coluna nova em base que já existe. CREATE TABLE IF NOT EXISTS não
        altera tabela criada antes, então sem isto a fila de uma VM em uso
        fica sem a coluna e o UPDATE falha.
        """
        tem = {c["name"] for c in self.db.execute("PRAGMA table_info(fatias)")}
        for coluna, tipo in (("apify_erro", "TEXT"), ("entregue_em", "TEXT"),
                             ("repetidas", "INTEGER DEFAULT 0"),
                             ("processadas", "INTEGER DEFAULT 0")):
            if coluna not in tem:
                self.db.execute(f"ALTER TABLE fatias ADD COLUMN {coluna} {tipo}")
        tem = {c["name"] for c in self.db.execute("PRAGMA table_info(pedidos)")}
        for coluna, tipo in (("cliente", "TEXT"), ("fechado_em", "TEXT")):
            if coluna not in tem:
                self.db.execute(f"ALTER TABLE pedidos ADD COLUMN {coluna} {tipo}")

    # ---------------------------------------------------------- criar
    def criar(self, cnpjs: list[str], *, filtro="", formatos=("xlsx",), blocos=None,
              com_apify=True, teto_usd=2.0, chave_idem=None,
              base_competencia=None, cliente=None) -> dict:
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
        # Colunas NOMEADAS, não posicionais. Com VALUES posicional, acrescentar
        # uma coluna no meio da tabela desloca tudo em silêncio: foi o que
        # aconteceu quando `cliente` entrou — o cliente passou a receber o
        # carimbo de data e o criado_em ficou nulo, sem erro nenhum.
        #
        # E a migração de uma base em uso acrescenta a coluna no FIM, então a
        # ordem física depende de quando o banco nasceu. Nomear resolve os dois.
        self.db.execute(
            "INSERT INTO pedidos (id, chave_idem, filtro, total_pedido, "
            "  tamanho_fatia, formatos, blocos, com_apify, teto_usd, status, "
            "  motivo, base_competencia, criado_em, concluido_em, cliente) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (pid, chave_idem, filtro, len(cnpjs), TAMANHO_LISTA,
             json.dumps(list(formatos)), json.dumps(blocos), int(com_apify),
             teto_usd, "pendente", None, base_competencia, _agora(), None,
             cliente))
        self.db.executemany(
            "INSERT INTO fatias (pedido_id,n,cnpjs,status) VALUES (?,?,?,'pendente')",
            [(pid, i, json.dumps(f)) for i, f in enumerate(fatias, 1)])
        self.db.commit()
        return {"id": pid, "fatias": len(fatias), "total": len(cnpjs),
                "eta_seg": round(len(cnpjs) * 1.05), "repetido": False}

    # ---------------------------------------------------------- worker
    def proxima_fatia(self) -> sqlite3.Row | None:
        """
        FIFO. Todas as fatias têm o mesmo tamanho, então não há prioridade.

        Pega fatia 'pendente' e também fatia 'executando' velha demais — ver
        MINUTOS_ORFA. Antes, a recuperação de órfã acontecia UMA vez, na
        partida do worker: worker vivo mas travado deixava a fatia em
        'executando' para sempre, e o pedido nunca terminava.

        E aceita pedido em QUALQUER estado menos 'cancelado'. Era lista
        branca — 'pendente', 'executando', 'pausado' — e isso travou duas
        vezes:

          · 'pausado' não estava na lista, e um token inválido congelava o
            pedido para sempre;
          · um pedido marcado 'pronto' por engano, com fatia ainda aberta,
            ficava invisível. Aconteceu na VM: o worker antigo marcou
            'pronto' numa fatia que deu erro, a fatia voltou para a fila e
            nunca mais foi pega.

        Lista branca precisa de alguém acertar todos os estados futuros.
        Lista negra de um só item — 'cancelado', que é o único em que NÃO se
        deve trabalhar — se cura sozinha. Fatia aberta é trabalho a fazer,
        qualquer que seja o rótulo do pedido.
        """
        limite = _agora_menos(MINUTOS_ORFA)
        cur = self.db.execute("""
            UPDATE fatias SET status='executando', iniciada_em=?
            WHERE (pedido_id, n) = (
              SELECT f.pedido_id, f.n FROM fatias f JOIN pedidos p ON p.id=f.pedido_id
              WHERE (f.status='pendente'
                     OR (f.status='executando' AND f.iniciada_em < ?))
                AND p.status <> 'cancelado'  
              ORDER BY p.criado_em, f.n LIMIT 1)
            RETURNING *""", [_agora(), limite])
        r = cur.fetchone()
        if r:
            # Sai de 'pausado' também: o que travou o pedido passou.
            self.db.execute(
                "UPDATE pedidos SET status='executando', motivo=NULL "
                "WHERE id=? AND status IN ('pendente','pausado')",
                [r["pedido_id"]])
            self.db.commit()
        return r

    def andamento(self, pid: str, n: int, feitas: int) -> None:
        """
        Quantas empresas desta fatia já foram consultadas. É o único número
        que existe enquanto a lista ainda não ficou pronta — sem ele a tela
        só teria "na fila" e silêncio por dois minutos.
        """
        self.db.execute(
            "UPDATE fatias SET processadas=? WHERE pedido_id=? AND n=?",
            [feitas, pid, n])
        self.db.commit()

    def progresso(self, pid: str) -> dict:
        """Soma do pedido: empresas andadas, listas prontas, listas no total."""
        r = self.db.execute(
            "SELECT COALESCE(SUM(processadas), 0) andadas,"
            "       SUM(status='pronto') prontas,"
            "       COUNT(*) listas "
            "FROM fatias WHERE pedido_id=?", [pid]).fetchone()
        return {"andadas": r["andadas"] or 0, "prontas": r["prontas"] or 0,
                "listas": r["listas"] or 0}

    def concluir_fatia(self, pid: str, n: int, *, leads=0, requisicoes=0,
                       cache_hits=0, custo=None, arquivos=None, erro=None,
                       apify_erro=None, repetidas=0):
        # custo=None é "não sei quanto custou", e é diferente de zero. Antes o
        # worker gravava 0.0 fixo e o campo era decoração.
        self.db.execute("""
            UPDATE fatias SET status=?, leads=?, repetidas=?, requisicoes=?,
                   cache_hits=?, custo_usd=?, apify_erro=?, arquivos=?,
                   erro=?, concluida_em=?
            WHERE pedido_id=? AND n=?""",
            ("erro" if erro else "pronto", leads, repetidas, requisicoes,
             cache_hits, custo, apify_erro, json.dumps(arquivos or {}), erro,
             _agora(), pid, n))
        # 'pronto' só quando TODAS as fatias deram certo. Antes esta contagem
        # ignorava as fatias em erro, então nove prontas e uma falhada viravam
        # um pedido 'pronto' — e o cliente recebia lista incompleta como
        # completa, que é a pior mentira que este sistema pode contar.
        resto = self.db.execute(
            "SELECT "
            " SUM(status IN ('pendente','executando')) abertas,"
            " SUM(status='erro') falhas "
            "FROM fatias WHERE pedido_id=?", [pid]).fetchone()
        if not resto["abertas"]:
            final = "parcial" if resto["falhas"] else "pronto"
            motivo = (f"{resto['falhas']} de "
                      f"{self._total_fatias(pid)} listas falharam"
                      if resto["falhas"] else None)
            self.db.execute(
                "UPDATE pedidos SET status=?, motivo=?, concluido_em=? WHERE id=?",
                [final, motivo, _agora(), pid])
        self.db.commit()

    def _total_fatias(self, pid: str) -> int:
        return self.db.execute("SELECT COUNT(*) c FROM fatias WHERE pedido_id=?",
                               [pid]).fetchone()["c"]

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
            "cliente": p["cliente"],
            "base_competencia": p["base_competencia"],
            "fatias_total": len(fs), "fatias_prontas": len(prontas),
            "leads": sum(f["leads"] for f in fs),
            "requisicoes": sum(f["requisicoes"] for f in fs),
            "cache_hits": sum(f["cache_hits"] for f in fs),
            # None em qualquer fatia contamina a soma: se não se sabe o custo
            # de uma, não se sabe o do pedido. Somar tratando None como zero
            # inventaria um número menor que o real.
            "custo_usd": (None if any(f["custo_usd"] is None
                                      for f in fs if f["status"] == "pronto")
                          else round(sum(f["custo_usd"] or 0 for f in fs), 4)),
            "apify_erros": [f["apify_erro"] for f in fs if f["apify_erro"]],
            "eta_seg": round(pend * 1.05),
            "criado_em": p["criado_em"], "concluido_em": p["concluido_em"],
            "fatias": [{"n": f["n"], "status": f["status"], "leads": f["leads"],
                        "arquivos": json.loads(f["arquivos"] or "{}"),
                        "custo_usd": f["custo_usd"],
                        "apify_erro": f["apify_erro"],
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

    # ---------------------------------------------------------- retenção
    def pedidos_para_limpar(self, dias=7) -> list[str]:
        """
        Pedidos concluídos há mais de `dias`, cujos arquivos podem sair do
        disco. `SAIDA/{pid}/` cresce para sempre num disco de 15 GB, e depois
        da entrega o arquivo que importa não está mais aqui.

        Só pedido CONCLUÍDO entra: pedido pausado ou em curso guarda os
        arquivos, mesmo velho.
        """
        corte = _agora_menos(dias * 24 * 60)
        return [r["id"] for r in self.db.execute(
            "SELECT id FROM pedidos WHERE status IN ('pronto','parcial','cancelado') "
            "AND concluido_em IS NOT NULL AND concluido_em < ?", [corte])]
