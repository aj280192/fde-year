"""Step 6: the task routes and API-key auth, end to end through FastAPI's TestClient."""

from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import pytest
from api import create_app
from auth import READ, WRITE, Principal, hash_key
from fastapi import FastAPI
from fastapi.testclient import TestClient
from models import Task, TaskState

# Raw test keys. Real keys come from auth.py's new_key(); simple strings are fine in tests.
KEYS = {"alice": "sk_test_alice", "bob": "sk_test_bob", "reader": "sk_test_reader"}


class FakeClock:
    """A clock the test controls, passed to create_app as `now`."""

    def __init__(self) -> None:
        self.current = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def app(clock: FakeClock) -> FastAPI:
    keys = {
        hash_key(KEYS["alice"]): Principal(
            key_id="alice", scopes=frozenset({READ, WRITE})
        ),
        hash_key(KEYS["bob"]): Principal(key_id="bob", scopes=frozenset({READ, WRITE})),
        hash_key(KEYS["reader"]): Principal(key_id="reader", scopes=frozenset({READ})),
    }
    return create_app(keys, now=clock.now)


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def as_user(who: str) -> dict[str, str]:
    """Headers for a request made with that user's API key."""
    return {"X-API-Key": KEYS[who]}


class JsonResponse(Protocol):
    """Anything with .json(). TestClient's response class differs between Starlette versions."""

    def json(self) -> Any: ...


def reason(response: JsonResponse) -> str:
    """The machine-readable reason from our error shape."""
    return response.json()["error"]["details"][0]["reason"]


def create(
    client: TestClient, who: str = "alice", text: str = "Diagnose crash-looping pods"
) -> str:
    """Create a task and return its id."""
    response = client.post("/v1/tasks", json={"input": text}, headers=as_user(who))
    assert response.status_code == 202
    return response.json()["id"]


# ---- Basics ----


def test_create_then_get(client: TestClient, clock: FakeClock) -> None:
    response = client.post(
        "/v1/tasks",
        json={"input": "Diagnose crash-looping pods"},
        headers=as_user("alice"),
    )
    assert response.status_code == 202
    created = response.json()
    assert created["state"] == "queued"
    assert created["id"].startswith("t_")
    assert created["result"] is None and created["error"] is None
    assert (
        created["created_at"]
        == created["updated_at"]
        == clock.now().isoformat().replace("+00:00", "Z")
    )

    fetched = client.get(f"/v1/tasks/{created['id']}", headers=as_user("alice"))
    assert fetched.status_code == 200
    assert fetched.json() == created


def test_get_unknown_task_is_404(client: TestClient) -> None:
    response = client.get("/v1/tasks/t_does_not_exist", headers=as_user("alice"))
    assert response.status_code == 404
    assert reason(response) == "TASK_NOT_FOUND"


def test_cancel_queued_task(client: TestClient, clock: FakeClock) -> None:
    task_id = create(client)
    clock.advance(seconds=5)
    response = client.post(f"/v1/tasks/{task_id}:cancel", headers=as_user("alice"))
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "cancelled"
    assert (
        body["updated_at"] != body["created_at"]
    )  # the change was timestamped with the fake clock
    # The change was saved, not just returned.
    assert (
        client.get(f"/v1/tasks/{task_id}", headers=as_user("alice")).json()["state"]
        == "cancelled"
    )


def test_cancel_twice_returns_the_same_task(
    client: TestClient, clock: FakeClock
) -> None:
    task_id = create(client)
    first = client.post(f"/v1/tasks/{task_id}:cancel", headers=as_user("alice"))
    clock.advance(seconds=5)
    second = client.post(f"/v1/tasks/{task_id}:cancel", headers=as_user("alice"))
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()  # identical, including updated_at


