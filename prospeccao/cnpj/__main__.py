"""
Pipeline de prospecção por CNPJ.

    python -m cnpj baixar                      # base da Receita (uma vez)
    python -m cnpj carregar
    python -m cnpj conferir

    python -m cnpj cnaes --busca tecelagem     # achar o código

    # PORTA A — filtro (topo do funil)
    python -m cnpj buscar --uf SC,PR --cnae 13 --contar
    python -m cnpj buscar --uf SC,PR --cnae 13 --limite 300 --out lista.csv

    # PORTA B — planilha com CNPJs
    python -m cnpj planilha minha_lista.xlsx --out lista.csv

    # enriquecimento (1 req/s) → CSV final
    python -m cnpj enriquecer lista.csv --out leads.csv
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import buscar as mod_buscar
from . import carregar as mod_carregar
from . import config, exportar
from .empresaqui import EmpresAqui, TokenInvalido, achatar, normalizar


def _ok(msg):   print(f"  \033[32m✓\033[0m {msg}")
def _erro(msg): print(f"  \033[31m✗\033[0m {msg}")
def _n(x):      return f"{x:,}".replace(",", ".")


# ──────────────────────────────────────────────── comandos

def cmd_testar(a):
    api = EmpresAqui()
    for cnpj in a.cnpjs:
        n = normalizar(cnpj)
        if not n:
            _erro(f"{cnpj}: CNPJ inválido (dígito verificador não bate)")
            continue
        t = time.time()
        r = api.consultar(n[0])
        dt = time.time() - t
        if r.http != 200 or not r.dados:
            _erro(f"{n[0]}: HTTP {r.http}")
            continue
        linhas = achatar(r.dados)
        for L in linhas:
            enr = any(v for k, v in L.items() if k.startswith("enr_"))
            _ok(f"{L['cnpj']}  {L['razao_social']}")
            print(f"      {L['municipio']}/{L['uf']} · {L['situacao']} · {L['porte']}")
            print(f"      tel {L['telefone_1'] or '—'} · whats {L['enr_whatsapp_principal'] or '—'}"
                  f" · email {L['enr_email_principal'] or L['email'] or '—'}")
            print(f"      sócio-adm: {L['socio_admin'] or '—'}")
            print(f"      enrichment: {'PREENCHIDO' if enr else 'VAZIO (plano sem Plus?)'}"
                  f"  ({dt:.2f}s{' · cache' if r.do_cache else ''})")
    print("\n ", api.estatisticas())


def cmd_baixar(a):
    print("Baixando base pública de CNPJ (Parquet):")
    arquivos = mod_carregar.baixar(apenas_essenciais=not a.completo)
    _ok(f"{len(arquivos)} arquivo(s) em {config.BRUTO}")


def cmd_montar(a):
    """Baixa, carrega e apaga um arquivo por vez — cabe em disco pequeno."""
    print("Montando o índice (baixa, carrega e apaga um arquivo por vez):")
    resumo = mod_carregar.montar(apagar_parquet=not a.manter_parquet)
    _ok(f"{len(resumo)} tabela(s) · " +
        " · ".join(f"{k} {_n(v)}" for k, v in resumo.items()))
    import os
    tam = os.path.getsize(config.DB) / 1e9
    print(f"      índice: {tam:.2f} GB")


def cmd_carregar(a):
    print("Carregando no DuckDB:")
    resumo = mod_carregar.carregar()
    if not resumo:
        _erro("nenhum Parquet encontrado — rode `baixar` antes")
        return 1
    _ok(f"{len(resumo)} tabela(s) em {config.DB}")


def cmd_conferir(a):
    mod_carregar.conferir()


def cmd_cnaes(a):
    r = mod_buscar.cnaes_disponiveis(prefixo=a.prefixo, busca=a.busca)
    for cod, desc in r[: a.limite]:
        print(f"  {cod}  {desc}")
    print(f"\n  {len(r)} CNAE(s)")


def cmd_buscar(a):
    f = dict(uf=a.uf, cnae=a.cnae, situacao=a.situacao, porte=a.porte,
             municipio=a.municipio, capital_min=a.capital_min,
             apenas_matriz=a.apenas_matriz)

    total = mod_buscar.contar(**f)
    print(f"\n  {_n(total)} empresas batem com o filtro")

    if a.contar:
        return
    if not total:
        return

    # O PORTÃO: o filtro é grátis e ilimitado, o enriquecimento é 1 req/s.
    # Nunca manda o resultado bruto do filtro pro enriquecimento.
    if a.limite:
        print(f"  cortando as {_n(a.limite)} melhores por '{a.ordenar}'")
    elif total > 1000:
        print(f"  \033[33m⚠ sem --limite.\033[0m Enriquecer {_n(total)} a 1 req/s "
              f"levaria {total/3600:.1f} h. Considere --limite.")

    linhas = mod_buscar.buscar(limite=a.limite, ordenar=a.ordenar, **f)
    destino = exportar.escrever_csv(linhas, a.out or config.SAIDA / "lista.csv")
    _ok(f"{_n(len(linhas))} linhas → {destino}")
    for L in linhas[:5]:
        print(f"      {L['cnpj']}  {(L['razao_social'] or '')[:46]:46} {L['uf']} "
              f"{(L['municipio'] or '')[:18]}")


def cmd_planilha(a):
    cnpjs, info = exportar.ler_cnpjs(a.arquivo)
    print(f"\n  linhas lidas:        {_n(info['linhas'])}")
    print(f"  coluna detectada:    índice {info.get('coluna_detectada')}")
    _ok(f"CNPJs válidos:       {_n(info.get('validos', 0))}")
    if info.get("invalidos_descartados"):
        print(f"  descartados (DV):    {_n(info['invalidos_descartados'])}"
              f"   \033[33m← não viram requisição\033[0m")
    if not cnpjs:
        _erro("nenhum CNPJ aproveitável na planilha")
        return 1
    destino = exportar.escrever_csv([{"cnpj": c} for c in cnpjs],
                                    a.out or config.SAIDA / "lista.csv",
                                    colunas=["cnpj"])
    _ok(f"→ {destino}")


def cmd_enriquecer(a):
    cnpjs, info = exportar.ler_cnpjs(a.arquivo)
    if a.limite:
        cnpjs = cnpjs[: a.limite]
    if not cnpjs:
        _erro("nenhum CNPJ na entrada")
        return 1

    api = EmpresAqui()
    em_cache = sum(1 for c in cnpjs if api._do_cache(c) is not None)
    faltam = len(cnpjs) - em_cache
    print(f"\n  {_n(len(cnpjs))} CNPJs · {_n(em_cache)} em cache · "
          f"{_n(faltam)} a consultar (~{faltam * config.INTERVALO_SEG / 60:.1f} min)")

    destino = a.out or config.SAIDA / "leads.csv"
    tamanho = max(1, a.lote)
    linhas, erros, t0 = [], 0, time.time()

    # Processa em lotes: grava parcial a cada lote, então queda no meio
    # não perde o que já foi consultado (e o cache cobre a retomada).
    for inicio in range(0, len(cnpjs), tamanho):
        bloco = cnpjs[inicio:inicio + tamanho]
        do_bloco = []
        for r in api.consultar_lote(bloco):
            if r.http == 200 and r.dados:
                do_bloco += achatar(r.dados)
            else:
                erros += 1

        if a.apify and do_bloco:
            try:
                from . import apify
                resumo = apify.enriquecer_lote(
                    do_bloco, usar_maps=True, usar_ig=True,
                    usar_li=a.linkedin, teto_usd=a.teto_usd)
                print(f"\n      apify: {resumo}")
            except apify.SemToken as e:
                _erro(f"{e}  (seguindo sem Apify)")
                a.apify = False
            except Exception as e:
                _erro(f"apify falhou neste lote: {e}")

        linhas += do_bloco
        exportar.escrever_csv(linhas, destino)      # parcial a cada lote
        feitos = min(inicio + tamanho, len(cnpjs))
        print(f"\r  {feitos}/{len(cnpjs)}  ok={len(linhas)} erros={erros} "
              f"{time.time()-t0:.0f}s", end="", flush=True)
    print()

    destino = exportar.escrever_csv(linhas, destino)
    _ok(f"{_n(len(linhas))} leads → {destino}")
    com = lambda k: sum(1 for l in linhas if l.get(k))
    print(f"      whatsapp {com('enr_whatsapp_principal')} · "
          f"email {com('enr_email_principal')} · "
          f"instagram {com('enr_instagram_principal')} · "
          f"decisor {com('socio_admin')}")


# ──────────────────────────────────────────────── cli

def main(argv=None):
    p = argparse.ArgumentParser("cnpj", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("testar", help="testa a API com CNPJs")
    s.add_argument("cnpjs", nargs="+")
    s.set_defaults(fn=cmd_testar)

    s = sub.add_parser("baixar", help="baixa a base da Receita")
    s.add_argument("--completo", action="store_true", help="inclui sócios e Simples")
    s.set_defaults(fn=cmd_baixar)

    s = sub.add_parser("montar", help="baixa+carrega+apaga por arquivo (disco pequeno)")
    s.add_argument("--manter-parquet", action="store_true", dest="manter_parquet")
    s.set_defaults(fn=cmd_montar)

    s = sub.add_parser("carregar", help="carrega os Parquet já baixados")
    s.set_defaults(fn=cmd_carregar)

    s = sub.add_parser("conferir", help="confere a base carregada")
    s.set_defaults(fn=cmd_conferir)

    s = sub.add_parser("cnaes", help="procura código CNAE")
    s.add_argument("--prefixo")
    s.add_argument("--busca")
    s.add_argument("--limite", type=int, default=40)
    s.set_defaults(fn=cmd_cnaes)

    s = sub.add_parser("buscar", help="PORTA A — filtro por UF/CNAE/porte")
    s.add_argument("--uf"); s.add_argument("--cnae"); s.add_argument("--municipio")
    s.add_argument("--porte"); s.add_argument("--situacao", default="ativa")
    s.add_argument("--capital-min", type=float, dest="capital_min")
    s.add_argument("--matriz", action="store_true", dest="apenas_matriz",
                   help="só matrizes — evita 9 filiais do mesmo banco")
    s.add_argument("--ordenar", default="capital",
                   choices=list(mod_buscar.ORDENS))
    s.add_argument("--limite", type=int)
    s.add_argument("--contar", action="store_true", help="só conta, não exporta")
    s.add_argument("--out")
    s.set_defaults(fn=cmd_buscar)

    s = sub.add_parser("planilha", help="PORTA B — lê CNPJs de .xlsx/.csv")
    s.add_argument("arquivo"); s.add_argument("--out")
    s.set_defaults(fn=cmd_planilha)

    s = sub.add_parser("enriquecer", help="EmpresAqui 1 req/s → CSV final")
    s.add_argument("arquivo"); s.add_argument("--out")
    s.add_argument("--limite", type=int)
    s.add_argument("--lote", type=int, default=10,
                   help="grava parcial a cada N (padrão 10)")
    s.add_argument("--apify", action="store_true",
                   help="roda Maps + Instagram em 100%% do lote")
    s.add_argument("--linkedin", action="store_true",
                   help="inclui decisor via LinkedIn (caro)")
    s.add_argument("--teto-usd", type=float, default=5.0, dest="teto_usd")
    s.set_defaults(fn=cmd_enriquecer)

    a = p.parse_args(argv)
    try:
        return a.fn(a) or 0
    except TokenInvalido as e:
        _erro(f"{e}\n    export EMPRESAQUI_TOKEN=...")
        return 2
    except FileNotFoundError as e:
        _erro(f"arquivo não encontrado: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
