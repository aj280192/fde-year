"""The Postgres implementation of the TaskRepository protocol (repository.py).

It behaves exactly like InMemoryTaskRepository, and must pass the same tests. Each method is one
transaction. Nothing outside this file sees a TaskRow: services only ever get domain objects.
"""

from datetime import datetime

from domain.idempotency import IdempotencyRecord
from domain.task import Task, TaskError, TaskState
from psycopg.errors import UniqueViolation
from sqlalchemy import Engine, select, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from db.models import IdempotencyKeyRow, TaskRow, TenantRow

# A position in "newest first" order: (created_at, task id). Tasks strictly before it come next.
# The same definition as repository.Cursor; kept here so db/ doesn't import the top-level module.
Cursor = tuple[datetime, str]


class PostgresTaskRepository:
    """Tasks, owners and idempotency records in Postgres."""

    def __init__(self, engine: Engine) -> None:
        # The caller makes the engine (serve.py, conftest.py): no connection is opened on import.
        self._sessions = sessionmaker(engine, expire_on_commit=False)

    def add(self, task: Task, owner: str) -> None:
        """Store a new task and record who owns it.

        The owner's tenant row is created if it's missing. A real system would create tenants
        through an admin API; here the repository makes sure the foreign key is satisfied.
        """
        try:
            with self._sessions() as s, s.begin():
                s.execute(
                    pg_insert(TenantRow)
                    .values(id=owner)
                    .on_conflict_do_nothing(index_elements=["id"])
                )
                s.add(_to_row(task, owner))
                s.flush()  # send the INSERT now, so a constraint violation is raised inside the try

        except IntegrityError as exc:
            # Only a duplicate primary key means "already exists". A failed CHECK (input too long)
            # or foreign key is a different bug, and must not be reported as a duplicate.
            if not isinstance(exc.orig, UniqueViolation):
                raise
            raise ValueError(f"task {task.id} already exists") from exc

    def get(self, task_id: str, owner: str) -> Task | None:
        """The task, or None if it doesn't exist OR belongs to someone else (never confirm it exists)."""
        with self._sessions() as s:
            row = s.scalars(
                select(TaskRow).where(TaskRow.id == task_id, TaskRow.tenant_id == owner)
            ).one_or_none()
            return None if row is None else _to_domain(row)

    def save(self, task: Task) -> None:
        """Replace an existing task with a changed copy. The owner never changes."""
        # Not yet safe against a concurrent change between the service's get and this save
        # (DESIGN.md section 14, row 6): Thursday's lab adds SELECT ... FOR UPDATE.
        with self._sessions() as s, s.begin():
            row = s.get(TaskRow, task.id)
            if row is None:
                raise KeyError(
                    f"task {task.id} was never added"
                )  # save updates; add creates
            # tenant_id, input and created_at never change after a task is created.
            row.state = task.state.value
            row.result = task.result
            row.error_code = task.error.code if task.error else None
            row.error_message = task.error.message if task.error else None
            row.updated_at = task.updated_at

    def list_for_owner(
        self, owner: str, before: Cursor | None, limit: int
    ) -> list[Task]:
        """Up to `limit` of the owner's tasks, newest first, starting after `before` if given.

        Matches the index (tenant_id, created_at, id): Postgres reads it backwards, with no sort.
        """
        query = (
            select(TaskRow)
            .where(TaskRow.tenant_id == owner)
            .order_by(TaskRow.created_at.desc(), TaskRow.id.desc())
            .limit(limit)
        )
        if before is not None:
            # (created_at, id) < (t, id): a row comparison, exactly like Python's tuple compare.
            query = query.where(
                tuple_(TaskRow.created_at, TaskRow.id) < tuple_(*before)
            )
        with self._sessions() as s:
            return [_to_domain(row) for row in s.scalars(query)]

    def get_idempotency(self, owner: str, key: str) -> IdempotencyRecord | None:
        """The record for this (owner, idempotency key), or None."""
        with self._sessions() as s:
            row = s.get(IdempotencyKeyRow, (owner, key))
            if row is None:
                return None
            return IdempotencyRecord(
                fingerprint=row.fingerprint,
                task_id=row.task_id,
                created_at=row.created_at,
            )

    def put_idempotency(self, owner: str, key: str, record: IdempotencyRecord) -> None:
        """Remember what an idempotent create produced, replacing any older record."""
        stmt = pg_insert(IdempotencyKeyRow).values(
            tenant_id=owner,
            key=key,
            fingerprint=record.fingerprint,
            task_id=record.task_id,
            created_at=record.created_at,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["tenant_id", "key"],
            set_={
                "fingerprint": stmt.excluded.fingerprint,
                "task_id": stmt.excluded.task_id,
                "created_at": stmt.excluded.created_at,
            },
        )

        with self._sessions() as s, s.begin():
            s.execute(stmt)


def _to_domain(row: TaskRow) -> Task:
    """A database row as a domain Task. `state` comes back as text, so it's turned into TaskState."""
    error = None
    if row.error_code is not None and row.error_message is not None:
        error = TaskError(code=row.error_code, message=row.error_message)

    return Task(
        id=row.id,
        state=TaskState(row.state),
        input=row.input,
        result=row.result,
        error=error,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _to_row(task: Task, tenant_id: str) -> TaskRow:
    """A domain Task as a new database row, owned by `tenant_id`."""
    error_code = task.error.code if task.error else None
    error_message = task.error.message if task.error else None

    return TaskRow(
        id=task.id,
        tenant_id=tenant_id,
        state=task.state.value,
        input=task.input,
        result=task.result,
        error_code=error_code,
        error_message=error_message,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )
