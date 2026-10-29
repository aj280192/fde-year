"""The task state machine (DESIGN.md section 6) and the request and task models."""

from datetime import UTC, datetime
from itertools import product

import pytest
from models import ALLOWED, TERMINAL, CreateTaskRequest, Task, TaskState, can_transition
from pydantic import ValidationError

S = TaskState

# DESIGN.md table 6c, written out by hand: the 10 legal moves. The tests compare the code with this.
LEGAL: set[tuple[TaskState, TaskState]] = {
    (S.QUEUED, S.RUNNING),
    (S.QUEUED, S.FAILED),
    (S.QUEUED, S.CANCELLED),
    (S.RUNNING, S.WAITING_FOR_INPUT),
    (S.RUNNING, S.SUCCEEDED),
    (S.RUNNING, S.FAILED),
    (S.RUNNING, S.CANCELLED),
    (S.WAITING_FOR_INPUT, S.RUNNING),
    (S.WAITING_FOR_INPUT, S.FAILED),
    (S.WAITING_FOR_INPUT, S.CANCELLED),
}
ALL_PAIRS = list(product(TaskState, repeat=2))  # all 36 (from, to) pairs
ILLEGAL = [pair for pair in ALL_PAIRS if pair not in LEGAL]  # the other 26


# ---- The state machine ----


def test_every_state_has_rules() -> None:
    assert set(ALLOWED) == set(
        TaskState
    )  # a forgotten state would raise KeyError later


def test_there_are_exactly_ten_legal_moves() -> None:
    assert sum(len(targets) for targets in ALLOWED.values()) == len(LEGAL) == 10


@pytest.mark.parametrize(("old", "new"), sorted(LEGAL))
def test_legal_moves_are_allowed(old: TaskState, new: TaskState) -> None:
    assert can_transition(old, new)


@pytest.mark.parametrize(("old", "new"), ILLEGAL)
def test_illegal_moves_are_refused(old: TaskState, new: TaskState) -> None:
    assert not can_transition(old, new)


def test_terminal_states_are_the_three_final_ones() -> None:
    assert TERMINAL == {S.SUCCEEDED, S.FAILED, S.CANCELLED}


@pytest.mark.parametrize("state", sorted(TERMINAL))
def test_nothing_leaves_a_terminal_state(state: TaskState) -> None:
    assert ALLOWED[state] == frozenset()


@pytest.mark.parametrize("state", list(TaskState))
def test_no_state_moves_to_itself(state: TaskState) -> None:
    assert not can_transition(state, state)


def test_every_non_terminal_state_can_be_cancelled() -> None:
    for state in set(TaskState) - TERMINAL:
        assert can_transition(state, S.CANCELLED)


def test_success_always_comes_from_running() -> None:
    sources = {old for old in TaskState if can_transition(old, S.SUCCEEDED)}
    assert sources == {
        S.RUNNING
    }  # no queued -> succeeded, no waiting_for_input -> succeeded


def test_states_serialise_as_lowercase_strings() -> None:
    assert [state.value for state in TaskState] == [
        "queued",
        "running",
        "waiting_for_input",
        "succeeded",
        "failed",
        "cancelled",
    ]


# ---- CreateTaskRequest: the client may set `input` and nothing else ----


def test_valid_request() -> None:
    assert (
        CreateTaskRequest.model_validate({"input": "Diagnose pods"}).input
        == "Diagnose pods"
    )


@pytest.mark.parametrize(
    ("body", "error_type"),
    [
        ({"input": "x", "state": "succeeded"}, "extra_forbidden"),
        ({"input": "x", "id": "t_mine"}, "extra_forbidden"),
        ({}, "missing"),
        ({"input": ""}, "string_too_short"),
        ({"input": "x" * 10_001}, "string_too_long"),
        ({"input": 42}, "string_type"),  # strict: no silent conversion of 42 to "42"
    ],
)
def test_invalid_requests_are_rejected(
    body: dict[str, object], error_type: str
) -> None:
    with pytest.raises(ValidationError) as info:
        CreateTaskRequest.model_validate(body)
    assert info.value.errors()[0]["type"] == error_type


def test_longest_allowed_input() -> None:
    assert (
        len(CreateTaskRequest.model_validate({"input": "x" * 10_000}).input) == 10_000
    )


# ---- Task ----


def make_task() -> Task:
    stamp = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)
    return Task(id="t_1", state=S.QUEUED, input="x", created_at=stamp, updated_at=stamp)


def test_task_is_frozen() -> None:
    task = make_task()
    with pytest.raises(ValidationError):
        task.state = S.CANCELLED  # pydantic refuses this at runtime


def test_model_copy_makes_a_new_task_and_keeps_the_old_one() -> None:
    task = make_task()
    cancelled = task.model_copy(update={"state": S.CANCELLED})
    assert cancelled.state is S.CANCELLED
    assert task.state is S.QUEUED


def test_new_task_has_no_result_and_no_error() -> None:
    task = make_task()
    assert task.result is None
    assert task.error is None
