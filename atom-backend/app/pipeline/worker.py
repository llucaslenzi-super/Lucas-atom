"""In-process pipeline worker (Bloco 6).

Runs the cascade E1 -> E2 -> E5 (padrao path) via the selected providers,
records a pipeline_stage_events row per stage, enforces the per-consulta cost
guardrail, then persists leads and debits quota by DELIVERED leads.

In the sprint this runs as a FastAPI BackgroundTask. In production the orchestration
moves to n8n / Cloud Tasks, which calls the same persistence via the HMAC-signed
callback (app/routers/internal.py). The persistence logic is shared: apply_callback.
"""
import json

from sqlalchemy import text
from sqlalchemy.engine import Connection

from app.config import settings
from app.db import admin_engine
from app.providers import get_providers
from app.providers.base import LeadLimpo


def _stage(conn: Connection, run_id, tenant_id, etapa, status, entrada, saida, custo, detalhe=None):
    conn.execute(
        text(
            """
            INSERT INTO pipeline_stage_events
                (pipeline_run_id, tenant_id, etapa, status, itens_entrada,
                 itens_saida, custo_usd, detalhe)
            VALUES (:r, :t, :e, :s, :ie, :isd, :c, CAST(:d AS jsonb))
            """
        ),
        {"r": run_id, "t": tenant_id, "e": etapa, "s": status, "ie": entrada,
         "isd": saida, "c": custo, "d": json.dumps(detalhe or {})},
    )


def apply_callback(
    conn: Connection, consulta_id, tenant_id, run_id, leads: list[LeadLimpo],
    custo_total: float, parcial: bool, solicitados: int,
) -> None:
    """Persist leads, debit quota by delivered, finalize statuses."""
    if leads:
        conn.execute(
            text(
                """
                INSERT INTO leads
                    (consulta_id, tenant_id, empresa_nome, pais, cidade, tipo_negocio,
                     site, telefone, email, whatsapp, instagram, score, racional, fontes)
                VALUES
                    (:cid, :tid, :empresa, :pais, :cidade, :tipo, :site, :tel, :email,
                     :wpp, :ig, :score, :racional, CAST(:fontes AS jsonb))
                """
            ),
            [
                {
                    "cid": consulta_id, "tid": tenant_id, "empresa": ld.empresa_nome,
                    "pais": ld.pais, "cidade": ld.cidade, "tipo": ld.tipo_negocio,
                    "site": ld.site, "tel": ld.telefone, "email": ld.email,
                    "wpp": ld.whatsapp, "ig": ld.instagram, "score": ld.score,
                    "racional": ld.racional, "fontes": json.dumps(ld.fontes),
                }
                for ld in leads
            ],
        )

    entregues = len(leads)
    status = "parcial" if (parcial or entregues < solicitados) else "pronta"
    conn.execute(
        text(
            "UPDATE consultas SET status = :st, leads_entregues = :n, concluido_em = now() "
            "WHERE id = :id"
        ),
        {"st": status, "n": entregues, "id": consulta_id},
    )
    # Quota debited by DELIVERED leads (ARQUITETURA.md §7), in the active cycle.
    conn.execute(
        text(
            """
            UPDATE assinaturas SET leads_consumidos_mes = leads_consumidos_mes + :n
            WHERE tenant_id = :t AND status = 'ativa'
              AND current_date BETWEEN ciclo_inicio AND ciclo_fim
            """
        ),
        {"n": entregues, "t": tenant_id},
    )
    conn.execute(
        text(
            "UPDATE pipeline_runs SET status = :st, custo_total_usd = :c, concluido_em = now() "
            "WHERE id = :r"
        ),
        {"st": status, "c": custo_total, "r": run_id},
    )


def run_consulta(consulta_id: str) -> None:
    prov = get_providers()
    ceiling = settings.cost_ceiling_usd

    with admin_engine.begin() as conn:
        c = conn.execute(
            text(
                "SELECT tenant_id, produto_descricao, perfil_comprador, paises, leads_solicitados "
                "FROM consultas WHERE id = :id"
            ),
            {"id": consulta_id},
        ).mappings().first()
        if c is None:
            return
        run_id = conn.execute(
            text("SELECT id FROM pipeline_runs WHERE consulta_id = :id"), {"id": consulta_id}
        ).scalar_one()
        conn.execute(
            text("UPDATE consultas SET status = 'processando' WHERE id = :id"), {"id": consulta_id}
        )
        conn.execute(
            text("UPDATE pipeline_runs SET status = 'processando', iniciado_em = now() WHERE id = :r"),
            {"r": run_id},
        )

    tenant_id = str(c["tenant_id"])
    alvo = c["leads_solicitados"]
    mercado = (c["paises"] or ["(n/d)"])[0]
    produto = c["produto_descricao"] or ""
    perfil = c["perfil_comprador"] or ""
    custo = 0.0
    parcial = False

    try:
        with admin_engine.begin() as conn:
            empresas, custo1 = prov.discovery.descobrir(produto, mercado, perfil, alvo)
            custo += custo1
            _stage(conn, run_id, tenant_id, "descoberta", "ok", 0, len(empresas), custo1)

            if custo >= ceiling:
                parcial = True
                _stage(conn, run_id, tenant_id, "enriquecimento", "pulada", len(empresas), 0, 0,
                       {"motivo": "teto de custo"})
                apply_callback(conn, consulta_id, tenant_id, run_id, [], custo, True, alvo)
                return

            brutos, custo2 = prov.enrichment.enriquecer(empresas, mercado)
            custo += custo2
            _stage(conn, run_id, tenant_id, "enriquecimento", "ok", len(empresas), len(brutos), custo2)

            leads, custo3 = prov.cleaner.limpar(brutos, produto, perfil, alvo)
            custo += custo3
            _stage(conn, run_id, tenant_id, "limpeza", "ok", len(brutos), len(leads), custo3)

            apply_callback(conn, consulta_id, tenant_id, run_id, leads, custo, parcial, alvo)
    except Exception as exc:  # noqa: BLE001 - mark the run as errored, surface the message
        with admin_engine.begin() as conn:
            conn.execute(
                text("UPDATE consultas SET status = 'erro', erro_msg = :m WHERE id = :id"),
                {"m": str(exc)[:500], "id": consulta_id},
            )
            conn.execute(
                text("UPDATE pipeline_runs SET status = 'erro', concluido_em = now() WHERE id = :r"),
                {"r": run_id},
            )
