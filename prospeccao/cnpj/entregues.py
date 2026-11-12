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

E exclui POR CLIENTE. A mesma empresa pode ir para o cliente A e para o
cliente B; nunca duas vezes para o mesmo. Era global até 12/11, o que dava
exclusividade entre clientes e esgotava a base muito mais rápido do que o
negócio precisa.
"""
from __future__ import annotations

from pathlib import Path

import duckdb

from . import config

ARQUIVO = config.DADOS / "entregues.duckdb"

# Rótulo das linhas que já existiam quando o registro virou por cliente.
# Elas não têm cliente, e NÃO são distribuídas por adivinhação: recebem este
# rótulo único, e quem souber de quem eram troca depois, com um UPDATE.
CLIENTE_ANTIGO = "cliente-1"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS entregues (
  cliente       VARCHAR NOT NULL,
  cnpj          VARCHAR NOT NULL,
  cnpj_basico   VARCHAR NOT NULL,
  razao_social  VARCHAR,
  lote_id       VARCHAR NOT NULL,
  entregue_em   TIMESTAMP NOT NULL,
  filtro_usado  VARCHAR,
  PRIMARY KEY (cliente, cnpj)
);
CREATE INDEX IF NOT EXISTS ix_entregues_basico ON entregues(cliente, cnpj_basico);
CREATE INDEX IF NOT EXISTS ix_entregues_lote   ON entregues(lote_id);
"""


def _con(arquivo: Path | None = None, somente_leitura=False):
    alvo = Path(arquivo or ARQUIVO)
    alvo.parent.mkdir(parents=True, exist_ok=True)
    if somente_leitura and not alvo.exists():
        duckdb.connect(str(alvo)).execute(_ESQUEMA)
    con = duckdb.connect(str(alvo), read_only=somente_leitura)
    if not somente_leitura:
        # Migrar ANTES do esquema, não depois: o esquema cria o índice
        # (cliente, cnpj_basico), e numa tabela antiga essa coluna ainda não
        # existe — o CREATE INDEX falha e nem chega na migração.
        _migrar(con)
        con.execute(_ESQUEMA)
    return con


