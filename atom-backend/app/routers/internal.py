"""Internal callback (Bloco 6): n8n/worker pushes cleaned leads back to the API.

Authenticated by HMAC-SHA256 over the raw body (shared secret). Writes via the
owner engine on the tenant's behalf, reusing the worker's persistence logic.
"""
import hashlib
import hmac
import json

from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import text

from app.config import settings
from app.db import admin_engine
from app.pipeline.worker import apply_callback
from app.providers.base import LeadLimpo

router = APIRouter(prefix="/v1/internal", tags=["internal"])


def _lead_from(d: dict) -> LeadLimpo:
    return LeadLimpo(
        empresa_nome=d.get("empresa_nome") or d.get("empresa") or "",
        pais=d.get("pais"), cidade=d.get("cidade"), tipo_negocio=d.get("tipo_negocio"),
        site=d.get("site"), telefone=d.get("telefone"), email=d.get("email"),
        whatsapp=d.get("whatsapp"), instagram=d.get("instagram"),
        score=float(d.get("score") or 0), racional=d.get("racional") or "",
        fontes=d.get("fontes") or {},
    )


@router.post("/consultas/{consulta_id}/callback")
async def callback(consulta_id: str, request: Request, x_signature: str = Header(default="")):
    body = await request.body()
    expected = hmac.new(
        settings.callback_hmac_secret.encode(), body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected, x_signature):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid signature")

    payload = json.loads(body or b"{}")
    leads = [_lead_from(x) for x in payload.get("leads", [])]

    with admin_engine.begin() as conn:
        row = conn.execute(
            text("SELECT tenant_id, leads_solicitados FROM consultas WHERE id = :id"),
            {"id": consulta_id},
        ).mappings().first()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "consulta nao encontrada")
        run_id = conn.execute(
            text("SELECT id FROM pipeline_runs WHERE consulta_id = :id"), {"id": consulta_id}
        ).scalar_one()
        apply_callback(
            conn, consulta_id, str(row["tenant_id"]), run_id, leads,
            float(payload.get("custo_total_usd", 0.0)), bool(payload.get("parcial", False)),
            row["leads_solicitados"],
        )
    return {"status": "ok", "leads_persistidos": len(leads)}
