"""
Ponte entre a VM e o n8n. É o único lugar do sistema que fala com o n8n.

A VM não escuta porta nenhuma: nem túnel, nem domínio, nem certificado. Ela
só faz chamadas de SAÍDA. Então a ponte faz os dois sentidos por fora:

    busca trabalho   GET  /api/v1/data-tables/<pedidos>/rows   (API REST)
    entrega a lista  POST /webhook/prospeccao-guardar           (webhook)

Ler a fila pela API REST e não por webhook é de propósito: chamada de API não
conta como execução no n8n. Com um webhook de polling a cada minuto seriam
1.440 execuções por dia só para descobrir que não há nada a fazer.
"""
from __future__ import annotations

import base64
import fcntl
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cnpj import config, entregues, exportar
from servico.fila import Fila

INTERVALO = int(os.environ.get("PONTE_INTERVALO", "60"))

N8N = os.environ.get("N8N_BASE", "https://atomtecnologia.app.n8n.cloud").rstrip("/")
JWT = (os.environ.get("N8N_JWT") or "").strip()
SEGREDO = (os.environ.get("PONTE_TOKEN") or "").strip()

TABELA_PEDIDOS = os.environ.get("N8N_TABELA_PEDIDOS", "7xKe4gdNqDX4SKEC")
WEBHOOK_GUARDAR = f"{N8N}/webhook/prospeccao-guardar"

# Tipos MIME por formato, para o navegador do cliente saber o que recebeu.
TIPOS = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


class SemCredencial(RuntimeError):
    pass


# Erros que são do pedido, não do caminho. Repetir dá o mesmo resultado, então
# o pedido é marcado como erro e o cliente sabe o motivo — em vez de ficar em
# laço no log e esperando uma lista que nunca vem.
PERMANENTES = (ValueError, TypeError, KeyError, base64.binascii.Error)

# Usado só pela auditoria de sabotagem, para trocar PERMANENTES por algo
# que nunca casa e provar que sem ele o pedido fica em laço.
class _NadaDisso(Exception):
    pass


def _log(msg: str) -> None:
    print(f"[ponte] {msg}", flush=True)


# ────────────────────────────────────────────────── HTTP

