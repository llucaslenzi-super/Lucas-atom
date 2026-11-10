import io
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.db import tenant_tx
from app.deps import CurrentUser, current_user, tenant_conn
from app.export import build_csv, build_pdf, build_xlsx
from app.pipeline.worker import run_consulta
from app.schemas import ConsultaIn, ConsultaOut, LeadOut
from app.storage import save_bytes

router = APIRouter(prefix="/v1/consultas", tags=["consultas"])

_MEDIA = {
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
    "pdf": "application/pdf",
}


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ConsultaOut)
def criar_consulta(
    body: ConsultaIn,
    response: Response,
    background: BackgroundTasks,
    user: CurrentUser = Depends(current_user),
) -> ConsultaOut:
    """Reserve quota under a row lock, enqueue the consulta, then run the pipeline.

    Quota is counted by DELIVERED leads (debited at the callback). ``available``
    discounts in-flight reservations, and the subscription row is taken
    ``FOR UPDATE`` so simultaneous dispatches serialize and cannot overshoot.
    """
    with tenant_tx(user.tenant_id) as conn:
        sub = conn.execute(
            text(
                """
                SELECT id, leads_contratados_mes, leads_consumidos_mes
                FROM assinaturas
                WHERE status = 'ativa' AND current_date BETWEEN ciclo_inicio AND ciclo_fim
                ORDER BY ciclo_inicio DESC LIMIT 1 FOR UPDATE
                """
            )
        ).mappings().first()
        if sub is None:
            raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED, "sem assinatura ativa no ciclo")

        reservado = conn.execute(
            text(
                "SELECT COALESCE(SUM(leads_solicitados), 0) "
                "FROM consultas WHERE status IN ('fila', 'processando')"
            )
        ).scalar_one()
        disponivel = sub["leads_contratados_mes"] - sub["leads_consumidos_mes"] - reservado
        if disponivel <= 0:
            raise HTTPException(status.HTTP_409_CONFLICT, "cota mensal esgotada")

        leads_solicitados = min(body.leads_solicitados, disponivel)
        consulta_id = conn.execute(
            text(
                """
                INSERT INTO consultas
                    (tenant_id, user_id, relatorio_id, tipo, produto_descricao,
                     codigo_fiscal, paises, perfil_comprador, plano, status, leads_solicitados)
                VALUES
                    (:tenant_id, :user_id, :relatorio_id, :tipo, :produto_descricao,
                     :codigo_fiscal, :paises, :perfil_comprador, :plano, 'fila', :leads_solicitados)
                RETURNING id
                """
            ),
            {
                "tenant_id": user.tenant_id, "user_id": user.user_id,
                "relatorio_id": str(body.relatorio_id) if body.relatorio_id else None,
                "tipo": body.tipo, "produto_descricao": body.produto_descricao,
                "codigo_fiscal": body.codigo_fiscal, "paises": body.paises,
                "perfil_comprador": body.perfil_comprador, "plano": body.plano,
                "leads_solicitados": leads_solicitados,
            },
        ).scalar_one()
        conn.execute(
            text("INSERT INTO pipeline_runs (consulta_id, tenant_id, status) VALUES (:c, :t, 'fila')"),
            {"c": consulta_id, "t": user.tenant_id},
        )
    # Committed above. Enqueue the pipeline (Cloud Tasks -> n8n in prod).
    background.add_task(run_consulta, str(consulta_id))
    response.headers["Location"] = f"/v1/consultas/{consulta_id}"
    return ConsultaOut(
        id=consulta_id, status="fila", leads_solicitados=leads_solicitados,
        leads_entregues=0, plano=body.plano,
    )


@router.get("", response_model=list[ConsultaOut])
def listar_consultas(conn: Connection = Depends(tenant_conn)) -> list[ConsultaOut]:
    rows = conn.execute(
        text(
            "SELECT id, status, leads_solicitados, leads_entregues, plano "
            "FROM consultas ORDER BY criado_em DESC"
        )
    ).mappings().all()
    return [ConsultaOut(**r) for r in rows]


@router.get("/{consulta_id}", response_model=ConsultaOut)
def obter_consulta(consulta_id: UUID, conn: Connection = Depends(tenant_conn)) -> ConsultaOut:
    row = conn.execute(
        text(
            "SELECT id, status, leads_solicitados, leads_entregues, plano "
            "FROM consultas WHERE id = :id"
        ),
        {"id": str(consulta_id)},
    ).mappings().first()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "consulta nao encontrada")
    return ConsultaOut(**row)


@router.get("/{consulta_id}/leads", response_model=list[LeadOut])
def listar_leads(
    consulta_id: UUID,
    conn: Connection = Depends(tenant_conn),
    limit: int = Query(50, ge=1, le=350),
    offset: int = Query(0, ge=0),
) -> list[LeadOut]:
    if conn.execute(
        text("SELECT 1 FROM consultas WHERE id = :id"), {"id": str(consulta_id)}
    ).first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "consulta nao encontrada")
    rows = conn.execute(
        text(
            """
            SELECT id, empresa_nome, pais, cidade, tipo_negocio, telefone,
                   email, whatsapp, instagram, score
            FROM leads WHERE consulta_id = :cid ORDER BY score DESC
            LIMIT :limit OFFSET :offset
            """
        ),
        {"cid": str(consulta_id), "limit": limit, "offset": offset},
    ).mappings().all()
    return [LeadOut(**r) for r in rows]


@router.get("/{consulta_id}/export")
def exportar(
    consulta_id: UUID,
    formato: str = Query("xlsx", pattern="^(xlsx|csv|pdf)$"),
    user: CurrentUser = Depends(current_user),
    conn: Connection = Depends(tenant_conn),
) -> StreamingResponse:
    if conn.execute(
        text("SELECT 1 FROM consultas WHERE id = :id"), {"id": str(consulta_id)}
    ).first() is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "consulta nao encontrada")
    rows = conn.execute(
        text(
            """
            SELECT empresa_nome, pais, cidade, tipo_negocio, site, telefone,
                   email, whatsapp, instagram, score
            FROM leads WHERE consulta_id = :cid ORDER BY score DESC
            """
        ),
        {"cid": str(consulta_id)},
    ).mappings().all()
    leads = [dict(r) for r in rows]

    if formato == "csv":
        data = build_csv(leads)
    elif formato == "pdf":
        data = build_pdf(leads, f"Atom - leads da consulta {consulta_id}")
    else:
        data = build_xlsx(leads)

    path = save_bytes(f"{user.tenant_id}/exports/{consulta_id}.{formato}", data)
    conn.execute(
        text(
            "INSERT INTO exports (consulta_id, tenant_id, formato, gcs_path) "
            "VALUES (:c, :t, :f, :p)"
        ),
        {"c": str(consulta_id), "t": user.tenant_id, "f": formato, "p": path},
    )
    return StreamingResponse(
        io.BytesIO(data),
        media_type=_MEDIA[formato],
        headers={"Content-Disposition": f'attachment; filename="leads_{consulta_id}.{formato}"'},
    )
