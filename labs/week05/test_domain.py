"""The domain Task on its own: plain Python, no HTTP, no Pydantic."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta

import pytest
from domain.errors import DomainError, TaskAlreadyFinished
from domain.task import Task, TaskError, TaskState

T0 = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
LATER = T0 + timedelta(seconds=5)


def make(state: TaskState = TaskState.QUEUED) -> Task:
    return Task(id="t_1", state=state, input="x", created_at=T0, updated_at=T0)


@pytest.mark.parametrize(
    "state", [TaskState.QUEUED, TaskState.RUNNING, TaskState.WAITING_FOR_INPUT]
)
def test_cancel_an_unfinished_task(state: TaskState) -> None:
    task = make(state)
    cancelled = task.cancel(LATER)
    assert cancelled.state is TaskState.CANCELLED
    assert cancelled.updated_at == LATER
    assert task.state is state  # the original is untouched


def test_cancel_twice_returns_the_same_task() -> None:
    once = make().cancel(LATER)
    assert once.cancel(LATER + timedelta(seconds=5)) is once  # no new timestamp


@pytest.mark.parametrize("state", [TaskState.SUCCEEDED, TaskState.FAILED])
def test_cannot_cancel_a_finished_task(state: TaskState) -> None:
    with pytest.raises(TaskAlreadyFinished) as info:
        make(state).cancel(LATER)
    assert info.value.task_id == "t_1"
    assert info.value.state == state
    assert isinstance(info.value, DomainError)


def test_task_is_frozen() -> None:
    task = make()
    with pytest.raises(FrozenInstanceError):
        task.state = TaskState.RUNNING  # type: ignore[misc]


def test_fields_must_be_named() -> None:
    with pytest.raises(TypeError):
        Task("t_1", TaskState.QUEUED, "x", None, None, T0, T0)  # type: ignore[misc]


def test_task_error_is_frozen() -> None:
    error = TaskError(code="TOOL_UNAVAILABLE", message="kubectl timed out")
    with pytest.raises(FrozenInstanceError):
        error.code = "OTHER"  # type: ignore[misc]