def _api(caminho: str, metodo="GET", corpo=None, params=None, timeout=60):
    """Chamada à API REST do n8n. Levanta SemCredencial sem o JWT."""
    if not JWT:
        raise SemCredencial("N8N_JWT não está no ambiente")
    url = f"{N8N}/api/v1/{caminho.lstrip('/')}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(
        url, data=dados, method=metodo,
        headers={"X-N8N-API-KEY": JWT, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        bruto = r.read().decode("utf-8", "replace")
    return json.loads(bruto) if bruto.strip() else {}


def _linhas(resposta) -> list[dict]:
    """
    A API devolve as linhas em formatos diferentes conforme o endpoint:
    lista crua, {"data": [...]} ou {"data": {"data": [...]}}. Normaliza, em
    vez de escolher um e quebrar quando vier o outro.
    """
    d = resposta
    for _ in range(2):
        if isinstance(d, dict):
            d = d.get("data", [])
    return d if isinstance(d, list) else []


# ────────────────────────────────────────────────── entrada

def pedidos_pendentes() -> list[dict]:
    filtro = json.dumps({"type": "and", "filters": [
        {"columnName": "status", "condition": "eq", "value": "pendente"}]})
    return _linhas(_api(f"data-tables/{TABELA_PEDIDOS}/rows",
                        params={"filter": filtro, "limit": 50}))


def marcar_pedido(linha_id, **campos) -> None:
    filtro = json.dumps({"type": "and", "filters": [
        {"columnName": "id", "condition": "eq", "value": linha_id}]})
    _api(f"data-tables/{TABELA_PEDIDOS}/rows/update", metodo="PATCH",
         corpo={"filter": json.loads(filtro), "data": campos})


def criar_local(fila: Fila, linha: dict) -> dict:
    """
    Transforma uma linha da fila do n8n num pedido na fila da VM.

    `chave_idem` é o id da linha: se a ponte morrer entre criar o pedido e
    marcar a linha como em curso, a próxima volta encontra a mesma linha
    pendente e NÃO cria um segundo pedido — a fila já tem UNIQUE nessa chave.
    """
    cliente = (linha.get("cliente") or "").strip() or entregues.CLIENTE_ANTIGO

    # Enriquecimento é DESLIGADO por omissão, e isso é decisão de segurança,
    # não de desenho: o padrão da fila é ligado, então um pedido que não diga
    # nada gastaria dólar de Apify sem ninguém ter pedido. Quem quer gastar
    # diz que quer, e diz quanto.
    com_apify = str(linha.get("com_apify") or "").strip().lower() in (
        "1", "true", "sim", "s", "yes")
    try:
        teto_usd = float(linha.get("teto_usd") or 0) or 2.0
    except (TypeError, ValueError):
        teto_usd = 2.0
    formatos = tuple(
        f.strip() for f in (linha.get("formatos") or "xlsx,csv").split(",")
        if f.strip() in TIPOS) or ("xlsx", "csv")
    total = int(linha.get("total") or 100)

    if linha.get("planilha_b64"):
        # Caminho da planilha: aqui o CNAE é resultado, não critério, então
        # não existe teto de dois CNAEs.
        nome = linha.get("planilha_nome") or "lista.csv"
        tmp = Path(config.DADOS) / "tmp" / f"entrada-{linha['id']}-{nome}"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        try:
            tmp.write_bytes(base64.b64decode(linha["planilha_b64"]))
            cnpjs, info = exportar.ler_cnpjs(tmp)
        finally:
            tmp.unlink(missing_ok=True)
        if not cnpjs:
            raise ValueError(
                f"nenhum CNPJ válido na planilha "
                f"({info.get('invalidos_descartados', 0)} descartados pelo dígito)")
        return fila.criar(cnpjs, filtro="planilha", formatos=formatos,
                          cliente=cliente, com_apify=com_apify,
                          teto_usd=teto_usd, chave_idem=str(linha["id"]))

    from cnpj import buscar as mod_buscar
    # normalizar_filtro: o n8n guarda o filtro com os nomes da API, no plural.
    filtro = mod_buscar.normalizar_filtro(json.loads(linha.get("filtro") or "{}"))
    filtro["cliente"] = cliente
    linhas = mod_buscar.buscar(limite=total, ordenar="cnpj",
                               marcar_entregues=True, **filtro)
    if not linhas:
        raise ValueError("o filtro não devolveu nenhuma empresa")
    return fila.criar([l["cnpj"] for l in linhas],
                      filtro=json.dumps(filtro, ensure_ascii=False),
                      formatos=formatos, cliente=cliente,
                      com_apify=com_apify, teto_usd=teto_usd,
                      chave_idem=str(linha["id"]))


def puxar(fila: Fila) -> int:
    criados = 0
    for linha in pedidos_pendentes():
        try:
            r = criar_local(fila, linha)
        except PERMANENTES as e:
            # Falha no PEDIDO, não no caminho: tentar de novo dá o mesmo erro.
            # Antes, qualquer exceção caía no retry e o pedido ficava em laço
            # de minuto em minuto, para sempre — foi o que aconteceu com o
            # `buscar() got an unexpected keyword argument 'ufs'`: dez
            # tentativas idênticas no log e nada no n8n dizendo o motivo.
            _log(f"pedido {linha['id']} recusado: {type(e).__name__}: {e}")
            marcar_pedido(linha["id"], status="erro",
                          motivo=f"{type(e).__name__}: {e}"[:300])
            continue
        except Exception as e:
            # Transitório: rede, n8n fora do ar, disco. Tenta na volta seguinte.
            _log(f"pedido {linha['id']} falhou (vai tentar de novo): "
                 f"{type(e).__name__}: {e}")
            continue
        marcar_pedido(linha["id"], status="em_curso", pedido_id=r["id"])
        criados += 1
        _log(f"pedido {linha['id']} → {r['id']} · {r['fatias']} lista(s) "
             f"de {r['total']} empresas")
    return criados


# ────────────────────────────────────────────────── saída

def guardar(pedido_id: str, n: int, formato: str, caminho: Path,
            empresas: int) -> None:
    if not SEGREDO:
        raise SemCredencial("PONTE_TOKEN não está no ambiente")
    corpo = {
        "token": SEGREDO, "pedido_id": pedido_id, "fatia": n,
        "formato": formato, "empresas": empresas,
        "filename": f"prospeccao-{pedido_id}-{n:03d}.{formato}",
        "ct": TIPOS.get(formato, "application/octet-stream"),
        "b64": base64.b64encode(caminho.read_bytes()).decode(),
    }
    req = urllib.request.Request(
        WEBHOOK_GUARDAR, data=json.dumps(corpo).encode(), method="POST",
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        resposta = json.loads(r.read().decode("utf-8", "replace") or "{}")
    if not resposta.get("ok"):
        raise RuntimeError(f"n8n recusou: {str(resposta)[:200]}")


def entregar(fila: Fila) -> int:
    """
    Manda as fatias prontas e ainda não entregues, e SÓ ENTÃO registra as
    empresas como entregues.

    A ordem é o ponto. Registrar na geração do arquivo, como era antes, marca
    a empresa para sempre mesmo quando a entrega falha — e aí o cliente nunca
    recebe aquela empresa, nem naquela lista nem em nenhuma futura. É o único
    estrago irreversível deste sistema.
    """
    pendentes = fila.db.execute(
        "SELECT f.pedido_id, f.n, f.arquivos, f.leads, p.cliente, p.filtro "
        "FROM fatias f JOIN pedidos p ON p.id = f.pedido_id "
        "WHERE f.status='pronto' AND f.entregue_em IS NULL "
        "ORDER BY f.pedido_id, f.n").fetchall()

    entregues_agora = 0
    for f in pendentes:
        arquivos = json.loads(f["arquivos"] or "{}")
        if not arquivos:
            continue
        pid, n = f["pedido_id"], f["n"]
        try:
            for formato, caminho in sorted(arquivos.items()):
                p = Path(caminho)
                if not p.exists():
                    raise FileNotFoundError(caminho)
                guardar(pid, n, formato, p, f["leads"] or 0)
        except Exception as e:
            _log(f"{pid}/{n} não entregue: {type(e).__name__}: {e}")
            continue

        # Chegou ao n8n. Agora, e não antes, as empresas entram no registro.
        cliente = f["cliente"] or entregues.CLIENTE_ANTIGO
        cnpjs = json.loads(fila.db.execute(
            "SELECT cnpjs FROM fatias WHERE pedido_id=? AND n=?",
            [pid, n]).fetchone()["cnpjs"])
        novas = entregues.registrar(
            [{"cnpj": c, "cnpj_base": c[:8]} for c in cnpjs],
            f"{pid}-{n}", f["filtro"] or "", cliente=cliente)
        fila.db.execute(
            "UPDATE fatias SET entregue_em=? WHERE pedido_id=? AND n=?",
            [datetime.now(timezone.utc).isoformat(timespec="seconds"), pid, n])
        fila.db.commit()
        entregues_agora += 1
        _log(f"{pid}/{n} entregue · {len(arquivos)} formato(s) · "
             f"{novas} empresa(s) nova(s) no registro de {cliente}")

    return entregues_agora


# ────────────────────────────────────────────────── laço

def _trava():
    """Uma ponte só. Duas entregariam a mesma fatia duas vezes."""
    alvo = config.DADOS / "ponte.lock"
    alvo.parent.mkdir(parents=True, exist_ok=True)
    fh = open(alvo, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("outra ponte já está rodando — saindo", flush=True)
        raise SystemExit(1)
    fh.write(str(os.getpid())); fh.flush()
    return fh


def main() -> int:
    trava = _trava()
    fila = Fila(config.DADOS / "jobs.sqlite")
    _log(f"n8n em {N8N} · ciclo de {INTERVALO}s")

    while True:
        try:
            puxar(fila)
            entregar(fila)
        except SemCredencial as e:
            # Sem credencial não há o que tentar; dormir e avisar é melhor que
            # sair em laço quente e esconder o motivo no reinício do systemd.
            _log(f"{e} — esperando {INTERVALO}s")
        except urllib.error.URLError as e:
            _log(f"n8n inalcançável: {e.reason}")
        except Exception as e:
            _log(f"ciclo falhou: {type(e).__name__}: {e}")
        time.sleep(INTERVALO)
    return 0


if __name__ == "__main__":
    sys.exit(main())
