from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.deps import CurrentUser, current_user, tenant_conn
from app.schemas import ConsultaIn, ConsultaOut, LeadOut

router = APIRouter(prefix="/v1/consultas", tags=["consultas"])


@router.post("", status_code=status.HTTP_202_ACCEPTED, response_model=ConsultaOut)
def criar_consulta(
    body: ConsultaIn,
    response: Response,
    user: CurrentUser = Depends(current_user),
    conn: Connection = Depends(tenant_conn),
) -> ConsultaOut:
    """Reserve quota under a row lock, then enqueue the consulta.

    Quota is counted by DELIVERED leads (debited later, at the pipeline
    callback). To stop simultaneous dispatches from both grabbing the whole
    allowance, available = contratado - consumido - reservado-em-voo, and the
    subscription row is taken ``FOR UPDATE`` so concurrent calls serialize.
    """
    sub = conn.execute(
        text(
            """
            SELECT id, leads_contratados_mes, leads_consumidos_mes
            FROM assinaturas
            WHERE status = 'ativa'
              AND current_date BETWEEN ciclo_inicio AND ciclo_fim
            ORDER BY ciclo_inicio DESC
            LIMIT 1
            FOR UPDATE
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
            "tenant_id": user.tenant_id,
            "user_id": user.user_id,
            "relatorio_id": str(body.relatorio_id) if body.relatorio_id else None,
            "tipo": body.tipo,
            "produto_descricao": body.produto_descricao,
            "codigo_fiscal": body.codigo_fiscal,
            "paises": body.paises,
            "perfil_comprador": body.perfil_comprador,
            "plano": body.plano,
            "leads_solicitados": leads_solicitados,
        },
    ).scalar_one()

    conn.execute(
        text(
            "INSERT INTO pipeline_runs (consulta_id, tenant_id, status) "
            "VALUES (:cid, :tid, 'fila')"
        ),
        {"cid": consulta_id, "tid": user.tenant_id},
    )

    # Cloud Tasks enqueue happens here in Bloco 6 (mocked in the sprint).
    response.headers["Location"] = f"/v1/consultas/{consulta_id}"
    return ConsultaOut(
        id=consulta_id,
        status="fila",
        leads_solicitados=leads_solicitados,
        leads_entregues=0,
        plano=body.plano,
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
def obter_consulta(
    consulta_id: UUID, conn: Connection = Depends(tenant_conn)
) -> ConsultaOut:
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
    exists = conn.execute(
        text("SELECT 1 FROM consultas WHERE id = :id"), {"id": str(consulta_id)}
    ).first()
    if exists is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "consulta nao encontrada")
    rows = conn.execute(
        text(
            """
            SELECT id, empresa_nome, pais, cidade, tipo_negocio, telefone,
                   email, whatsapp, instagram, score
            FROM leads WHERE consulta_id = :cid
            ORDER BY criado_em
            LIMIT :limit OFFSET :offset
            """
        ),
        {"cid": str(consulta_id), "limit": limit, "offset": offset},
    ).mappings().all()
    return [LeadOut(**r) for r in rows]
