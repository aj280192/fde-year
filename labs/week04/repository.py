"""Where tasks are kept. Services depend on the TaskRepository protocol, never on a storage library.

Today there is one implementation, in memory. A Postgres one later has the same methods, so
nothing above this file changes.
"""

from datetime import datetime
from typing import Protocol

from domain.task import Task
from idempotency import IdempotencyRecord

# A position in "newest first" order: (created_at, task id). Tasks strictly before it come next.
Cursor = tuple[datetime, str]


class TaskRepository(Protocol):
    """The storage the services need, and nothing more."""

    def add(self, task: Task, owner: str) -> None:
        """Store a new task and record who owns it."""
        ...

    def get(self, task_id: str, owner: str) -> Task | None:
        """The task, or None if it doesn't exist OR belongs to someone else (never confirm it exists)."""
        ...

    def save(self, task: Task) -> None:
        """Replace an existing task with a changed copy. The owner never changes."""
        ...

    def list_for_owner(
        self, owner: str, before: Cursor | None, limit: int
    ) -> list[Task]:
        """Up to `limit` of the owner's tasks, newest first, starting after `before` if given."""
        ...

    def get_idempotency(self, owner: str, key: str) -> IdempotencyRecord | None:
        """The record for this (owner, idempotency key), or None."""
        ...

    def put_idempotency(self, owner: str, key: str, record: IdempotencyRecord) -> None:
        """Remember what an idempotent create produced, replacing any older record."""
        ...


class InMemoryTaskRepository:
    """Dicts in memory. Lost on restart; fine for tests and this week's lab."""

    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}
        self._owners: dict[
            str, str
        ] = {}  # task id -> owner key_id; kept apart from Task
        self._idempotency: dict[tuple[str, str], IdempotencyRecord] = {}

    def add(self, task: Task, owner: str) -> None:
        if task.id in self._tasks:
            raise ValueError(
                f"task {task.id} already exists"
            )  # a bug in the caller, not a user error
        self._tasks[task.id] = task
        self._owners[task.id] = owner

    def get(self, task_id: str, owner: str) -> Task | None:
        if self._owners.get(task_id) != owner:
            return None
        return self._tasks[task_id]

    def save(self, task: Task) -> None:
        if task.id not in self._tasks:
            raise KeyError(
                f"task {task.id} was never added"
            )  # save updates; add creates
        # No await anywhere in here, so in asyncio nothing can interleave between a service's
        # read and this write. A database needs a conditional UPDATE instead (DESIGN.md 14).
        self._tasks[task.id] = task

    def list_for_owner(
        self, owner: str, before: Cursor | None, limit: int
    ) -> list[Task]:
        mine = [self._tasks[tid] for tid, who in self._owners.items() if who == owner]
        # Tuples compare position by position: created_at first, then id as the tie-breaker.
        mine.sort(key=lambda t: (t.created_at, t.id), reverse=True)
        if before is not None:
            mine = [t for t in mine if (t.created_at, t.id) < before]
        return mine[:limit]

    def get_idempotency(self, owner: str, key: str) -> IdempotencyRecord | None:
        return self._idempotency.get((owner, key))

    def put_idempotency(self, owner: str, key: str, record: IdempotencyRecord) -> None:
        self._idempotency[(owner, key)] = record
