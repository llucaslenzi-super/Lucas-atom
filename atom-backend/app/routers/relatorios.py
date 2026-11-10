"""Bloco 3: upload do relatorio PEIEX, leitura (2 modelos) e sugestao."""
import io

from fastapi import APIRouter, Depends, File, UploadFile
from pypdf import PdfReader
from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.deps import CurrentUser, current_user, tenant_conn
from app.providers import get_report_parser
from app.storage import save_bytes

router = APIRouter(prefix="/v1/relatorios", tags=["relatorios"])


def _extract_text(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception:
        return ""


@router.post("", status_code=201)
def upload_relatorio(
    file: UploadFile = File(...),
    user: CurrentUser = Depends(current_user),
    conn: Connection = Depends(tenant_conn),
) -> dict:
    data = file.file.read()
    parsed = get_report_parser().parse(_extract_text(data))
    gcs_path = save_bytes(f"{user.tenant_id}/relatorios/{file.filename}", data)

    relatorio_id = conn.execute(
        text(
            """
            INSERT INTO relatorios
                (tenant_id, arquivo_gcs, tipo, produto_descricao, codigo_fiscal,
                 mercado_sugerido, perfil_comprador)
            VALUES (:t, :gcs, :tipo, :desc, :cod, :merc, :perfil)
            RETURNING id
            """
        ),
        {
            "t": user.tenant_id, "gcs": gcs_path, "tipo": parsed.tipo,
            "desc": parsed.produto_descricao, "cod": parsed.codigo_fiscal,
            "merc": parsed.mercado_sugerido, "perfil": parsed.perfil_comprador,
        },
    ).scalar_one()

    return {
        "id": str(relatorio_id),
        "tipo": parsed.tipo,
        "codigo_fiscal": parsed.codigo_fiscal,
        "produto_descricao": parsed.produto_descricao,
        "mercado_sugerido": parsed.mercado_sugerido,
        "perfil_comprador": parsed.perfil_comprador,
    }
