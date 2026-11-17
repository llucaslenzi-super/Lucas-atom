"""
As opções dos menus da tela, tiradas da base.

A tela não alcança a VM — ela fala só com o n8n. Então estas listas são
calculadas aqui, uma vez por carga da base, e publicadas lá.

Por que vêm da base e não de uma tabela fixa do IBGE: só a base sabe quais
cidades e quais CNAEs têm empresa de verdade. Oferecer no menu um CNAE sem
nenhuma empresa é prometer uma pesquisa que volta vazia.
"""
from __future__ import annotations

import json

from . import buscar
from .setores import NOMES as NOMES_SETOR

# Só empresa ativa: é o universo que a pesquisa enxerga.
ATIVA = "situacao_cadastral = '02'"


def municipios(db=None) -> list[list]:
    """[uf, código, nome, quantas] — o código é o que vai no filtro."""
    con = buscar._conectar(db)
    try:
        return [[uf, cod, nome, n] for uf, cod, nome, n in con.execute(
            f"""SELECT e.uf, e.municipio, m.descricao, COUNT(*)
                FROM estabelecimentos e JOIN municipios m ON m.codigo = e.municipio
                WHERE {ATIVA} GROUP BY 1,2,3 ORDER BY 1,3""").fetchall()]
    finally:
        con.close()


def cnaes(db=None) -> list[list]:
    """[código, descrição, quantas] só dos que têm empresa ativa."""
    con = buscar._conectar(db)
    try:
        return [[c, d, n] for c, d, n in con.execute(
            f"""SELECT e.cnae_principal, c.descricao, COUNT(*)
                FROM estabelecimentos e JOIN cnaes c ON c.codigo = e.cnae_principal
                WHERE {ATIVA} GROUP BY 1,2 ORDER BY 2""").fetchall()]
    finally:
        con.close()


def setores(db=None) -> list[list]:
    """
    [dois dígitos, nome oficial, quantas] — o nível de cima do CNAE.

    O nome vem de `setores.py`, não da base: a Receita publica só a subclasse
    de 7 dígitos, e tirar o rótulo da atividade mais numerosa dava nome
    errado — a divisão 13 virava "Fabricação de outros produtos têxteis não
    especificados anteriormente", que é uma atividade dentro dela.

    Setor sem nenhuma empresa ativa não entra: oferecer no menu uma opção que
    volta vazia é prometer o que não existe.
    """
    con = buscar._conectar(db)
    try:
        linhas = con.execute(
            f"""SELECT substr(cnae_principal,1,2) d, COUNT(*) n
                FROM estabelecimentos WHERE {ATIVA} GROUP BY 1 ORDER BY 1""").fetchall()
    finally:
        con.close()
    return [[d, NOMES_SETOR.get(d, "Setor " + d), n] for d, n in linhas
            if d in NOMES_SETOR]


def matriz(db=None) -> list[list]:
    """
    [uf, cnae, quantas] — a contagem que a tela mostra enquanto a pessoa
    mexe nos filtros.

    Só matriz, como a pesquisa padrão. Município fica DE FORA de propósito:
    município × CNAE dá 1,4 milhão de células e 18,7 MB, grande demais para
    atravessar a rede toda vez. Com cidade escolhida, a tela mostra o número
    como teto e diz que é teto.
    """
    con = buscar._conectar(db)
    try:
        return [[u, c, n] for u, c, n in con.execute(
            f"""SELECT uf, cnae_principal, COUNT(*) FROM estabelecimentos
                WHERE {ATIVA} AND matriz_filial = '1'
                GROUP BY 1,2""").fetchall()]
    finally:
        con.close()


def tudo(db=None) -> dict[str, str]:
    """Cada lista já em JSON, pronta para virar uma linha de Data Table."""
    return {
        "municipios": json.dumps(municipios(db), ensure_ascii=False,
                                 separators=(",", ":")),
        "cnaes": json.dumps(cnaes(db), ensure_ascii=False,
                            separators=(",", ":")),
        "setores": json.dumps(setores(db), ensure_ascii=False,
                              separators=(",", ":")),
        "matriz": json.dumps(matriz(db), separators=(",", ":")),
    }
