"""The JSON shapes of requests and responses. Only the API layer uses these."""

from datetime import datetime
from typing import Literal

from domain.task import Task, TaskState
from pydantic import BaseModel, ConfigDict, Field, JsonValue


class CreateTaskRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    input: str = Field(min_length=1, max_length=10_000)


class TaskErrorOut(BaseModel):
    code: str
    message: str


class TaskOut(BaseModel):
    id: str
    state: TaskState
    input: str
    result: str | None = None
    error: TaskErrorOut | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, task: Task) -> "TaskOut":
        """Every field written out by hand, so a new internal field can't leak into the JSON."""
        error = (
            None
            if task.error is None
            else TaskErrorOut(code=task.error.code, message=task.error.message)
        )
        return cls(
            id=task.id,
            state=task.state,
            input=task.input,
            result=task.result,
            error=error,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


class ListTasksResponse(BaseModel):
    tasks: list[TaskOut]
    next_page_token: str = ""  # empty means this is the last page


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
