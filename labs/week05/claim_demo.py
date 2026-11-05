"""Step 2: two workers claim at the same moment and get different tasks, without waiting.

Run from labs/week05 with TEST_DATABASE_URL set:  uv run python claim_demo.py
"""

import os
from pathlib import Path
from typing import LiteralString, cast

import psycopg

URL = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
# psycopg's types accept only SQL written literally in the code, a guard against SQL injection
# (a query built from user input can't pass as a LiteralString). claim.sql is our own file in the
# repo, never user input, so we vouch for it explicitly.
CLAIM = cast(LiteralString, (Path(__file__).parent / "claim.sql").read_text())


def setup() -> None:
    with psycopg.connect(URL, autocommit=True) as conn:
        # The TEST database only: every test empties it anyway. Leftover queued tasks from other
        # runs would otherwise be claimed first.
        conn.execute(
            "TRUNCATE tool_calls, runs, idempotency_keys, tasks, tenants CASCADE"
        )
        conn.execute("INSERT INTO tenants (id) VALUES ('alice') ON CONFLICT DO NOTHING")
        for i in (1, 2, 3):
            conn.execute(
                "INSERT INTO tasks (id, tenant_id, state, input, created_at, updated_at) "
                "VALUES (%s, 'alice', 'queued', 'x', now() + %s * interval '1 second', now())",
                (f"t_q{i}", i),
            )


def claim(conn: psycopg.Connection) -> str | None:
    row = conn.execute(CLAIM).fetchone()
    return None if row is None else str(row[0])


def main() -> None:
    setup()
    w1 = psycopg.connect(URL)
    w2 = psycopg.connect(URL)
    try:
        got1 = claim(w1)  # w1's transaction is still open: its row stays locked
        got2 = claim(w2)  # w2 skips w1's locked row instead of waiting
        print(
            f"worker 1 claimed {got1}, worker 2 claimed {got2}, both without committing yet"
        )
        assert got1 is not None and got2 is not None and got1 != got2
        w1.commit()
        w2.commit()
    finally:
        w1.close()
        w2.close()
    with psycopg.connect(URL) as conn:
        rows = conn.execute(
            "SELECT id, state FROM tasks WHERE id LIKE 't_q%' ORDER BY id"
        ).fetchall()
    for task_id, state in rows:
        print(f"  {task_id}: {state}")


if __name__ == "__main__":
    main()
