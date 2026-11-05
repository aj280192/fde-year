# Week 5 · the task API on Postgres

## Schema

```mermaid
erDiagram
    tenants ||--o{ tasks : owns
    tenants ||--o{ idempotency_keys : owns
    tasks ||--o{ idempotency_keys : "created by"
    tasks ||--o{ runs : "attempted by"
    runs ||--o{ tool_calls : makes
```

## Run it
docker start pg
export DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/tasks
uv run alembic upgrade head         # from labs/week05

## Test it
export TEST_DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/tasks_test
uv run pytest labs/week05 -q        # repository and service tests run on memory and Postgres

## Results
(Saturday: query times before and after the indexes go here.)