@pytest.mark.parametrize("finished", [TaskState.SUCCEEDED, TaskState.FAILED])
def test_cancel_finished_task_is_409(
    client: TestClient, app: FastAPI, finished: TaskState
) -> None:
    task_id = create(client)
    # No route can finish a task yet (there is no worker), so put one in the store directly.
    tasks: dict[str, Task] = app.state.tasks
    tasks[task_id] = tasks[task_id].model_copy(update={"state": finished})

    response = client.post(f"/v1/tasks/{task_id}:cancel", headers=as_user("alice"))
    assert response.status_code == 409
    assert reason(response) == "TASK_ALREADY_FINISHED"
    assert tasks[task_id].state is finished  # unchanged


def test_events_is_not_implemented_yet(client: TestClient) -> None:
    task_id = create(client)
    response = client.get(f"/v1/tasks/{task_id}/events", headers=as_user("alice"))
    assert response.status_code == 501
    assert reason(response) == "NOT_IMPLEMENTED"


def test_events_for_unknown_task_is_404_not_501(client: TestClient) -> None:
    response = client.get("/v1/tasks/t_nope/events", headers=as_user("alice"))
    assert response.status_code == 404


# ---- Authentication: who are you? ----


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/v1/tasks"),
        ("GET", "/v1/tasks/t_any"),
        ("POST", "/v1/tasks/t_any:cancel"),
        ("GET", "/v1/tasks/t_any/events"),
    ],
)
def test_no_key_is_401_on_every_route(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path, json={"input": "x"})
    assert response.status_code == 401
    assert reason(response) == "API_KEY_INVALID"


def test_wrong_key_is_401(client: TestClient) -> None:
    response = client.get("/v1/tasks/t_any", headers={"X-API-Key": "sk_not_a_real_key"})
    assert response.status_code == 401
    assert reason(response) == "API_KEY_INVALID"


# ---- Authorisation: what may you do? ----


def test_read_only_key_cannot_create(client: TestClient, app: FastAPI) -> None:
    response = client.post("/v1/tasks", json={"input": "x"}, headers=as_user("reader"))
    assert response.status_code == 403
    assert reason(response) == "INSUFFICIENT_PERMISSION"
    tasks: dict[str, Task] = app.state.tasks
    assert tasks == {}  # nothing was created


def test_read_only_key_cannot_cancel(client: TestClient) -> None:
    response = client.post("/v1/tasks/t_any:cancel", headers=as_user("reader"))
    assert response.status_code == 403


def test_read_only_key_can_read(client: TestClient) -> None:
    # The scope check passes, so the request reaches the route and gets an ordinary 404.
    response = client.get("/v1/tasks/t_any", headers=as_user("reader"))
    assert response.status_code == 404


# ---- Isolation: you only ever see your own tasks ----


def test_other_users_task_is_404_not_403(client: TestClient) -> None:
    task_id = create(client, who="alice")
    response = client.get(f"/v1/tasks/{task_id}", headers=as_user("bob"))
    assert response.status_code == 404  # never confirm that alice's task exists
    assert reason(response) == "TASK_NOT_FOUND"


def test_other_user_cannot_cancel(client: TestClient) -> None:
    task_id = create(client, who="alice")
    response = client.post(f"/v1/tasks/{task_id}:cancel", headers=as_user("bob"))
    assert response.status_code == 404
    still = client.get(f"/v1/tasks/{task_id}", headers=as_user("alice"))
    assert still.json()["state"] == "queued"


# ---- Validation: one error shape ----


def test_extra_field_is_rejected_in_our_shape(client: TestClient) -> None:
    response = client.post(
        "/v1/tasks", json={"input": "x", "state": "succeeded"}, headers=as_user("alice")
    )
    assert response.status_code == 422
    assert reason(response) == "INVALID_REQUEST_BODY"


@pytest.mark.parametrize(
    "body", [{}, {"input": ""}, {"input": "x" * 10_001}, {"input": 42}]
)
def test_bad_input_is_rejected(client: TestClient, body: dict[str, object]) -> None:
    response = client.post("/v1/tasks", json=body, headers=as_user("alice"))
    assert response.status_code == 422
    assert reason(response) == "INVALID_REQUEST_BODY"
    assert "x" * 100 not in response.text  # the submitted value is never echoed back
