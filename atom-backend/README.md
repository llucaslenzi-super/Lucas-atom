# Atom — backend

Agente de Prospecção de Exportação (Atom). Backend: FastAPI + PostgreSQL.
Fase atual: Blocos 0–2 e 4 (esqueleto, schema + RLS, auth + tenancy, consulta + cota).

## Rodar local

### Com Docker
```bash
docker compose up
# API em http://localhost:8000  (health: /v1/health, docs: /docs)
```

### Sem Docker (Postgres nativo)
```bash
uv venv && uv pip install -e ".[dev]"
cp .env.example .env
bash scripts/dev_db.sh          # sobe Postgres local em ./.pg
uv run alembic upgrade head     # cria schema + RLS
uv run python -m app.seed       # tenant demo (admin@demo.com / demo12345)
uv run uvicorn app.main:app --reload
```

## Testes
```bash
bash scripts/dev_db.sh && uv run alembic upgrade head
uv run pytest
```
Cobrem: health, auth (login/refresh/token inválido/expirado), **isolamento
multi-tenant A×B (app + RLS no banco)** e **cota com corrida** (FOR UPDATE).

## Arquitetura multi-tenant (defesa em 2 camadas)
- **App:** `tenant_id` vem só do JWT; toda transação faz `SET LOCAL app.tenant_id`.
- **Banco:** RLS em todas as tabelas de negócio. `atom_app` (NOBYPASSRLS) só enxerga
  o próprio tenant; `atom_owner` (dono, isento de RLS) roda migrations/seed e a
  função `auth_lookup` (login entre tenants, SECURITY DEFINER).

## Próximos blocos
3 relatórios (upload + parse 2 modelos) · 5 integrações (OpenAI/Apify/Places,
mockadas até ter chave) · 6 orquestração (worker/n8n) · 7 export XLSX/CSV/PDF ·
8 GCP · 9 endurecimento. Ver o doc do plano.
