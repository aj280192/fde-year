"""The in-memory repository on its own. A Postgres repository later must pass these same tests."""

from datetime import UTC, datetime, timedelta

import pytest
from domain.idempotency import IdempotencyRecord
from domain.task import Task, TaskState
from repository import InMemoryTaskRepository, TaskRepository

T0 = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)


def make(task_id: str, seconds: int = 0) -> Task:
    at = T0 + timedelta(seconds=seconds)
    return Task(
        id=task_id, state=TaskState.QUEUED, input="x", created_at=at, updated_at=at
    )


@pytest.fixture
def repo() -> TaskRepository:  # typed as the protocol: proves the class satisfies it
    return InMemoryTaskRepository()


def test_add_then_get(repo: TaskRepository) -> None:
    task = make("t_1")
    repo.add(task, owner="alice")
    assert repo.get("t_1", owner="alice") == task


def test_get_unknown_is_none(repo: TaskRepository) -> None:
    assert repo.get("t_nope", owner="alice") is None


def test_get_someone_elses_task_is_none(repo: TaskRepository) -> None:
    repo.add(make("t_1"), owner="alice")
    assert repo.get("t_1", owner="bob") is None


def test_adding_the_same_id_twice_is_a_bug(repo: TaskRepository) -> None:
    repo.add(make("t_1"), owner="alice")
    with pytest.raises(ValueError):
        repo.add(make("t_1"), owner="alice")


def test_save_replaces_the_task(repo: TaskRepository) -> None:
    repo.add(make("t_1"), owner="alice")
    cancelled = make("t_1").cancel(T0 + timedelta(seconds=5))
    repo.save(cancelled)
    found = repo.get("t_1", owner="alice")
    assert found is not None and found.state is TaskState.CANCELLED


def test_save_keeps_the_owner(repo: TaskRepository) -> None:
    repo.add(make("t_1"), owner="alice")
    repo.save(make("t_1").cancel(T0))
    assert repo.get("t_1", owner="bob") is None


def test_save_of_unknown_task_is_a_bug(repo: TaskRepository) -> None:
    with pytest.raises(KeyError):
        repo.save(make("t_never_added"))


def test_list_is_newest_first_and_limited(repo: TaskRepository) -> None:
    for i in range(5):
        repo.add(make(f"t_{i}", seconds=i), owner="alice")
    assert [t.id for t in repo.list_for_owner("alice", before=None, limit=3)] == [
        "t_4",
        "t_3",
        "t_2",
    ]


def test_list_after_a_cursor(repo: TaskRepository) -> None:
    for i in range(5):
        repo.add(make(f"t_{i}", seconds=i), owner="alice")
    page = repo.list_for_owner(
        "alice", before=(T0 + timedelta(seconds=2), "t_2"), limit=10
    )
    assert [t.id for t in page] == ["t_1", "t_0"]


def test_same_timestamp_is_ordered_by_id(repo: TaskRepository) -> None:
    repo.add(make("t_a"), owner="alice")
    repo.add(make("t_b"), owner="alice")
    first = repo.list_for_owner("alice", before=None, limit=1)
    rest = repo.list_for_owner(
        "alice", before=(first[0].created_at, first[0].id), limit=10
    )
    assert [t.id for t in first + rest] == ["t_b", "t_a"]  # both, once each


def test_list_shows_only_the_owners_tasks(repo: TaskRepository) -> None:
    repo.add(make("t_1"), owner="alice")
    repo.add(make("t_2"), owner="bob")
    assert [t.id for t in repo.list_for_owner("bob", before=None, limit=10)] == ["t_2"]


def test_idempotency_records(repo: TaskRepository) -> None:
    record = IdempotencyRecord(fingerprint="f", task_id="t_1", created_at=T0)
    assert repo.get_idempotency("alice", "k1") is None
    repo.put_idempotency("alice", "k1", record)
    assert repo.get_idempotency("alice", "k1") == record
    assert repo.get_idempotency("bob", "k1") is None  # scoped by owner
