# Secrets templates

Secrets never enter git. Provide at runtime via environment variables or Docker
secrets ([DEPLOYMENT_PLAN.md](../../docs/DEPLOYMENT_PLAN.md) §5).

| Template key | Environment variable | Used by |
|---|---|---|
| `db_password` | `SPC_DB_PASSWORD` | Staging/production PostgreSQL |
| `database_url` | `SPC_DATABASE_URL` | SQLAlchemy URL for Postgres adapters |
| `auth_mode` | `SPC_AUTH_MODE` | `header` (local) or `proxy` (SSO at reverse proxy) |

Copy `*.example.yaml` values into the site secret store; do not commit real
values. Only `*.example.yaml` and this README are tracked under this directory.
