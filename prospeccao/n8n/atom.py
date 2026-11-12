"""
Cliente mínimo da API do n8n, preso na instância da Atom.

O `assert` do host não é paranoia: as ferramentas MCP desta sessão apontam
para a soultextil, e eu já criei uma pasta na instância errada uma vez.
"""
import json, os, urllib.request, urllib.error

JWT = os.environ.get("N8N_JWT", "").strip()
if not JWT:
    raise SystemExit("falta N8N_JWT no ambiente")
HOST = "atomtecnologia.app.n8n.cloud"
BASE = f"https://{HOST}/api/v1"
PROJETO = "U7PD2iEcNVV1GxIs"          # Missner

assert HOST.startswith("atomtecnologia"), "instância errada"


def api(caminho, metodo="GET", corpo=None):
    url = BASE + caminho
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo, headers={
        "X-N8N-API-KEY": JWT, "Content-Type": "application/json",
        "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            t = r.read().decode("utf-8", "replace")
            return json.loads(t) if t.strip() else {}
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode("utf-8", "replace")[:600]
        raise SystemExit(f"{metodo} {caminho} -> {e.code}\n{detalhe}")


def tabela(nome):
    for t in api("/data-tables?limit=200").get("data", []):
        if t["name"] == nome and t["projectId"] == PROJETO:
            return t
    return None


def workflow(nome):
    for w in api("/workflows?limit=250").get("data", []):
        if w["name"] == nome:
            return w
    return None
