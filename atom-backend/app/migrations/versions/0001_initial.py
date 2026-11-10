"""initial schema + RLS

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

BUSINESS_TABLES = [
    "users",
    "assinaturas",
    "relatorios",
    "consultas",
    "leads",
    "exports",
    "pipeline_runs",
    "pipeline_stage_events",
    "eventos_auditoria",
]


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE tenants (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            nome text NOT NULL,
            cnpj text,
            status text NOT NULL DEFAULT 'ativo',
            criado_em timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE users (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            email citext NOT NULL UNIQUE,
            senha_hash text NOT NULL,
            role text NOT NULL DEFAULT 'user',
            criado_em timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE assinaturas (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            leads_contratados_mes int NOT NULL,
            leads_consumidos_mes int NOT NULL DEFAULT 0,
            ciclo_inicio date NOT NULL,
            ciclo_fim date NOT NULL,
            plano text NOT NULL DEFAULT 'padrao',
            status text NOT NULL DEFAULT 'ativa',
            criado_em timestamptz NOT NULL DEFAULT now()
        );

        -- relatorio do cliente (input). Delta vs doc original: tipo + codigo_fiscal
        -- (produto -> NCM, servico -> NBS) no lugar de produto_ncm.
        CREATE TABLE relatorios (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            arquivo_gcs text,
            tipo text NOT NULL DEFAULT 'produto' CHECK (tipo IN ('produto','servico')),
            produto_descricao text,
            codigo_fiscal text,
            mercado_sugerido text,
            perfil_comprador text,
            criado_em timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE consultas (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid REFERENCES users(id),
            relatorio_id uuid REFERENCES relatorios(id),
            tipo text NOT NULL DEFAULT 'produto' CHECK (tipo IN ('produto','servico')),
            produto_descricao text,
            codigo_fiscal text,
            paises text[] NOT NULL DEFAULT '{}',
            perfil_comprador text,
            filtros jsonb NOT NULL DEFAULT '{}',
            plano text NOT NULL DEFAULT 'padrao',
            status text NOT NULL DEFAULT 'fila'
                CHECK (status IN ('fila','processando','pronta','erro','parcial')),
            leads_solicitados int NOT NULL DEFAULT 0,
            leads_entregues int NOT NULL DEFAULT 0,
            erro_msg text,
            criado_em timestamptz NOT NULL DEFAULT now(),
            concluido_em timestamptz
        );

        CREATE TABLE leads (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            consulta_id uuid NOT NULL REFERENCES consultas(id),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            empresa_nome text,
            pais text,
            cidade text,
            tipo_negocio text,
            site text,
            telefone text,
            email text,
            whatsapp text,
            instagram text,
            decisor_nome text,
            decisor_cargo text,
            decisor_linkedin text,
            decisor_email text,
            score numeric,
            racional text,
            fontes jsonb NOT NULL DEFAULT '{}',
            criado_em timestamptz NOT NULL DEFAULT now()
        );

        -- Delta: formato (xlsx|csv|pdf) para o export multi-formato.
        CREATE TABLE exports (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            consulta_id uuid NOT NULL REFERENCES consultas(id),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            formato text,
            gcs_path text,
            criado_em timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE pipeline_runs (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            consulta_id uuid NOT NULL REFERENCES consultas(id),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            status text NOT NULL DEFAULT 'fila',
            custo_total_usd numeric NOT NULL DEFAULT 0,
            iniciado_em timestamptz,
            concluido_em timestamptz,
            criado_em timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE pipeline_stage_events (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            pipeline_run_id uuid NOT NULL REFERENCES pipeline_runs(id),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            etapa text,
            status text,
            itens_entrada int,
            itens_saida int,
            custo_usd numeric,
            detalhe jsonb NOT NULL DEFAULT '{}',
            criado_em timestamptz NOT NULL DEFAULT now()
        );

        CREATE TABLE eventos_auditoria (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id uuid NOT NULL REFERENCES tenants(id),
            user_id uuid,
            acao text,
            detalhe jsonb NOT NULL DEFAULT '{}',
            criado_em timestamptz NOT NULL DEFAULT now()
        );
        """
    )

    # RLS: owner (atom_owner) is exempt by ENABLE (not FORCE), so migrations,
    # the SECURITY DEFINER login function and admin provisioning read all rows;
    # the app role (atom_app, NOBYPASSRLS) only ever sees its own tenant.
    op.execute(
        """
        ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenants_isolation ON tenants
            USING (id = current_setting('app.tenant_id', true)::uuid)
            WITH CHECK (id = current_setting('app.tenant_id', true)::uuid);
        """
    )
    for t in BUSINESS_TABLES:
        op.execute(
            f"""
            ALTER TABLE {t} ENABLE ROW LEVEL SECURITY;
            CREATE POLICY {t}_isolation ON {t}
                USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
                WITH CHECK (tenant_id = current_setting('app.tenant_id', true)::uuid);
            """
        )

    # Login path: resolve credentials by email across tenants, before the tenant
    # is known. SECURITY DEFINER runs as the owner (RLS-exempt).
    op.execute(
        """
        CREATE FUNCTION auth_lookup(p_email citext)
        RETURNS TABLE(user_id uuid, tenant_id uuid, role text, senha_hash text)
        LANGUAGE sql SECURITY DEFINER SET search_path = public AS $fn$
            SELECT id, tenant_id, role, senha_hash FROM users WHERE email = p_email;
        $fn$;
        """
    )

    # Grants to the app role (created by scripts/bootstrap_roles.sql).
    op.execute(
        """
        GRANT USAGE ON SCHEMA public TO atom_app;
        GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO atom_app;
        REVOKE EXECUTE ON FUNCTION auth_lookup(citext) FROM PUBLIC;
        GRANT EXECUTE ON FUNCTION auth_lookup(citext) TO atom_app;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS auth_lookup(citext);")
    for t in ["eventos_auditoria", "pipeline_stage_events", "pipeline_runs", "exports",
              "leads", "consultas", "relatorios", "assinaturas", "users", "tenants"]:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
