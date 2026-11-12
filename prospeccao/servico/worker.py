"""
Worker: pega uma fatia por vez e a processa inteira.

UM worker só, e isso é o desenho correto, não uma concessão: o limite de 1
requisição por segundo é do token, global. Dois workers não processam mais
rápido — processam a 2 req/s e levam 401.

O flock existe porque o incidente provável não é systemd duplicado; é alguém
rodando `python -m cnpj enriquecer` na VM "para testar" e dobrando a cadência.
"""
from __future__ import annotations

import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cnpj import config, entregues
from cnpj.empresaqui import EmpresAqui, TokenInvalido, achatar
from cnpj.exportar import escrever
from servico.fila import Fila

INTERVALO_OCIOSO = 5     # segundos entre varreduras quando não há trabalho
PAUSA_TOKEN = 60         # espera quando o token é recusado


def _trava():
    """Um worker, garantido pelo sistema de arquivos."""
    alvo = config.DADOS / "worker.lock"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    fh = open(alvo, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("outro worker já está rodando — saindo", flush=True)
        raise SystemExit(1)
    fh.write(str(os.getpid())); fh.flush()
    return fh


def processar(fila: Fila, fatia, api: EmpresAqui) -> None:
    pid, n = fatia["pedido_id"], fatia["n"]
    cnpjs = json.loads(fatia["cnpjs"])
    p = fila.db.execute("SELECT * FROM pedidos WHERE id=?", [pid]).fetchone()
    t0 = time.time()

    leads, req, hits = [], 0, 0
    try:
        for r in api.consultar_lote(cnpjs):
            if r.do_cache:
                hits += 1
            else:
                req += 1
            if r.http == 200 and r.dados:
                leads += achatar(r.dados)
    except TokenInvalido as e:
        # A fatia volta para a fila e o worker ESPERA. Sair faria o systemd
        # reiniciar em laço quente e esconder o motivo.
        fila.devolver_fatia(pid, n, f"token recusado: {e}")
        fila.marcar("pausado_por", "token_empresaqui")
        print(f"[{pid}/{n}] token recusado — pausando {PAUSA_TOKEN}s", flush=True)
        time.sleep(PAUSA_TOKEN)
        return

    custo, apify_erro = None, None
    if p["com_apify"] and leads:
        try:
            from cnpj import apify
            resumo = apify.enriquecer_lote(leads, usar_maps=True, usar_ig=True,
                                           usar_li=False, teto_usd=p["teto_usd"])
            custo = resumo.get("custo_usd")
            if resumo.get("pulados"):
                # Teto batido no meio: parte do enriquecimento não rodou, e
                # isso tem de aparecer no pedido, não só no log.
                apify_erro = ("teto de US$ "
                              f"{p['teto_usd']} batido; não rodou: "
                              + ", ".join(resumo["pulados"]))
            print(f"[{pid}/{n}] apify: {resumo}", flush=True)
        except Exception as e:
            # Antes isto era engolido com um print: a fatia ficava pronta sem
            # enriquecimento nenhum e nada no pedido dizia isso. Lead sem
            # contato parecia empresa sem contato.
            apify_erro = f"{type(e).__name__}: {e}"[:200]
            print(f"[{pid}/{n}] apify falhou (seguindo sem): {e}", flush=True)

    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    comp = p["base_competencia"]
    for l in leads:
        l["lote_id"] = f"{pid}-{n}"
        l["extraido_em"] = agora
        l["base_competencia"] = comp

    destino = config.SAIDA / pid / f"fatia-{n:03d}"
    arquivos = escrever(leads, destino, json.loads(p["formatos"]),
                        json.loads(p["blocos"] or "null"))

    # Só AGORA as empresas entram no registro: fatia que falha não marca ninguém.
    entregues.registrar(leads, f"{pid}-{n}", p["filtro"] or "")

    fila.concluir_fatia(pid, n, leads=len(leads), requisicoes=req, cache_hits=hits,
                        custo=custo, apify_erro=apify_erro,
                        arquivos={k: str(v) for k, v in arquivos.items()})
    print(f"[{pid}/{n}] {len(leads)} leads · {req} req · {hits} cache · "
          f"US$ {custo if custo is not None else '?'} · "
          f"{time.time()-t0:.0f}s" + (f" · APIFY: {apify_erro}" if apify_erro else ""),
          flush=True)


def main() -> int:
    trava = _trava()
    fila = Fila(config.DADOS / "jobs.sqlite")
    orfas = fila.retomar_orfas()
    if orfas:
        print(f"retomando {orfas} fatia(s) interrompida(s)", flush=True)
    print("worker no ar", flush=True)

    api = None
    while True:
        try:
            if api is None:
                api = EmpresAqui()
                fila.marcar("pausado_por", "")
        except TokenInvalido as e:
            print(f"sem token utilizável: {e} — esperando {PAUSA_TOKEN}s", flush=True)
            fila.marcar("pausado_por", "token_ausente")
            time.sleep(PAUSA_TOKEN)
            continue

        fatia = fila.proxima_fatia()
        if fatia is None:
            fila.marcar("batida", datetime.now(timezone.utc).isoformat(timespec="seconds"))
            time.sleep(INTERVALO_OCIOSO)
            continue
        try:
            processar(fila, fatia, api)
        except Exception as e:
            fila.concluir_fatia(fatia["pedido_id"], fatia["n"], erro=str(e)[:300])
            print(f"[{fatia['pedido_id']}/{fatia['n']}] ERRO: {e}", flush=True)
        fila.marcar("batida", datetime.now(timezone.utc).isoformat(timespec="seconds"))


if __name__ == "__main__":
    raise SystemExit(main())
