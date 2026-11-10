-- Runs once on first init of the Postgres container (docker-entrypoint-initdb.d).
-- POSTGRES_USER=atom_owner already owns database POSTGRES_DB=atom.
CREATE ROLE atom_app LOGIN NOSUPERUSER NOBYPASSRLS;
CREATE EXTENSION IF NOT EXISTS citext;
GRANT ALL ON SCHEMA public TO atom_owner;
