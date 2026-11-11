"""
O filtro mestre — topo do funil.

Roda sobre a base da Receita no disco: grátis, sem limite de requisição,
devolve dezenas de milhares em segundos. É o que a API do EmpresAqui NÃO
faz (ela só consulta por CNPJ, não busca por critério).

    buscar(uf=["SC","PR"], cnae=["13","14"], situacao="ativa")
"""
from __future__ import annotations

import duckdb

from . import config

# Teto por pesquisa, definido pelo cliente. Erro explícito em vez de corte
# silencioso: truncar sem avisar devolveria lista errada parecendo certa.
MAX_CNAES = 2


class CnaesDemais(ValueError):
    pass


SITUACAO_COD = {"ativa": "02", "nula": "01", "suspensa": "03",
                "inapta": "04", "baixada": "08"}
PORTE_COD = {"mei": "01", "micro": "01", "pequeno": "03",
             "medio": "05", "grande": "05", "demais": "05"}


def _conectar(db=None):
    """Base em somente-leitura, com o registro de entregues anexado como `ent`."""
    con = duckdb.connect(str(db or config.DB), read_only=True)
    from . import entregues as _e
    if _e.ARQUIVO.exists():
        # IF NOT EXISTS é obrigatório: conexões para o mesmo arquivo compartilham
        # a instância dentro do processo, então o anexo sobrevive entre elas.
        # Sem isso, a segunda requisição do serviço morre com "ent already exists".
        con.execute(f"ATTACH IF NOT EXISTS '{_e.ARQUIVO}' AS ent (READ_ONLY)")
    return con


def _lista(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",")]
    return [str(x).strip() for x in v if str(x).strip()]


def _onde(uf, cnae, situacao, porte, municipio, capital_min,
          abertura_de, abertura_ate, com_contato, apenas_matriz=False,
          excluir_entregues=True):
    cond, par = [], []

    # Empresa já entregue nunca volta. A exclusão acontece AQUI, no filtro, e
    # não depois: gastar requisição do EmpresAqui numa empresa que seria
    # descartada desperdiça tempo e cota. Exclui por cnpj_basico — entregue a
    # matriz, a filial não volta disfarçada de lead novo.
    if excluir_entregues:
        from . import entregues as _e
        if _e.ARQUIVO.exists():
            cond.append("e.cnpj_basico NOT IN (SELECT cnpj_basico FROM ent.entregues)")

    # Sem isso, "as 10 maiores de SC" devolve 9 agências do mesmo banco.
    # Uma agência não é um lead; a empresa é.
    if apenas_matriz:
        cond.append("e.matriz_filial = '1'")

    if uf := _lista(uf):
        cond.append(f"e.uf IN ({','.join('?' * len(uf))})")
        par += [u.upper() for u in uf]

    # CNAE por PREFIXO: "13" pega a divisão inteira, "1322300" pega o código exato.
    if cnae := _lista(cnae):
        if len(cnae) > MAX_CNAES:
            raise CnaesDemais(
                f"{len(cnae)} CNAEs pedidos; o máximo por pesquisa é {MAX_CNAES}. "
                f"Rode uma pesquisa para cada grupo.")
        ors = []
        for c in cnae:
            c = "".join(ch for ch in c if ch.isdigit())
            if not c:
                continue
            ors.append("e.cnae_principal LIKE ?")
            par.append(c + "%")
        if ors:
            cond.append("(" + " OR ".join(ors) + ")")

    if situacao:
        if situacao == "todas":
            pass
        else:
            cods = [SITUACAO_COD.get(s.lower(), s) for s in _lista(situacao)]
            # a base usa 2 dígitos ("02"); aceitamos 1 dígito também
            todos = sorted({c.zfill(2) for c in cods} | {c.lstrip("0") for c in cods})
            cond.append(f"e.situacao_cadastral IN ({','.join('?' * len(todos))})")
            par += todos

    if porte := _lista(porte):
        cods = sorted({PORTE_COD.get(p.lower(), p).zfill(2) for p in porte})
        cond.append(f"em.porte IN ({','.join('?' * len(cods))})")
        par += cods

    if municipio := _lista(municipio):
        cond.append(f"({' OR '.join(['UPPER(m.descricao) LIKE ?'] * len(municipio))})")
        par += [f"%{x.upper()}%" for x in municipio]

    if capital_min is not None:
        cond.append("TRY_CAST(REPLACE(em.capital_social, ',', '.') AS DOUBLE) >= ?")
        par.append(float(capital_min))

    if abertura_de:
        cond.append("e.data_abertura >= ?")
        par.append(str(abertura_de).replace("-", ""))
    if abertura_ate:
        cond.append("e.data_abertura <= ?")
        par.append(str(abertura_ate).replace("-", ""))

    # Só quem já tem algum contato no cadastro — economiza requisição depois.
    if com_contato:
        cond.append("(NULLIF(TRIM(e.telefone_1),'') IS NOT NULL "
                    "OR NULLIF(TRIM(e.email),'') IS NOT NULL)")

    return (" WHERE " + " AND ".join(cond) if cond else ""), par


_SELECT = """
SELECT
  e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv            AS cnpj,
  em.razao_social,
  e.nome_fantasia,
  CASE e.situacao_cadastral WHEN '02' THEN 'ATIVA' WHEN '2' THEN 'ATIVA'
       WHEN '01' THEN 'NULA' WHEN '03' THEN 'SUSPENSA'
       WHEN '04' THEN 'INAPTA' WHEN '08' THEN 'BAIXADA'
       ELSE e.situacao_cadastral END                     AS situacao,
  CASE e.matriz_filial WHEN '1' THEN 'MATRIZ' ELSE 'FILIAL' END AS matriz_filial,
  e.uf,
  m.descricao                                            AS municipio,
  e.bairro,
  e.cnae_principal,
  c.descricao                                            AS cnae_descricao,
  CASE em.porte WHEN '01' THEN 'MICROEMPRESA' WHEN '03' THEN 'PEQUENO PORTE'
       WHEN '05' THEN 'MEDIO/GRANDE PORTE' ELSE 'NAO INFORMADO' END AS porte,
  TRY_CAST(REPLACE(em.capital_social, ',', '.') AS DOUBLE) AS capital_social,
  e.data_abertura,
  NULLIF(TRIM(e.ddd_1 || e.telefone_1), '')              AS telefone_1,
  NULLIF(TRIM(e.ddd_2 || e.telefone_2), '')              AS telefone_2,
  NULLIF(TRIM(e.email), '')                              AS email
FROM estabelecimentos e
LEFT JOIN empresas   em ON em.cnpj_basico = e.cnpj_basico
LEFT JOIN municipios m  ON m.codigo       = e.municipio
LEFT JOIN cnaes      c  ON c.codigo       = e.cnae_principal
"""

ORDENS = {
    "capital": "capital_social DESC NULLS LAST",
    "recentes": "e.data_abertura DESC",
    "antigas": "e.data_abertura ASC",
    # Prioriza quem já tem contato: menos requisição gasta no enriquecimento.
    "contato": "(CASE WHEN NULLIF(TRIM(e.email),'') IS NOT NULL THEN 2 ELSE 0 END + "
               "CASE WHEN NULLIF(TRIM(e.telefone_1),'') IS NOT NULL THEN 1 ELSE 0 END) DESC, "
               "capital_social DESC NULLS LAST",
}


def contar(db=None, **f) -> int:
    """Conta antes de gastar. O portão do funil começa aqui."""
    onde, par = _onde(f.get("uf"), f.get("cnae"), f.get("situacao", "ativa"),
                      f.get("porte"), f.get("municipio"), f.get("capital_min"),
                      f.get("abertura_de"), f.get("abertura_ate"),
                      f.get("com_contato"), f.get("apenas_matriz", False),
                      f.get("excluir_entregues", True))
    con = _conectar(db)
    sql = ("SELECT COUNT(*) FROM estabelecimentos e "
           "LEFT JOIN empresas em ON em.cnpj_basico = e.cnpj_basico "
           "LEFT JOIN municipios m ON m.codigo = e.municipio" + onde)
    n = con.execute(sql, par).fetchone()[0]
    con.close()
    return n


def buscar(db=None, uf=None, cnae=None, situacao="ativa", porte=None,
           municipio=None, capital_min=None, abertura_de=None, abertura_ate=None,
           com_contato=False, apenas_matriz=False, excluir_entregues=True,
           ordenar="capital", limite=None) -> list[dict]:
    onde, par = _onde(uf, cnae, situacao, porte, municipio, capital_min,
                      abertura_de, abertura_ate, com_contato, apenas_matriz,
                      excluir_entregues)
    sql = _SELECT + onde + f" ORDER BY {ORDENS.get(ordenar, ORDENS['capital'])}"
    if limite:
        sql += f" LIMIT {int(limite)}"
    con = _conectar(db)
    cur = con.execute(sql, par)
    nomes = [d[0] for d in cur.description]
    linhas = [dict(zip(nomes, r)) for r in cur.fetchall()]
    con.close()
    return linhas


def cnaes_disponiveis(db=None, prefixo=None, busca=None) -> list[tuple]:
    """Ajuda a descobrir o código certo: `cnaes(busca='tecelagem')`."""
    con = _conectar(db)
    cond, par = [], []
    if prefixo:
        cond.append("codigo LIKE ?")
        par.append(str(prefixo) + "%")
    if busca:
        cond.append("UPPER(descricao) LIKE ?")
        par.append(f"%{busca.upper()}%")
    sql = "SELECT codigo, descricao FROM cnaes"
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    r = con.execute(sql + " ORDER BY codigo", par).fetchall()
    con.close()
    return r
