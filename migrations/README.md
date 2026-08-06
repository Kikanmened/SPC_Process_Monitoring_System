# Database migrations

Alembic revisions for the **PostgreSQL** production schema ([ADR-0008](../docs/DECISION_LOG.md#adr-0008)).

DuckDB local stores apply the same DDL from
`spc_platform.infrastructure.repositories.ddl` when the adapter opens — they
do not run Alembic.

## Usage

```bash
export SPC_DATABASE_URL='postgresql+psycopg://user:pass@localhost:5432/spc'
uv run alembic upgrade head
uv run alembic downgrade -1
```

Contract and integration tests use `SPC_TEST_DATABASE_URL` when set; without
it, PostgreSQL cases are skipped and Fake + DuckDB still run.
