"""Quota (ARQUITETURA.md §7): capped by the monthly allowance, enforced under a
row lock so simultaneous dispatches cannot overshoot it.
"""
import threading

from sqlalchemy import text

from tests.conftest import admin


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _post(client, token: str, pedido: int):
    return client.post(
        "/v1/consultas",
        headers=_auth(token),
        json={"tipo": "produto", "leads_solicitados": pedido},
    )


def test_quota_clamps_and_exhausts(client, tenant_factory):
    t = tenant_factory("Cota", leads=350)

    r1 = _post(client, t["token"], 300)
    assert r1.status_code == 202
    assert r1.json()["leads_solicitados"] == 300

    # Only 50 left -> request of 100 is clamped to 50.
    r2 = _post(client, t["token"], 100)
    assert r2.status_code == 202
    assert r2.json()["leads_solicitados"] == 50

    # Nothing left -> 409.
    r3 = _post(client, t["token"], 10)
    assert r3.status_code == 409


def test_no_subscription_returns_402(client, tenant_factory):
    t = tenant_factory("SemPlano", leads=350)
    with admin.begin() as c:
        c.execute(
            text("UPDATE assinaturas SET status = 'cancelada' WHERE tenant_id = :t"),
            {"t": t["tenant_id"]},
        )
    assert _post(client, t["token"], 10).status_code == 402


def test_concurrent_dispatch_does_not_overshoot(client, tenant_factory):
    t = tenant_factory("Corrida", leads=350)
    results: list = []

    def worker():
        results.append(_post(client, t["token"], 300))

    threads = [threading.Thread(target=worker) for _ in range(2)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()

    granted = sum(r.json()["leads_solicitados"] for r in results if r.status_code == 202)
    assert granted <= 350, f"quota overshot: granted {granted}"

    with admin.begin() as c:
        reserved = c.execute(
            text(
                "SELECT COALESCE(SUM(leads_solicitados), 0) FROM consultas "
                "WHERE tenant_id = :t"
            ),
            {"t": t["tenant_id"]},
        ).scalar_one()
    assert reserved <= 350
