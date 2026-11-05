"""Step 1: a lost update between two transactions, then the same race prevented with FOR UPDATE.

Session A cancels a running task; session B (a worker) marks it succeeded. Both read the state
first, as the service does. Run from labs/week05 with TEST_DATABASE_URL set:

    uv run python race_demo.py

It uses its own task row, 't_race', in the TEST database, and resets it before each scenario.
"""

import os
import threading
import time

import psycopg

URL = os.environ["TEST_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
SETUP = """
INSERT INTO tenants (id) VALUES ('alice') ON CONFLICT DO NOTHING;
INSERT INTO tasks (id, tenant_id, state, input, created_at, updated_at)
VALUES ('t_race', 'alice', 'running', 'x', now(), now())
ON CONFLICT (id) DO UPDATE SET state = 'running', updated_at = now();
"""


def reset() -> None:
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(SETUP)


def final_state() -> str:
    with psycopg.connect(URL) as conn:
        row = conn.execute("SELECT state FROM tasks WHERE id = 't_race'").fetchone()
        assert row is not None
        return str(row[0])


def lost_update() -> None:
    """Both read 'running', both decide their move is legal, the later commit wins."""
    reset()
    a = psycopg.connect(
        URL
    )  # each connection is its own session; a transaction starts on first use
    b = psycopg.connect(URL)
    try:
        seen_a = a.execute("SELECT state FROM tasks WHERE id = 't_race'").fetchone()
        seen_b = b.execute("SELECT state FROM tasks WHERE id = 't_race'").fetchone()
        print(f"  A reads {seen_a}, B reads {seen_b}")
        a.execute(
            "UPDATE tasks SET state = 'cancelled', updated_at = now() WHERE id = 't_race'"
        )
        a.commit()
        print("  A cancels and commits")
        b.execute(
            "UPDATE tasks SET state = 'succeeded', updated_at = now() WHERE id = 't_race'"
        )
        b.commit()
        print("  B, still believing it's 'running', marks it succeeded and commits")
    finally:
        a.close()
        b.close()
    print(
        f"  final state: {final_state()}  <- the cancel is lost, and cancelled -> succeeded is illegal"
    )


def with_for_update() -> None:
    """The lock covers read, check and write: B's read waits for A, then sees 'cancelled'."""
    reset()
    a = psycopg.connect(URL)
    b = psycopg.connect(URL)
    log: list[str] = []

    def worker_b() -> None:
        start = time.monotonic()
        row = b.execute(
            "SELECT state FROM tasks WHERE id = 't_race' FOR UPDATE"
        ).fetchone()
        assert row is not None
        state = str(row[0])
        log.append(
            f"  B's read waited {time.monotonic() - start:.1f} s, then saw '{state}'"
        )
        if state == "running":  # the check, inside the same transaction as the write
            b.execute(
                "UPDATE tasks SET state = 'succeeded', updated_at = now() WHERE id = 't_race'"
            )
            log.append("  B marks it succeeded")
        else:
            log.append(f"  B refuses: {state} -> succeeded is not a legal move")
        b.commit()

    try:
        a.execute("SELECT state FROM tasks WHERE id = 't_race' FOR UPDATE")
        print("  A reads 'running' FOR UPDATE: the row is now locked by A")
        thread = threading.Thread(target=worker_b)
        thread.start()
        time.sleep(1.0)  # B is now blocked on the lock
        a.execute(
            "UPDATE tasks SET state = 'cancelled', updated_at = now() WHERE id = 't_race'"
        )
        a.commit()
        print("  A cancels and commits, releasing the lock")
        thread.join()
    finally:
        a.close()
        b.close()
    print("\n".join(log))
    print(f"  final state: {final_state()}  <- the cancel stands")


if __name__ == "__main__":
    print("1. Without a lock:")
    lost_update()
    print("\n2. With SELECT ... FOR UPDATE:")
    with_for_update()
