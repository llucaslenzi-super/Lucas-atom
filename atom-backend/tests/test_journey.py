"""End-to-end journey with mocked providers: dispatch -> pipeline -> leads ->
quota debited -> export in XLSX/CSV/PDF. Proves the whole backend runs locally.
"""
from sqlalchemy import text

from app.config import settings
from tests.conftest import admin


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_full_journey_runs_and_exports(client, tenant_factory):
    t = tenant_factory("Jornada", leads=350)

    r = client.post(
        "/v1/consultas",
        headers=_auth(t["token"]),
        json={
            "tipo": "produto",
            "produto_descricao": "Kit de calcinhas de algodao",
            "codigo_fiscal": "6108.21.00",
            "paises": ["Paraguai"],
            "plano": "padrao",
            "leads_solicitados": 12,
        },
    )
    assert r.status_code == 202
    cid = r.json()["id"]

    # Pipeline ran as a background task; consulta is now pronta with 12 leads.
    got = client.get(f"/v1/consultas/{cid}", headers=_auth(t["token"])).json()
    assert got["status"] == "pronta"
    assert got["leads_entregues"] == 12

    leads = client.get(f"/v1/consultas/{cid}/leads", headers=_auth(t["token"])).json()
    assert len(leads) == 12
    assert all(ld["telefone"] and ld["email"] for ld in leads)  # campos garantidos

    # Quota debited by delivered leads.
    with admin.begin() as c:
        consumido = c.execute(
            text("SELECT leads_consumidos_mes FROM assinaturas WHERE tenant_id = :t"),
            {"t": t["tenant_id"]},
        ).scalar_one()
    assert consumido == 12

    # Stage events recorded.
    with admin.begin() as c:
        etapas = c.execute(
            text(
                "SELECT etapa FROM pipeline_stage_events pse "
                "JOIN pipeline_runs pr ON pr.id = pse.pipeline_run_id "
                "WHERE pr.consulta_id = :c ORDER BY pse.criado_em"
            ),
            {"c": cid},
        ).scalars().all()
    assert etapas == ["descoberta", "enriquecimento", "limpeza"]

    # Export in all three formats.
    xlsx = client.get(f"/v1/consultas/{cid}/export?formato=xlsx", headers=_auth(t["token"]))
    assert xlsx.status_code == 200 and xlsx.content[:2] == b"PK"
    csv = client.get(f"/v1/consultas/{cid}/export?formato=csv", headers=_auth(t["token"]))
    assert csv.status_code == 200 and b"Empresa" in csv.content
    pdf = client.get(f"/v1/consultas/{cid}/export?formato=pdf", headers=_auth(t["token"]))
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_cost_guardrail_marks_parcial(client, tenant_factory, monkeypatch):
    monkeypatch.setattr(settings, "cost_ceiling_usd", 0.0)  # trip on the first stage
    t = tenant_factory("Guard", leads=350)
    r = client.post(
        "/v1/consultas",
        headers=_auth(t["token"]),
        json={"tipo": "produto", "paises": ["EUA"], "leads_solicitados": 20},
    )
    cid = r.json()["id"]
    got = client.get(f"/v1/consultas/{cid}", headers=_auth(t["token"])).json()
    assert got["status"] == "parcial"
    assert got["leads_entregues"] == 0
