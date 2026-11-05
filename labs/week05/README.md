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