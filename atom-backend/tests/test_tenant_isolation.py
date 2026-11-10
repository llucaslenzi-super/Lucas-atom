"""Mandatory acceptance test (ARQUITETURA.md §6): a tenant A JWT never returns
a tenant B row, in any endpoint. Also checks RLS directly at the DB layer.
"""
from sqlalchemy import text

from app.db import tenant_tx
from tests.conftest import insert_consulta


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_api_tenant_a_cannot_see_tenant_b(client, tenant_factory):
    a = tenant_factory("TenantA")
    b = tenant_factory("TenantB")
    consulta_b = insert_consulta(b["tenant_id"])
    consulta_a = insert_consulta(a["tenant_id"])

    # A lists only its own consultas.
    r = client.get("/v1/consultas", headers=_auth(a["token"]))
    assert r.status_code == 200
    ids = {c["id"] for c in r.json()}
    assert consulta_a in ids
    assert consulta_b not in ids

    # A cannot fetch B's consulta by id (looks like it does not exist).
    r = client.get(f"/v1/consultas/{consulta_b}", headers=_auth(a["token"]))
    assert r.status_code == 404

    # A cannot read B's leads either.
    r = client.get(f"/v1/consultas/{consulta_b}/leads", headers=_auth(a["token"]))
    assert r.status_code == 404


def test_rls_enforced_at_db_layer(client, tenant_factory):
    a = tenant_factory("DbA")
    b = tenant_factory("DbB")
    insert_consulta(a["tenant_id"])
    insert_consulta(b["tenant_id"])

    with tenant_tx(a["tenant_id"]) as conn:
        rows = conn.execute(text("SELECT tenant_id FROM consultas")).scalars().all()
    assert rows, "tenant A should see its own rows"
    assert all(str(tid) == a["tenant_id"] for tid in rows)
