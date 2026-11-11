"""
API do Agente de Prospecção Misner.

Assíncrona por desenho: a borda da Cloudflare corta a resposta em 100 s, e
mesmo uma fatia de 100 leva ~2 min. Nenhum endpoint espera o trabalho.

Autenticação por Bearer. O hostname do túnel é público — o túnel protege as
portas da VM, não a aplicação. Em produção, Cloudflare Access na frente.
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cnpj import buscar as mod_buscar, config
from servico.fila import Fila

TOKEN = os.environ.get("API_TOKEN", "")
FILA = Fila(config.DADOS / "jobs.sqlite")
app = FastAPI(title="Misner · Prospecção", version="1.0")

# Uma conexão DuckDB NÃO é thread-safe. Abrir e fechar a cada chamada perde o
# pool de buffers; o certo é conexão longeva com cursor() por thread.
_BASE = {"con": None, "meta": {}}
_TRAVA = threading.Lock()


def _meta() -> dict:
    p = config.DADOS / "base.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _base():
    with _TRAVA:
        if _BASE["con"] is None:
            _BASE["meta"] = _meta()
            _BASE["con"] = mod_buscar._conectar()
    return _BASE["con"]


def auth(authorization: str = Header(default="")):
    if not TOKEN:
        raise HTTPException(500, "API_TOKEN não configurado")
    if authorization.removeprefix("Bearer ").strip() != TOKEN:
        raise HTTPException(401, "não autenticado")


class Filtro(BaseModel):
    ufs: list[str] | None = None
    cnaes: list[str] | None = Field(default=None, description="máximo 2")
    municipios: list[str] | None = None
    porte: list[str] | None = None
    situacao: str = "ativa"
    apenas_matriz: bool = True
    com_contato: bool = False
    capital_min: float | None = None
    excluir_entregues: bool = True

    def kw(self) -> dict:
        return dict(uf=self.ufs, cnae=self.cnaes, municipio=self.municipios,
                    porte=self.porte, situacao=self.situacao,
                    apenas_matriz=self.apenas_matriz, com_contato=self.com_contato,
                    capital_min=self.capital_min,
                    excluir_entregues=self.excluir_entregues)


class Pedido(BaseModel):
    filtro: Filtro | None = None
    cnpjs: list[str] | None = None
    total: int = 100
    tamanho_fatia: int = 100
    formatos: list[str] = ["xlsx"]
    blocos: list[str] | None = None
    com_apify: bool = True
    teto_usd: float = 2.0


@app.get("/v1/saude")
def saude():
    """Vivo e pronto são coisas diferentes: a base leva segundos para abrir."""
    pronto, erro = True, None
    try:
        _base().execute("SELECT 1").fetchone()
    except Exception as e:
        pronto, erro = False, str(e)[:120]
    return {"ok": True, "pronto": pronto, "erro": erro,
            "base": _BASE["meta"] or _meta(), "fila": FILA.estado()}


@app.get("/v1/cnaes", dependencies=[Depends(auth)])
def cnaes(busca: str | None = None, prefixo: str | None = None, limite: int = 40):
    """Sem isto, quem chama precisa adivinhar que tecelagem é 1322300."""
    r = mod_buscar.cnaes_disponiveis(prefixo=prefixo, busca=busca)
    return {"total": len(r), "cnaes": [{"codigo": c, "descricao": d}
                                       for c, d in r[:limite]]}


@app.post("/v1/contar", dependencies=[Depends(auth)])
def contar(f: Filtro):
    try:
        return {"total": mod_buscar.contar(**f.kw())}
    except mod_buscar.CnaesDemais as e:
        raise HTTPException(422, str(e))


@app.post("/v1/buscar", dependencies=[Depends(auth)])
def buscar_(f: Filtro, limite: int = 100, ordenar: str = "contato"):
    # Limite obrigatório: um filtro largo sem teto materializa milhões de
    # dicts em 4 GB de RAM e derruba a API.
    if not 1 <= limite <= 1000:
        raise HTTPException(413, "limite entre 1 e 1000")
    try:
        linhas = mod_buscar.buscar(limite=limite, ordenar=ordenar, **f.kw())
    except mod_buscar.CnaesDemais as e:
        raise HTTPException(422, str(e))
    return {"total": len(linhas), "empresas": linhas}


@app.post("/v1/pedidos", status_code=202, dependencies=[Depends(auth)])
def criar_pedido(p: Pedido, idempotency_key: str | None = Header(default=None)):
    if p.cnpjs:
        lista, filtro = p.cnpjs, "planilha"
    elif p.filtro:
        try:
            linhas = mod_buscar.buscar(limite=p.total, ordenar="contato", **p.filtro.kw())
        except mod_buscar.CnaesDemais as e:
            raise HTTPException(422, str(e))
        lista = [l["cnpj"] for l in linhas]
        filtro = json.dumps(p.filtro.model_dump(), ensure_ascii=False)
    else:
        raise HTTPException(422, "informe filtro ou cnpjs")
    if not lista:
        raise HTTPException(422, "o filtro não devolveu nenhuma empresa")

    r = FILA.criar(lista, filtro=filtro, formatos=p.formatos, blocos=p.blocos,
                   com_apify=p.com_apify, teto_usd=p.teto_usd,
                   tamanho_fatia=p.tamanho_fatia, chave_idem=idempotency_key,
                   base_competencia=(_BASE["meta"] or _meta()).get("competencia"))
    if r.get("repetido"):
        raise HTTPException(409, f"pedido já existe: {r['id']}")
    return r


@app.get("/v1/pedidos/{pid}", dependencies=[Depends(auth)])
def ver_pedido(pid: str):
    p = FILA.pedido(pid)
    if not p:
        raise HTTPException(404, "pedido não encontrado")
    return p


@app.post("/v1/pedidos/{pid}/cancelar", status_code=202, dependencies=[Depends(auth)])
def cancelar(pid: str):
    if not FILA.pedido(pid):
        raise HTTPException(404, "pedido não encontrado")
    return {"canceladas": FILA.cancelar(pid)}


@app.get("/v1/pedidos/{pid}/fatias/{n}/arquivo", dependencies=[Depends(auth)])
def arquivo(pid: str, n: int, formato: str = "xlsx"):
    p = FILA.pedido(pid)
    if not p:
        raise HTTPException(404, "pedido não encontrado")
    fatia = next((f for f in p["fatias"] if f["n"] == n), None)
    if not fatia:
        raise HTTPException(404, "fatia não encontrada")
    if fatia["status"] != "pronto":
        raise HTTPException(409, f"fatia ainda {fatia['status']}")
    caminho = fatia["arquivos"].get(formato)
    if not caminho or not Path(caminho).exists():
        raise HTTPException(404, f"formato {formato} não gerado nesta fatia")
    return FileResponse(caminho, filename=f"{pid}-fatia{n}.{formato}")
