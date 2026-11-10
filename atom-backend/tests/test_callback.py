"""Internal HMAC callback (Bloco 6): the path n8n/worker uses to push leads."""
import hashlib
import hmac
import json

from sqlalchemy import text

from app.config import settings
from tests.conftest import admin, insert_consulta


def _sign(body: bytes) -> str:
    return hmac.new(settings.callback_hmac_secret.encode(), body, hashlib.sha256).hexdigest()


def _with_run(tenant_id: str) -> str:
    cid = insert_consulta(tenant_id)
    with admin.begin() as c:
        c.execute(
            text("INSERT INTO pipeline_runs (consulta_id, tenant_id, status) VALUES (:c, :t, 'fila')"),
            {"c": cid, "t": tenant_id},
        )
    return cid


def test_callback_rejects_bad_signature(client, tenant_factory):
    t = tenant_factory("CbBad")
    cid = _with_run(t["tenant_id"])
    body = json.dumps({"leads": []}).encode()
    r = client.post(
        f"/v1/internal/consultas/{cid}/callback", content=body, headers={"x-signature": "nope"}
    )
    assert r.status_code == 401


def test_callback_persists_with_valid_signature(client, tenant_factory):
    t = tenant_factory("CbOk")
    cid = _with_run(t["tenant_id"])
    body = json.dumps(
        {
            "leads": [
                {"empresa": "ACME SA", "pais": "Paraguai", "telefone": "+595-1", "email": "a@b.com"}
            ],
            "custo_total_usd": 1.2,
            "parcial": False,
        }
    ).encode()
    r = client.post(
        f"/v1/internal/consultas/{cid}/callback", content=body, headers={"x-signature": _sign(body)}
    )
    assert r.status_code == 200
    assert r.json()["leads_persistidos"] == 1

    with admin.begin() as c:
        n = c.execute(
            text("SELECT leads_entregues FROM consultas WHERE id = :id"), {"id": cid}
        ).scalar_one()
    assert n == 1
