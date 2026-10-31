"""Step 6: the task routes and API-key auth, end to end through FastAPI's TestClient."""

from collections.abc import Mapping
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

import pytest
from api.app import create_app
from api.auth import READ, WRITE, Principal, hash_key
from domain.task import TaskState
from fastapi import FastAPI
from fastapi.testclient import TestClient
from repository import TaskRepository

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


class TaskResponse(JsonResponse, Protocol):
    """A response we also read status and headers from."""

    @property
    def status_code(self) -> int: ...

    @property
    def headers(self) -> Mapping[str, str]: ...


def stored(app: FastAPI, owner: str = "alice") -> int:
    """How many tasks the owner has in the app's repository."""
    repo: TaskRepository = app.state.repo
    return len(repo.list_for_owner(owner, before=None, limit=1000))


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
    repo: TaskRepository = app.state.repo
    task = repo.get(task_id, "alice")
    assert task is not None
    repo.save(replace(task, state=finished))

    response = client.post(f"/v1/tasks/{task_id}:cancel", headers=as_user("alice"))
    assert response.status_code == 409
    assert reason(response) == "TASK_ALREADY_FINISHED"
    unchanged = repo.get(task_id, "alice")
    assert unchanged is not None and unchanged.state is finished


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
    assert stored(app, "reader") == 0  # nothing was created


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


# ---- Pagination ----


def all_pages(
    client: TestClient, who: str, page_size: int
) -> tuple[list[str], list[int]]:
    """Follow next_page_token to the end. Returns every id seen, and the size of each page."""
    ids: list[str] = []
    sizes: list[int] = []
    token = ""
    while True:
        params: dict[str, str | int] = {"page_size": page_size, "page_token": token}
        response = client.get("/v1/tasks", params=params, headers=as_user(who))
        assert response.status_code == 200
        body = response.json()
        ids += [task["id"] for task in body["tasks"]]
        sizes.append(len(body["tasks"]))
        token = body["next_page_token"]
        if not token:
            return ids, sizes


def create_many(
    client: TestClient, clock: FakeClock, n: int, who: str = "alice"
) -> list[str]:
    """Create n tasks one second apart, oldest first."""
    ids: list[str] = []
    for i in range(n):
        ids.append(create(client, who=who, text=f"task {i}"))
        clock.advance(seconds=1)
    return ids


def test_pages_have_the_right_sizes(client: TestClient, clock: FakeClock) -> None:
    create_many(client, clock, 5)
    _, sizes = all_pages(client, "alice", page_size=2)
    assert sizes == [2, 2, 1]


def test_pages_are_newest_first_and_complete(
    client: TestClient, clock: FakeClock
) -> None:
    created = create_many(client, clock, 5)
    seen, _ = all_pages(client, "alice", page_size=2)
    assert seen == list(reversed(created))  # every task, once, newest first


def test_exact_multiple_of_page_size_has_no_empty_last_page(
    client: TestClient, clock: FakeClock
) -> None:
    create_many(client, clock, 4)
    _, sizes = all_pages(client, "alice", page_size=2)
    assert sizes == [2, 2]  # page_size + 1 means we know page 2 is the last


def test_default_page_size_is_20(client: TestClient, clock: FakeClock) -> None:
    create_many(client, clock, 25)
    body = client.get("/v1/tasks", headers=as_user("alice")).json()
    assert len(body["tasks"]) == 20
    assert body["next_page_token"] != ""


def test_tasks_with_the_same_timestamp_are_not_lost(
    client: TestClient, clock: FakeClock
) -> None:
    # Two tasks share a created_at; only the id tie-breaker keeps them apart.
    same_time = [create(client, text="a"), create(client, text="b")]
    clock.advance(seconds=1)
    later = create_many(client, clock, 3)
    seen, _ = all_pages(client, "alice", page_size=2)
    assert sorted(seen) == sorted(same_time + later)
    assert len(seen) == len(set(seen)) == 5  # no task twice


def test_new_task_while_paging_causes_no_duplicates_or_skips(
    client: TestClient, clock: FakeClock
) -> None:
    original = create_many(client, clock, 5)
    first = client.get(
        "/v1/tasks", params={"page_size": 2}, headers=as_user("alice")
    ).json()
    create(client, text="arrives while the user is paging")  # newer than everything

    seen = [task["id"] for task in first["tasks"]]
    token = first["next_page_token"]
    while token:
        params: dict[str, str | int] = {"page_size": 2, "page_token": token}
        body = client.get("/v1/tasks", params=params, headers=as_user("alice")).json()
        seen += [task["id"] for task in body["tasks"]]
        token = body["next_page_token"]
    assert seen == list(
        reversed(original)
    )  # page numbers would have shown one task twice


def test_empty_list(client: TestClient) -> None:
    body = client.get("/v1/tasks", headers=as_user("alice")).json()
    assert body == {"tasks": [], "next_page_token": ""}


def test_list_shows_only_my_tasks(client: TestClient, clock: FakeClock) -> None:
    create_many(client, clock, 3, who="alice")
    mine = create_many(client, clock, 2, who="bob")
    seen, _ = all_pages(client, "bob", page_size=10)
    assert sorted(seen) == sorted(mine)


def test_read_only_key_can_list(client: TestClient) -> None:
    assert client.get("/v1/tasks", headers=as_user("reader")).status_code == 200