def _migrar(con) -> None:
    """
    Põe a coluna `cliente` numa tabela que nasceu sem ela.

    CREATE TABLE IF NOT EXISTS não altera tabela existente, então sem isto o
    registro de uma VM em uso continuaria com o esquema antigo e toda consulta
    por cliente falharia. Não dá para trocar a chave primária com ALTER, então
    a tabela é refeita e o conteúdo migra inteiro, sob CLIENTE_ANTIGO.
    """
    # information_schema, não PRAGMA: o PRAGMA do DuckDB levanta Catalog Error
    # quando a tabela não existe, e aqui ela pode não existir ainda.
    existe = con.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'entregues'").fetchone()
    if not existe:
        return
    tem = {r[0] for r in con.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'entregues'").fetchall()}
    if "cliente" in tem:
        return
    n_antes = con.execute("SELECT COUNT(*) FROM entregues").fetchone()[0]
    con.execute("ALTER TABLE entregues RENAME TO entregues_sem_cliente")
    con.execute(_ESQUEMA)
    con.execute(
        "INSERT INTO entregues "
        "SELECT ?, cnpj, cnpj_basico, razao_social, lote_id, entregue_em, "
        "       filtro_usado FROM entregues_sem_cliente", [CLIENTE_ANTIGO])
    n_depois = con.execute("SELECT COUNT(*) FROM entregues").fetchone()[0]
    if n_depois != n_antes:
        # Não apaga a tabela antiga se perdeu linha: melhor sobrar lixo do que
        # perder o registro de quem já foi entregue.
        raise RuntimeError(
            f"migração perdeu linhas: {n_antes} antes, {n_depois} depois. "
            "A tabela antiga foi preservada como entregues_sem_cliente.")
    con.execute("DROP TABLE entregues_sem_cliente")
    print(f"  registro migrado: {n_depois} entregas sob '{CLIENTE_ANTIGO}'")


def registrar(leads: list[dict], lote_id: str, filtro: str = "",
              arquivo=None, cliente: str = CLIENTE_ANTIGO) -> int:
    """
    Marca como entregues PARA ESTE CLIENTE. Chamado só quando a fatia foi
    entregue de verdade — fatia que falha no meio não marca ninguém.

    Empresa que já estava marcada para este cliente não conta de novo: o
    INSERT OR IGNORE preserva a data e o lote da PRIMEIRA entrega, que é o
    que a planilha mostra ao cliente quando a empresa vem repetida.
    """
    linhas = [(cliente, l["cnpj"], (l.get("cnpj_base") or l["cnpj"][:8]),
               l.get("razao_social"), lote_id, filtro)
              for l in leads if l.get("cnpj")]
    if not linhas:
        return 0
    con = _con(arquivo)
    antes = con.execute("SELECT COUNT(*) FROM entregues WHERE cliente=?",
                        [cliente]).fetchone()[0]
    con.executemany(
        "INSERT OR IGNORE INTO entregues VALUES (?,?,?,?,?,now(),?)", linhas)
    depois = con.execute("SELECT COUNT(*) FROM entregues WHERE cliente=?",
                         [cliente]).fetchone()[0]
    con.close()
    return depois - antes


def ja_entregues(arquivo=None, cliente: str = CLIENTE_ANTIGO) -> set[str]:
    """Os cnpj_basico já entregues A ESTE CLIENTE."""
    con = _con(arquivo, somente_leitura=True)
    r = {x[0] for x in con.execute(
        "SELECT DISTINCT cnpj_basico FROM entregues WHERE cliente=?",
        [cliente]).fetchall()}
    con.close()
    return r


def marcar(leads: list[dict], cliente: str, arquivo=None) -> int:
    """
    Preenche `ja_entregue` e `entregue_antes_em` em cada lead, lendo o
    registro como ele está AGORA. Altera a lista no lugar. Devolve quantas
    vieram repetidas.

    Por que aqui e não na consulta: a consulta marca, mas a fila guarda só a
    lista de CNPJs — as colunas se perdiam no caminho e nunca chegavam na
    planilha. Marcar na hora de escrever também é mais correto: o registro
    pode ter mudado entre o pedido e a execução da fatia.

    Tem de rodar ANTES de `registrar`. Depois, tudo apareceria como repetido.
    """
    if not leads:
        return 0
    con = _con(arquivo, somente_leitura=True)
    try:
        bases = {(l.get("cnpj_base") or (l.get("cnpj") or "")[:8]) for l in leads}
        bases.discard("")
        if not bases:
            return 0
        marcas = dict(con.execute(
            "SELECT cnpj_basico, MIN(entregue_em) FROM entregues "
            "WHERE cliente = ? AND cnpj_basico IN "
            f"({','.join('?' * len(bases))}) GROUP BY cnpj_basico",
            [cliente, *sorted(bases)]).fetchall())
    finally:
        con.close()

    n = 0
    for l in leads:
        base = l.get("cnpj_base") or (l.get("cnpj") or "")[:8]
        quando = marcas.get(base)
        l["ja_entregue"] = "SIM" if quando else ""
        l["entregue_antes_em"] = (quando.strftime("%d/%m/%Y")
                                  if hasattr(quando, "strftime") else quando) or ""
        n += 1 if quando else 0
    return n


def clientes(arquivo=None) -> list[tuple]:
    """Quem já recebeu alguma coisa, e quanto."""
    con = _con(arquivo, somente_leitura=True)
    r = con.execute("SELECT cliente, COUNT(*) n, MAX(entregue_em) ultimo "
                    "FROM entregues GROUP BY cliente ORDER BY n DESC").fetchall()
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
