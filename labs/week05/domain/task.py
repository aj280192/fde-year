"""A task, its six states, and the rules for moving between them (DESIGN.md section 6)."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum

from domain.errors import TaskAlreadyFinished


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL = frozenset({TaskState.SUCCEEDED, TaskState.FAILED, TaskState.CANCELLED})

ALLOWED: dict[TaskState, frozenset[TaskState]] = {
    TaskState.QUEUED: frozenset(
        {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.RUNNING: frozenset(
        {
            TaskState.WAITING_FOR_INPUT,
            TaskState.SUCCEEDED,
            TaskState.FAILED,
            TaskState.CANCELLED,
        }
    ),
    TaskState.WAITING_FOR_INPUT: frozenset(
        {TaskState.RUNNING, TaskState.FAILED, TaskState.CANCELLED}
    ),
    TaskState.SUCCEEDED: frozenset(),
    TaskState.FAILED: frozenset(),
    TaskState.CANCELLED: frozenset(),
}


def can_transition(old: TaskState, new: TaskState) -> bool:
    return new in ALLOWED[old]


@dataclass(frozen=True)
class TaskError:
    """Why a task failed. Data about the task, not an HTTP error."""

    code: str
    message: str


# kw_only: fields with defaults (result, error) can come before fields without (the times),
# and every Task(...) call has to name its fields, which reads better anyway.
@dataclass(frozen=True, kw_only=True)
class Task:
    id: str
    state: TaskState
    input: str
    result: str | None = None
    error: TaskError | None = None
    created_at: datetime
    updated_at: datetime

    def cancel(self, now: datetime) -> "Task":
        """Return the cancelled task. Cancelling twice is a no-op; a finished task can't be cancelled."""
        if self.state is TaskState.CANCELLED:
            return self
        if not can_transition(self.state, TaskState.CANCELLED):
            raise TaskAlreadyFinished(self.id, self.state)
        return replace(self, state=TaskState.CANCELLED, updated_at=now)
