"""Database access with two layers of multi-tenant defense.

- ``engine`` connects as the app role (NOBYPASSRLS). Every tenant-scoped
  transaction sets ``app.tenant_id`` so RLS policies filter rows.
- ``auth_lookup`` runs a SECURITY DEFINER function, the only path that reads a
  user across tenants (needed for login, before the tenant is known).
"""
from contextlib import contextmanager
from collections.abc import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Connection

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)

# System/owner engine (RLS-exempt): migrations, seed, and the internal pipeline
# worker/callback that must write across the tenant boundary on the tenant's behalf.
admin_engine = create_engine(settings.admin_database_url, pool_pre_ping=True, future=True)


@contextmanager
def tenant_tx(tenant_id: str) -> Iterator[Connection]:
    """A transaction scoped to one tenant. RLS sees only this tenant's rows."""
    with engine.begin() as conn:
        conn.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
        yield conn


def auth_lookup(email: str) -> dict | None:
    """Resolve login credentials by email, across tenants (SECURITY DEFINER)."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT user_id, tenant_id, role, senha_hash FROM auth_lookup(:email)"),
            {"email": email},
        ).mappings().first()
    return dict(row) if row else None
