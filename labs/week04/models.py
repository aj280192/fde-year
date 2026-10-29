from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class TaskState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_INPUT = "waiting_for_input"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL = frozenset({TaskState.SUCCEEDED, TaskState.CANCELLED, TaskState.FAILED})

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
    TaskState.CANCELLED: frozenset(),
    TaskState.FAILED: frozenset(),
}


def can_transition(old: TaskState, new: TaskState) -> bool:
    return new in ALLOWED[old]


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    input: str = Field(min_length=1, max_length=10_000)


class TaskError(BaseModel):
    code: str
    message: str


class Task(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str
    state: TaskState
    input: str
    result: str | None = None
    error: TaskError | None = None
    created_at: datetime
    updated_at: datetime


class ListTasksResponse(BaseModel):
    tasks: list[Task]
    next_page_token: str = ""  # empty token means last page


class TaskEvent(BaseModel):
    id: str
    type: Literal["state_changed", "log", "output"]
    created_at: datetime
    data: dict[str, JsonValue]


class ErrorDetail(BaseModel):
    reason: str


class ErrorBody(BaseModel):
    code: int
    status: str
    message: str
    details: list[ErrorDetail]


class ErrorResponse(BaseModel):
    error: ErrorBody
