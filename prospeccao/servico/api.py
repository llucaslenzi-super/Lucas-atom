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
from pydantic import BaseModel, Field, field_validator

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cnpj import buscar as mod_buscar, config
from cnpj.empresaqui import normalizar
from servico.fila import Fila, TAMANHO_LISTA

TOKEN = os.environ.get("API_TOKEN", "")

# Teto de empresas por pedido. Não é limite técnico: a 1 req/s, 10.000
# empresas são 2h47 de trabalho, e a pessoa tem de pedir isso de propósito,
# em pedidos separados, em vez de por acidente num campo de formulário.
TETO_TOTAL = 10_000
FORMATOS = {"csv", "xlsx", "pdf"}
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
    # Quem recebe. O registro de "nunca volta" e por cliente desde 12/11: a
    # mesma empresa pode ir para dois clientes, nao duas vezes para o mesmo.
    cliente: str = Field(min_length=1, max_length=60)
    ufs: list[str] | None = None
    cnaes: list[str] | None = Field(default=None, description="máximo 2")
    municipios: list[str] | None = None
    porte: list[str] | None = None
    situacao: str = "ativa"
    apenas_matriz: bool = True
    excluir_entregues: bool = True

    def kw(self) -> dict:
        return dict(cliente=self.cliente,
                    uf=self.ufs, cnae=self.cnaes, municipio=self.municipios,
                    porte=self.porte, situacao=self.situacao,
                    apenas_matriz=self.apenas_matriz,
                    excluir_entregues=self.excluir_entregues)


class Pedido(BaseModel):
    filtro: Filtro | None = None
    cnpjs: list[str] | None = None
    # Toda lista entregue tem no máximo 100 empresas, e isso não se configura:
    # `tamanho_fatia` saiu do modelo de propósito. 1000 empresas são 10 listas.
    total: int = Field(default=100, ge=1, le=TETO_TOTAL)
    formatos: list[str] = ["xlsx", "csv"]
    blocos: list[str] | None = None
    com_apify: bool = True
    teto_usd: float = Field(default=2.0, ge=0, le=100)
    # Entrega a repetida MARCADA em vez de esconde-la. Entregar 50 de 100
    # caladamente parece erro; entregar 100 com 50 marcadas mostra que a
    # pesquisa rodou e que o filtro esta esgotando.
    marcar_repetidas: bool = True
    # Obrigatorio quando o pedido vem por lista de CNPJs, porque ai nao ha
    # Filtro para carregar o cliente.
    cliente: str | None = None

    @field_validator("formatos")
    @classmethod
    def _formatos_validos(cls, v):
        # Antes isto só estourava dentro do worker, derrubando a fatia para
        # erro depois de a API já ter respondido 202 ao cliente.
        ruins = [f for f in v if f not in FORMATOS]
        if ruins:
            raise ValueError(f"formato desconhecido: {ruins}. "
                             f"Use {sorted(FORMATOS)}")
        return v or ["xlsx", "csv"]

    @field_validator("cnpjs")
    @classmethod
    def _cnpjs_validos(cls, v):
        # Normalizar AQUI, não lá dentro: se a limpeza acontece depois, o
        # total_pedido gravado na fila mente sobre o que será processado.
        if v is None:
            return v
        limpos, vistos = [], set()
        for bruto in v:
            n = normalizar(bruto)
            if n and n[0] not in vistos:
                vistos.add(n[0])
                limpos.append(n[0])
        if not limpos:
            raise ValueError("nenhum CNPJ válido na lista")
        if len(limpos) > TETO_TOTAL:
            raise ValueError(f"máximo de {TETO_TOTAL} CNPJs por pedido")
        return limpos


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
    """
    Devolve as três contas que a tela precisa mostrar antes de gastar:
    quantas batem com o filtro, quantas são novas para este cliente, e
    quantas ele já recebeu antes.

    Uma conta só não serve: "944 disponíveis" sem dizer que 340 já foram
    entregues faz a pessoa achar que o sistema está escondendo empresa.
    """
    try:
        kw = f.kw()
        novas = mod_buscar.contar(**kw)
        total = mod_buscar.contar(**{**kw, "excluir_entregues": False})
    except mod_buscar.CnaesDemais as e:
        raise HTTPException(422, str(e))
    return {"total": total, "novas": novas, "repetidas": total - novas,
            "cliente": f.cliente}


@app.post("/v1/buscar", dependencies=[Depends(auth)])
def buscar_(f: Filtro, limite: int = 100, ordenar: str = "cnpj"):
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
    cliente = p.cliente or (p.filtro.cliente if p.filtro else None)
    if not cliente:
        raise HTTPException(422, "informe o cliente")

    if p.cnpjs:
        lista, filtro = p.cnpjs, "planilha"
    elif p.filtro:
        try:
            # marcar_entregues traz a repetida na lista, rotulada. Sem ele a
            # repetida sai fora e o cliente recebe menos do que pediu sem
            # entender por quê.
            linhas = mod_buscar.buscar(limite=p.total, ordenar="cnpj",
                                       marcar_entregues=p.marcar_repetidas,
                                       **p.filtro.kw())
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
                   chave_idem=idempotency_key, cliente=cliente,
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