@pytest.mark.parametrize(
    "token",
    [
        "garbage",  # not base64
        "bm90IGpzb24=",  # base64 of "not json"
        "eyJ4IjogMX0=",  # base64 of {"x": 1}: missing keys
        "eyJ0IjogIm5vdCBhIGRhdGUiLCAiaWQiOiAidF8xIn0=",  # "t" is not a date
        "eyJ0IjogIjIwMjYtMTAtMjlUMTI6MDA6MDAiLCAiaWQiOiAidF8xIn0=",  # a date with no timezone
    ],
)
def test_bad_page_token_is_400(client: TestClient, token: str) -> None:
    response = client.get(
        "/v1/tasks", params={"page_token": token}, headers=as_user("alice")
    )
    assert response.status_code == 400
    assert reason(response) == "INVALID_PAGE_TOKEN"


@pytest.mark.parametrize("size", [0, -1, 101])
def test_page_size_out_of_range_is_422(client: TestClient, size: int) -> None:
    response = client.get(
        "/v1/tasks", params={"page_size": size}, headers=as_user("alice")
    )
    assert response.status_code == 422
    assert reason(response) == "INVALID_QUERY_PARAMETER"


# ---- Idempotency ----


def with_key(who: str, key: str) -> dict[str, str]:
    """Headers for a create that carries an Idempotency-Key."""
    return {**as_user(who), "Idempotency-Key": key}


def post_task(
    client: TestClient, headers: dict[str, str], text: str = "Diagnose pods"
) -> TaskResponse:
    return client.post("/v1/tasks", json={"input": text}, headers=headers)


def test_same_key_same_body_returns_the_first_task(
    client: TestClient, app: FastAPI
) -> None:
    first = post_task(client, with_key("alice", "retry-1"))
    second = post_task(client, with_key("alice", "retry-1"))
    assert first.status_code == second.status_code == 202
    assert second.json() == first.json()
    assert second.headers["Idempotent-Replayed"] == "true"
    assert "Idempotent-Replayed" not in first.headers
    assert stored(app) == 1  # the retry created nothing


def test_same_key_different_body_is_rejected(client: TestClient, app: FastAPI) -> None:
    post_task(client, with_key("alice", "retry-1"), text="Diagnose pods")
    response = post_task(client, with_key("alice", "retry-1"), text="Delete everything")
    assert response.status_code == 422
    assert reason(response) == "IDEMPOTENCY_KEY_REUSED"
    assert stored(app) == 1


def test_same_key_from_two_clients_makes_two_tasks(client: TestClient) -> None:
    alice = post_task(client, with_key("alice", "retry-1")).json()
    bob = post_task(client, with_key("bob", "retry-1")).json()
    assert (
        alice["id"] != bob["id"]
    )  # keys are scoped per API key: no collision, no leak


def test_different_keys_make_different_tasks(client: TestClient) -> None:
    a = post_task(client, with_key("alice", "retry-1")).json()
    b = post_task(client, with_key("alice", "retry-2")).json()
    assert a["id"] != b["id"]


def test_no_key_means_no_protection(client: TestClient, app: FastAPI) -> None:
    post_task(client, as_user("alice"))
    post_task(client, as_user("alice"))
    assert stored(app) == 2


def test_key_still_works_at_exactly_24_hours(
    client: TestClient, clock: FakeClock
) -> None:
    first = post_task(client, with_key("alice", "retry-1")).json()
    clock.advance(hours=24)
    again = post_task(client, with_key("alice", "retry-1")).json()
    assert again["id"] == first["id"]  # the boundary is inclusive: <= TTL


def test_key_expires_after_24_hours(client: TestClient, clock: FakeClock) -> None:
    first = post_task(client, with_key("alice", "retry-1")).json()
    clock.advance(hours=24, seconds=1)
    later = post_task(client, with_key("alice", "retry-1")).json()
    assert later["id"] != first["id"]
    # The new task replaces the old record, so a retry now returns the new one.
    retry = post_task(client, with_key("alice", "retry-1")).json()
    assert retry["id"] == later["id"]


def test_expired_key_can_be_reused_with_a_different_body(
    client: TestClient, clock: FakeClock
) -> None:
    post_task(client, with_key("alice", "retry-1"), text="first job")
    clock.advance(hours=25)
    response = post_task(client, with_key("alice", "retry-1"), text="a different job")
    assert response.status_code == 202


def test_replay_returns_the_task_as_it_is_now(client: TestClient) -> None:
    task_id = post_task(client, with_key("alice", "retry-1")).json()["id"]
    client.post(f"/v1/tasks/{task_id}:cancel", headers=as_user("alice"))
    replay = post_task(client, with_key("alice", "retry-1")).json()
    assert replay["id"] == task_id
    assert (
        replay["state"] == "cancelled"
    )  # our documented choice (DESIGN.md section 11)


def test_read_only_key_with_idempotency_key_is_still_403(client: TestClient) -> None:
    response = post_task(client, with_key("reader", "retry-1"))
    assert response.status_code == 403


@pytest.mark.parametrize("key", ["", "k" * 256])
def test_bad_idempotency_key_is_422(client: TestClient, app: FastAPI, key: str) -> None:
    response = post_task(client, with_key("alice", key))
    assert response.status_code == 422
    assert reason(response) == "INVALID_HEADER"
    assert stored(app) == 0


def test_longest_allowed_idempotency_key(client: TestClient) -> None:
    assert post_task(client, with_key("alice", "k" * 255)).status_code == 202
