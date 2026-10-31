from datetime import datetime
from typing import Literal

# Step 3: the rules now live in the domain. Re-exported here so nothing else has to change yet.
from domain.task import ALLOWED, TERMINAL, TaskState, can_transition
from pydantic import BaseModel, ConfigDict, Field, JsonValue

__all__ = ["ALLOWED", "TERMINAL", "TaskState", "can_transition"]


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
    next_page_token: str = ""


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
