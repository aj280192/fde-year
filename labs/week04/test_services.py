"""The use cases on their own: a real in-memory repository, no HTTP, no FastAPI."""

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from itertools import count

import pytest
from domain.errors import IdempotencyKeyReused, TaskAlreadyFinished, TaskNotFound
from domain.task import TaskState
from repository import InMemoryTaskRepository, TaskRepository
from services import cancel_task, create_task, get_task, list_tasks

T0 = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


@pytest.fixture
def repo() -> TaskRepository:
    return InMemoryTaskRepository()


@pytest.fixture
def ids() -> Callable[[], str]:
    """Predictable ids: t_1, t_2, t_3..."""
    counter = count(1)
    return lambda: f"t_{next(counter)}"


def make(
    repo: TaskRepository,
    ids: Callable[[], str],
    owner: str = "alice",
    at: datetime = T0,
) -> str:
    """Create a task without an idempotency key and return its id."""
    return create_task(repo, owner, "Diagnose pods", None, at, new_id=ids).task.id


# ---- create and get ----


def test_create_then_get(repo: TaskRepository, ids: Callable[[], str]) -> None:
    created = create_task(repo, "alice", "Diagnose pods", None, T0, new_id=ids)
    assert created.replayed is False
    assert created.task.state is TaskState.QUEUED
    assert created.task.created_at == created.task.updated_at == T0
    assert get_task(repo, "alice", created.task.id) == created.task


def test_id_comes_from_new_id(repo: TaskRepository) -> None:
    created = create_task(repo, "alice", "x", None, T0, new_id=lambda: "t_fixed")
    assert created.task.id == "t_fixed"


def test_default_ids_are_unique(repo: TaskRepository) -> None:
    first = create_task(repo, "alice", "x", None, T0).task.id
    second = create_task(repo, "alice", "x", None, T0).task.id
    assert first != second
    assert first.startswith("t_")


def test_get_unknown_task(repo: TaskRepository) -> None:
    with pytest.raises(TaskNotFound) as info:
        get_task(repo, "alice", "t_nope")
    assert info.value.task_id == "t_nope"


def test_get_someone_elses_task(repo: TaskRepository, ids: Callable[[], str]) -> None:
    task_id = make(repo, ids, owner="alice")
    with pytest.raises(TaskNotFound):
        get_task(repo, "bob", task_id)


# ---- cancel ----


def test_cancel_saves_the_change(repo: TaskRepository, ids: Callable[[], str]) -> None:
    task_id = make(repo, ids)
    later = T0 + timedelta(seconds=5)
    cancelled = cancel_task(repo, "alice", task_id, later)
    assert cancelled.state is TaskState.CANCELLED
    assert cancelled.updated_at == later
    assert get_task(repo, "alice", task_id) == cancelled  # stored, not just returned


def test_cancel_twice_changes_nothing(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    task_id = make(repo, ids)
    first = cancel_task(repo, "alice", task_id, T0 + timedelta(seconds=5))
    second = cancel_task(repo, "alice", task_id, T0 + timedelta(seconds=99))
    assert second == first  # same updated_at


@pytest.mark.parametrize("finished", [TaskState.SUCCEEDED, TaskState.FAILED])
def test_cancel_finished_task(
    repo: TaskRepository, ids: Callable[[], str], finished: TaskState
) -> None:
    task_id = make(repo, ids)
    repo.save(replace(get_task(repo, "alice", task_id), state=finished))
    with pytest.raises(TaskAlreadyFinished):
        cancel_task(repo, "alice", task_id, T0)
    assert get_task(repo, "alice", task_id).state is finished  # unchanged


def test_cancel_someone_elses_task(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    task_id = make(repo, ids, owner="alice")
    with pytest.raises(TaskNotFound):
        cancel_task(repo, "bob", task_id, T0)
    assert get_task(repo, "alice", task_id).state is TaskState.QUEUED


# ---- idempotency ----


def test_same_key_and_input_replays(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    first = create_task(repo, "alice", "Diagnose pods", "k1", T0, new_id=ids)
    second = create_task(
        repo, "alice", "Diagnose pods", "k1", T0 + timedelta(minutes=1), new_id=ids
    )
    assert (first.replayed, second.replayed) == (False, True)
    assert second.task == first.task
    assert len(list_tasks(repo, "alice", 100, None).tasks) == 1


def test_same_key_different_input(repo: TaskRepository, ids: Callable[[], str]) -> None:
    create_task(repo, "alice", "Diagnose pods", "k1", T0, new_id=ids)
    with pytest.raises(IdempotencyKeyReused):
        create_task(repo, "alice", "Delete everything", "k1", T0, new_id=ids)


def test_key_still_valid_at_exactly_24_hours(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    first = create_task(repo, "alice", "x", "k1", T0, new_id=ids)
    again = create_task(repo, "alice", "x", "k1", T0 + timedelta(hours=24), new_id=ids)
    assert again.replayed and again.task.id == first.task.id


def test_key_expires_after_24_hours(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    first = create_task(repo, "alice", "x", "k1", T0, new_id=ids)
    later = create_task(
        repo, "alice", "x", "k1", T0 + timedelta(hours=24, seconds=1), new_id=ids
    )
    assert not later.replayed and later.task.id != first.task.id


def test_keys_are_per_owner(repo: TaskRepository, ids: Callable[[], str]) -> None:
    alice = create_task(repo, "alice", "x", "k1", T0, new_id=ids)
    bob = create_task(repo, "bob", "x", "k1", T0, new_id=ids)
    assert alice.task.id != bob.task.id
    assert not bob.replayed


def test_replay_returns_the_task_as_it_is_now(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    first = create_task(repo, "alice", "x", "k1", T0, new_id=ids)
    cancel_task(repo, "alice", first.task.id, T0)
    replay = create_task(repo, "alice", "x", "k1", T0, new_id=ids)
    assert replay.replayed and replay.task.state is TaskState.CANCELLED


def test_no_key_means_no_protection(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    create_task(repo, "alice", "x", None, T0, new_id=ids)
    create_task(repo, "alice", "x", None, T0, new_id=ids)
    assert len(list_tasks(repo, "alice", 100, None).tasks) == 2


# ---- list ----


def test_paging_walks_every_task_once(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    created = [make(repo, ids, at=T0 + timedelta(seconds=i)) for i in range(5)]
    seen: list[str] = []
    sizes: list[int] = []
    cursor = None
    while True:
        page = list_tasks(repo, "alice", 2, cursor)
        seen += [t.id for t in page.tasks]
        sizes.append(len(page.tasks))
        cursor = page.next_cursor
        if cursor is None:
            break
    assert sizes == [2, 2, 1]
    assert seen == list(reversed(created))  # newest first, each once


def test_exact_multiple_has_no_empty_last_page(
    repo: TaskRepository, ids: Callable[[], str]
) -> None:
    for i in range(4):
        make(repo, ids, at=T0 + timedelta(seconds=i))
    first = list_tasks(repo, "alice", 2, None)
    second = list_tasks(repo, "alice", 2, first.next_cursor)
    assert len(second.tasks) == 2 and second.next_cursor is None


def test_empty_list(repo: TaskRepository) -> None:
    page = list_tasks(repo, "alice", 20, None)
    assert page.tasks == [] and page.next_cursor is None
