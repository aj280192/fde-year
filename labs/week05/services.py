"""Use cases: create, get, cancel and list tasks.

Plain functions over a TaskRepository. They take plain values, return domain objects and
raise DomainErrors. Nothing here knows about HTTP: no status codes, headers or page tokens.
"""

import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from domain.errors import IdempotencyKeyReused, TaskNotFound
from domain.idempotency import TTL, IdempotencyRecord, fingerprint
from domain.task import Task, TaskState
from repository import Cursor, TaskRepository


def default_task_id() -> str:
    return "t_" + secrets.token_urlsafe(16)


@dataclass(frozen=True)
class Created:
    task: Task
    replayed: bool  # True when an idempotency key returned an earlier task


@dataclass(frozen=True)
class Page:
    tasks: list[Task]
    next_cursor: Cursor | None  # None means this is the last page


def get_task(repo: TaskRepository, owner: str, task_id: str) -> Task:
    task = repo.get(task_id, owner)
    if task is None:  # missing, or someone else's: callers can't tell which
        raise TaskNotFound(task_id)
    return task


def cancel_task(repo: TaskRepository, owner: str, task_id: str, now: datetime) -> Task:
    task = get_task(repo, owner, task_id)
    cancelled = task.cancel(now)  # raises TaskAlreadyFinished for a finished task
    if cancelled is not task:  # already cancelled: nothing changed, so nothing to write
        # No await between get and save, so nothing interleaves in asyncio. With a database
        # this becomes one conditional UPDATE (DESIGN.md section 14).
        repo.save(cancelled)
    return cancelled


def create_task(
    repo: TaskRepository,
    owner: str,
    input: str,
    idempotency_key: str | None,
    now: datetime,
    new_id: Callable[[], str] = default_task_id,
) -> Created:
    fp = fingerprint(input)

    if idempotency_key is not None:
        record = repo.get_idempotency(owner, idempotency_key)
        if record is not None and now - record.created_at <= TTL:
            if record.fingerprint != fp:
                raise IdempotencyKeyReused()
            earlier = repo.get(record.task_id, owner)
            # If the earlier task has gone (deleted, or expired from a database), make a new one
            # rather than fail: that's what the client was asking for in the first place.
            if earlier is not None:
                return Created(task=earlier, replayed=True)

    task = Task(
        id=new_id(), state=TaskState.QUEUED, input=input, created_at=now, updated_at=now
    )
    repo.add(task, owner)
    if idempotency_key is not None:
        record = IdempotencyRecord(fingerprint=fp, task_id=task.id, created_at=now)
        repo.put_idempotency(owner, idempotency_key, record)
    return Created(task=task, replayed=False)


def list_tasks(
    repo: TaskRepository, owner: str, page_size: int, after: Cursor | None
) -> Page:
    found = repo.list_for_owner(owner, before=after, limit=page_size + 1)  # one extra
    if len(found) <= page_size:
        return Page(tasks=found, next_cursor=None)
    page = found[:page_size]
    last = page[-1]  # the last task RETURNED, not the extra one
    return Page(tasks=page, next_cursor=(last.created_at, last.id))
