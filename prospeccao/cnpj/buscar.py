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
    from .carregar import ajustar
    ajustar(con, leitura=True)       # teto de memória: a VM tem 1 GB
    from . import entregues as _e
    if _e.ARQUIVO.exists():
        # IF NOT EXISTS é obrigatório: conexões para o mesmo arquivo compartilham
        # a instância dentro do processo, então o anexo sobrevive entre elas.
        # Sem isso, a segunda requisição do serviço morre com "ent already exists".
        con.execute(f"ATTACH IF NOT EXISTS '{_e.ARQUIVO}' AS ent (READ_ONLY)")
    return con


def _tem_registro() -> bool:
    from . import entregues as _e
    return _e.ARQUIVO.exists()


def _lista(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = [x.strip() for x in v.split(",")]
    return [str(x).strip() for x in v if str(x).strip()]


def _onde(uf, cnae, situacao, porte, municipio,
          apenas_matriz=False, excluir_entregues=True,
          cliente=None):
    cond, par = [], []

    # Empresa já entregue nunca volta. A exclusão acontece AQUI, no filtro, e
    # não depois: gastar requisição do EmpresAqui numa empresa que seria
    # descartada desperdiça tempo e cota. Exclui por cnpj_basico — entregue a
    # matriz, a filial não volta disfarçada de lead novo.
    if excluir_entregues:
        from . import entregues as _e
        if _e.ARQUIVO.exists():
            cond.append("NOT EXISTS (SELECT 1 FROM ent.entregues t "
                        " WHERE t.cnpj_basico = e.cnpj_basico AND t.cliente = ?)")
            par.append(cliente)
            # NOT EXISTS, não NOT IN: com NOT IN, um único cnpj_basico
            # nulo no registro faz a condição inteira devolver zero
            # linhas — toda pesquisa voltaria vazia, sem erro nenhum.
            #
            # E por cliente: a mesma empresa pode ir para dois clientes, só
            # não duas vezes para o mesmo.

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

    return (" WHERE " + " AND ".join(cond) if cond else ""), par


_CAMPOS = """
SELECT
  e.cnpj_basico || e.cnpj_ordem || e.cnpj_dv            AS cnpj,
  em.razao_social,
  CASE e.situacao_cadastral WHEN '02' THEN 'ATIVA' WHEN '2' THEN 'ATIVA'
       WHEN '01' THEN 'NULA' WHEN '03' THEN 'SUSPENSA'
       WHEN '04' THEN 'INAPTA' WHEN '08' THEN 'BAIXADA'
       ELSE e.situacao_cadastral END                     AS situacao,
  CASE e.matriz_filial WHEN '1' THEN 'MATRIZ' ELSE 'FILIAL' END AS matriz_filial,
  e.uf,
  m.descricao                                            AS municipio,
  e.cnae_principal,
  c.descricao                                            AS cnae_descricao,
  CASE em.porte WHEN '01' THEN 'MICROEMPRESA' WHEN '03' THEN 'PEQUENO PORTE'
       WHEN '05' THEN 'MEDIO/GRANDE PORTE' ELSE 'NAO INFORMADO' END AS porte
-- O índice responde UMA pergunta: quais CNPJs existem em tal estado, cidade e
-- CNAE. Nome fantasia, bairro, abertura, telefone, e-mail e capital social NÃO
-- entram — tudo isso vem da API do EmpresAqui, e guardar aqui era duplicata
-- que custava disco e memória numa máquina de 1 GB.
"""

_DE = """
FROM estabelecimentos e
LEFT JOIN empresas   em ON em.cnpj_basico = e.cnpj_basico
LEFT JOIN municipios m  ON m.codigo       = e.municipio
LEFT JOIN cnaes      c  ON c.codigo       = e.cnae_principal
"""

# As duas colunas que marcam a repetida, e a junta que as alimenta.
#
# A junta é com uma AGREGAÇÃO, não com a tabela crua: o registro guarda uma
# linha por estabelecimento (cnpj), e uma empresa tem vários. Juntar direto
# por cnpj_basico MULTIPLICARIA a linha da empresa pelo número de
# estabelecimentos dela já entregues — uma lista de 100 voltaria com 130.
#
# MIN(entregue_em) é a PRIMEIRA entrega, que é a data que o cliente precisa
# ver: "você já pegou esta empresa naquela lista".
_MARCA_CAMPOS = """,
  CASE WHEN ja.primeiro IS NULL THEN '' ELSE 'SIM' END   AS ja_entregue,
  ja.primeiro                                            AS entregue_antes_em"""

_MARCA_DE = """
LEFT JOIN (SELECT cnpj_basico, MIN(entregue_em) AS primeiro
           FROM ent.entregues WHERE cliente = ? GROUP BY cnpj_basico) ja
       ON ja.cnpj_basico = e.cnpj_basico
"""

# Uma ordem só, e estável. A ordem importa porque empresa entregue nunca
# volta: quem fica fora dos primeiros 100 vai para a lista seguinte. Ordenar
# por CNPJ garante que a fatia 1 de hoje é a mesma fatia 1 de amanhã.
ORDENS = {"cnpj": "cnpj"}


def contar(db=None, **f) -> int:
    """
    Conta antes de gastar. O portão do funil começa aqui.

    Junta só a tabela que o filtro usar. Medido na VM de 1 GB, com SC + CNAE
    13 + matriz: 2,5 s com os dois LEFT JOIN, 0,129 s sem eles. Vinte vezes.

    A causa é que o DuckDB não tem como provar que `empresas` tem no máximo
    uma linha por CNPJ — não existe chave declarada —, então é obrigado a
    executar o cruzamento contra 27 milhões de linhas para contar 7.822, mesmo
    que nenhuma coluna das tabelas juntadas apareça no WHERE.
    """
    onde, par = _onde(f.get("uf"), f.get("cnae"), f.get("situacao", "ativa"),
                      f.get("porte"), f.get("municipio"),
                      f.get("apenas_matriz", False),
                      f.get("excluir_entregues", True),
                      f.get("cliente"))
    con = _conectar(db)
    sql = "SELECT COUNT(*) FROM estabelecimentos e" + _juntas(f) + onde
    n = con.execute(sql, par).fetchone()[0]
    con.close()
    return n


def _juntas(f: dict) -> str:
    """Só as tabelas que o filtro realmente consulta."""
    sql = ""
    if f.get("porte"):
        sql += " LEFT JOIN empresas em ON em.cnpj_basico = e.cnpj_basico"
    if f.get("municipio"):
        sql += " LEFT JOIN municipios m ON m.codigo = e.municipio"
    return sql


def buscar(db=None, uf=None, cnae=None, situacao="ativa", porte=None,
           municipio=None, apenas_matriz=False,
           excluir_entregues=True, ordenar="cnpj", limite=None,
           cliente=None, marcar_entregues=False) -> list[dict]:
    """
    `marcar_entregues` é o terceiro modo, e é de produto, não técnico.

    Quando o cliente pede 100 e só 50 são novas, entregar 50 caladamente
    parece erro. Com este modo ele recebe as 100, e as 50 que já tinha vêm
    com `ja_entregue` e `entregue_antes_em` preenchidos — então ele vê que a
    pesquisa rodou, que o filtro está esgotando, e que é hora de abrir o
    critério.

    `excluir_entregues` e `marcar_entregues` são opostos: o primeiro tira a
    repetida da lista, o segundo a mantém e rotula.
    """
    if marcar_entregues:
        excluir_entregues = False
    onde, par = _onde(uf, cnae, situacao, porte, municipio,
                      apenas_matriz, excluir_entregues, cliente)
    marca = marcar_entregues and _tem_registro()
    sql = (_CAMPOS + (_MARCA_CAMPOS if marca else "") + _DE
           + (_MARCA_DE if marca else "") + onde
           + f" ORDER BY {ORDENS.get(ordenar, ORDENS['cnpj'])}")
    # O parâmetro da junta vem ANTES dos do WHERE: posição, não nome.
    if marca:
        par = [cliente] + par
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
