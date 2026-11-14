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

### Asking questions (`POST /v1/ask`, added 14 Nov)

`POST /v1/ask` answers a question from the health booklets in `capstones/05-health-rag`: an `answer` event
and a `citations` event, or an `abstain` event with the reason, then `done`. The whole answer is checked
before any of it is sent (DESIGN.md, section 14, row 19). It needs the capstone's database and Ollama:

    export HEALTH_RAG_DATABASE_URL=postgresql://postgres:dev@localhost:5432/health_rag
    TASKS_API_KEY_HASH=<hash> uv run python labs/week05/serve.py
    curl -sN -X POST localhost:8000/v1/ask -H "X-API-Key: <key>" -H "Content-Type: application/json" \
      -d '{"question": "How should specimens be collected for suspected anthrax?"}'

Without `HEALTH_RAG_DATABASE_URL`, the route answers 501.

## Test it
export TEST_DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/tasks_test
uv run pytest labs/week05 -q        # repository and service tests run on memory and Postgres

### A lost update, then prevented with `FOR UPDATE`

A user cancels a running task (session A) while a worker marks it succeeded (session B). Both read
the state first, as `services.cancel_task` does.

| | Without a lock | With `SELECT … FOR UPDATE` |
| --- | --- | --- |
| A reads | `running` | `running`, and locks the row |
| B reads | `running` | **waits** for A's lock (about 1 s in the demo) |
| A writes `cancelled`, commits | ✓ | ✓, and the lock is released |
| B | writes `succeeded` on stale information, commits | its read returns `cancelled`; `cancelled → succeeded` is illegal, so it refuses |
| **Final state** | **`succeeded`: the cancel is lost, and the task made an illegal move** | **`cancelled`: correct** |

**What this means:** `FOR UPDATE` locks the row from the read until the commit, so a second
transaction's read waits and then sees the new value. The lock only helps if the read, the check
and the write are **one transaction**. In the API today they aren't: the service reads and checks
(`get_task`, `task.cancel`), and `save` writes, in separate transactions. Locking inside `save`
alone would not prevent this. The fix to choose (DESIGN.md section 14, row 6):

- a conditional update: `UPDATE tasks SET … WHERE id = :id AND state = :expected`, where zero rows
  updated means someone else changed the task first (compare-and-set; holds no lock between calls)
- or a unit of work that keeps one transaction across the whole service call (*Architecture
  Patterns* ch. 6)

### Claiming a task: `FOR UPDATE SKIP LOCKED`

`claim.sql` is the query a worker runs to take one queued task. In `claim_demo.py`, two workers
claim at the same moment, without committing: worker 1 gets `t_q1`, worker 2 **skips the locked
row** and gets `t_q2`, and neither waits. After both commit, `t_q1` and `t_q2` are `running` and
`t_q3` is still `queued`. Without `SKIP LOCKED`, worker 2 would wait for worker 1 to finish;
without `FOR UPDATE`, both could take `t_q1`.

### Run them

```bash
export TEST_DATABASE_URL=postgresql+psycopg://postgres:dev@localhost:5432/tasks_test
cd labs/week05
uv run python race_demo.py
uv run python claim_demo.py
```

Both use the **test** database only: `claim_demo.py` empties it first.

## Results

### One million tasks, two slow queries

1,000,000 tasks across 50 tenants (20,000 each; 90% finished, 10% active), after `VACUUM ANALYZE`.
Postgres 17 in Docker. Times are Execution Time from `EXPLAIN (ANALYZE, BUFFERS)`.

| Query | Before | After | Faster | Pages read | Index | Plan before → after |
| --- | --- | --- | --- | --- | --- | --- |
| A tenant's newest 20 tasks (the list endpoint) | 28.2 ms | 0.12 ms | 235× | 13,157 → 25 | `(tenant_id, created_at, id)` | Parallel Seq Scan + top-N heapsort → `Index Scan Backward`, no sort |
| Active tasks by state, one tenant | 28.6 ms | 0.69 ms | 42× | 13,141 → 5 | partial: `(tenant_id, state) WHERE state IN ('queued', 'running', 'waiting_for_input')` | Parallel Seq Scan + sort → `Index Only Scan`, 0 heap fetches |

Index sizes: the partial index is **744 kB**; the full composite index is **55 MB**, 74 times larger.

**What I noticed:**
- Before the indexes, both queries read the whole table (about 13,000 pages) to return 20 rows or 3 counts.
  Every page was already in memory (`shared hit`, no `read`), so 28 ms is the *best* case;
  reading from disk would be far slower.
- The planner's estimates were close (about 20,300 rows estimated for tenant_07, 20,000 actual),
  because `ANALYZE` had run. Bad estimates weren't the problem; the missing index was.
- The partial index holds only active tasks, about 10% of rows, so it's tiny, and it answers the count
  from the index alone. `Heap Fetches: 0` means `VACUUM` had marked the pages all-visible, so the table
  was never touched.
- The composite index is the one the initial migration already creates. This lab is the evidence for it.
  The partial index isn't in a migration yet: that's a second Alembic revision (follow-up).