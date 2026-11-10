#!/usr/bin/env bash
# Start a throwaway local Postgres 16 cluster (no Docker needed) and provision
# the atom database + roles. Writes the cluster into ./.pg (gitignored).
set -euo pipefail

cd "$(dirname "$0")/.."
PGDATA="$(pwd)/.pg"
PGBIN="$(ls -d /usr/lib/postgresql/*/bin | sort -V | tail -1)"
PORT="${PGPORT:-5432}"

if [ ! -d "$PGDATA" ]; then
  "$PGBIN/initdb" -D "$PGDATA" --auth=trust --username="$(whoami)" >/dev/null
fi

"$PGBIN/pg_ctl" -D "$PGDATA" -o "-p $PORT -k /tmp" -l "$PGDATA/server.log" start
sleep 1

psql -h localhost -p "$PORT" -d postgres -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='atom_owner') THEN CREATE ROLE atom_owner LOGIN NOSUPERUSER CREATEDB; END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='atom_app')   THEN CREATE ROLE atom_app   LOGIN NOSUPERUSER NOBYPASSRLS; END IF;
END \$\$;
SELECT 'CREATE DATABASE atom OWNER atom_owner'
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname='atom')\gexec
SQL

psql -h localhost -p "$PORT" -d atom -v ON_ERROR_STOP=1 -c "CREATE EXTENSION IF NOT EXISTS citext; GRANT ALL ON SCHEMA public TO atom_owner;"
echo "postgres up on port $PORT; database 'atom' ready"
