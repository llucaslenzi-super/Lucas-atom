"""Provision a demo tenant + admin user + active subscription.

Runs as the owner role (RLS-exempt), mirroring the admin-created onboarding
(no self-signup in v1). Idempotent on the demo email.
"""
from datetime import date

from sqlalchemy import create_engine, text

from app.config import settings
from app.security import hash_password

DEMO_EMAIL = "admin@demo.com"
DEMO_SENHA = "demo12345"


def main() -> None:
    engine = create_engine(settings.admin_database_url, future=True)
    with engine.begin() as c:
        if c.execute(text("SELECT 1 FROM users WHERE email = :e"), {"e": DEMO_EMAIL}).first():
            print("seed: demo tenant already present")
            return
        tid = c.execute(
            text("INSERT INTO tenants(nome) VALUES ('Demo Exportadora') RETURNING id")
        ).scalar_one()
        c.execute(
            text(
                "INSERT INTO users(tenant_id, email, senha_hash, role) "
                "VALUES (:t, :e, :h, 'admin')"
            ),
            {"t": tid, "e": DEMO_EMAIL, "h": hash_password(DEMO_SENHA)},
        )
        c.execute(
            text(
                """
                INSERT INTO assinaturas
                    (tenant_id, leads_contratados_mes, ciclo_inicio, ciclo_fim, plano, status)
                VALUES (:t, 350, :ini, :fim, 'padrao', 'ativa')
                """
            ),
            {"t": tid, "ini": date.today().replace(day=1), "fim": date(2999, 12, 31)},
        )
    print(f"seed: created tenant/admin ({DEMO_EMAIL} / {DEMO_SENHA}) + 350-lead subscription")


if __name__ == "__main__":
    main()
