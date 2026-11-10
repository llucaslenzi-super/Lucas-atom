"""Test fixtures. Assumes a Postgres with migrations applied (see scripts/dev_db.sh).

Tenants are provisioned via the owner engine (RLS-exempt), like the real
admin-created onboarding; the API is then exercised as those tenants.
"""
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.config import settings
from app.main import app
from app.security import hash_password, make_access

admin = create_engine(settings.admin_database_url, future=True)

_ALL_TABLES = (
    "eventos_auditoria, pipeline_stage_events, pipeline_runs, exports, leads, "
    "consultas, relatorios, assinaturas, users, tenants"
)


@pytest.fixture(autouse=True)
def _clean_db():
    with admin.begin() as c:
        c.execute(text(f"TRUNCATE {_ALL_TABLES} RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def tenant_factory():
    def _make(nome: str, leads: int = 350, senha: str = "secret123") -> dict:
        with admin.begin() as c:
            tid = c.execute(
                text("INSERT INTO tenants(nome) VALUES (:n) RETURNING id"), {"n": nome}
            ).scalar_one()
            email = nome.lower().replace(" ", "") + "@demo.com"
            uid = c.execute(
                text(
                    "INSERT INTO users(tenant_id, email, senha_hash, role) "
                    "VALUES (:t, :e, :h, 'admin') RETURNING id"
                ),
                {"t": tid, "e": email, "h": hash_password(senha)},
            ).scalar_one()
            c.execute(
                text(
                    """
                    INSERT INTO assinaturas
                        (tenant_id, leads_contratados_mes, ciclo_inicio, ciclo_fim, plano, status)
                    VALUES (:t, :l, :ini, :fim, 'padrao', 'ativa')
                    """
                ),
                {"t": tid, "l": leads, "ini": date.today() - timedelta(days=1),
                 "fim": date.today() + timedelta(days=30)},
            )
        return {
            "tenant_id": str(tid),
            "user_id": str(uid),
            "email": email,
            "senha": senha,
            "token": make_access(str(uid), str(tid), "admin"),
        }

    return _make


def insert_consulta(tenant_id: str) -> str:
    """Insert a consulta directly for a tenant (owner engine, RLS-exempt)."""
    with admin.begin() as c:
        return str(
            c.execute(
                text(
                    "INSERT INTO consultas(tenant_id, tipo, leads_solicitados, status) "
                    "VALUES (:t, 'produto', 10, 'fila') RETURNING id"
                ),
                {"t": tenant_id},
            ).scalar_one()
        )
