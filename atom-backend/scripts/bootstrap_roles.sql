-- Run once as a Postgres superuser, before migrations.
-- In production these roles/passwords come from infra (Cloud SQL + Secret Manager);
-- this file documents the role model and is used for local dev.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'atom_owner') THEN
        CREATE ROLE atom_owner LOGIN NOSUPERUSER CREATEDB;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'atom_app') THEN
        -- App role: subject to RLS (never bypasses), sees only its own tenant.
        CREATE ROLE atom_app LOGIN NOSUPERUSER NOBYPASSRLS;
    END IF;
END
$$;

-- Run connected to the target database (atom):
--   CREATE EXTENSION IF NOT EXISTS citext;
--   GRANT ALL ON SCHEMA public TO atom_owner;
