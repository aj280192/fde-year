"""The agent task API. Step 4: the frame (stores, error handlers, auth). Routes come in step 5."""

import secrets
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Annotated

from auth import READ, WRITE, Principal, hash_key
from errors import (
    ApiError,
    api_error_handler,
    api_key_invalid,
    insufficient_permission,
    not_implemented,
    task_already_finished,
    task_not_found,
    unhandled_error_handler,
    validation_error_handler,
)
from fastapi import Depends, FastAPI, Security
from fastapi.exceptions import RequestValidationError
from fastapi.security import APIKeyHeader
from models import (
    TERMINAL,
    CreateTaskRequest,
    ErrorResponse,
    Task,
    TaskState,
    can_transition,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def err(*codes: int) -> dict[int | str, dict[str, object]]:
    """The `responses=` value for a route: shows ErrorResponse in /docs for each error code."""
    return {code: {"model": ErrorResponse} for code in codes}


def create_app(
    api_keys: Mapping[str, Principal], now: Callable[[], datetime] = utc_now
) -> FastAPI:
    """Build the app. `api_keys` maps sha256(key) to its owner; `now` is injectable for tests."""
    # In-memory stores, one set per app, so every test starts empty. Saturday moves them
    # behind a repository.
    tasks: dict[str, Task] = {}
    owners: dict[
        str, str
    ] = {}  # task id -> key_id; kept out of Task so it never appears in a response

    app = FastAPI(title="Agent task API", version="0.1.0")

    # One error shape for everything (DESIGN.md section 8). This form passes pyright strict;
    # app.add_exception_handler(...) does not.
    app.exception_handler(ApiError)(api_error_handler)
    app.exception_handler(RequestValidationError)(validation_error_handler)
    app.exception_handler(Exception)(unhandled_error_handler)

    # auto_error=False: a missing header arrives as None, so we can answer 401 in our own shape.
    key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

    async def principal(raw: Annotated[str | None, Security(key_header)]) -> Principal:
        """Who is calling? 401 if the key is missing or unknown."""
        if raw is None:
            raise api_key_invalid()
        found = api_keys.get(hash_key(raw))
        if found is None:
            raise api_key_invalid()
        return found

    def require(scope: str) -> Callable[[Principal], Awaitable[Principal]]:
        """A dependency that lets the request through only if the key has `scope` (else 403)."""

        async def check(p: Annotated[Principal, Depends(principal)]) -> Principal:
            if scope not in p.scopes:
                raise insufficient_permission(scope)
            return p

        return check

    def owned(task_id: str, p: Principal) -> Task:
        """The caller's task, or 404. Another key's task is also 404, so its existence never leaks."""
        task = tasks.get(task_id)
        if task is None or owners.get(task_id) != p.key_id:
            raise task_not_found(task_id)
        return task

    # ---- Routes go here in step 5: create, get, cancel, events (and list in step 7). ----
    @app.post("/v1/tasks", status_code=202, responses=err(401, 403, 422))
    async def Create(
        body: CreateTaskRequest, p: Annotated[Principal, Depends(require(WRITE))]
    ) -> Task:
        stamp = now()

        task = Task(
            id="t_" + secrets.token_urlsafe(16),
            state=TaskState.QUEUED,
            input=body.input,
            created_at=stamp,
            updated_at=stamp,
        )

        tasks[task.id] = task
        owners[task.id] = p.key_id

        return task

    @app.get("/v1/tasks/{task_id}", responses=err(401, 403, 404))
    async def Get(
        task_id: str, p: Annotated[Principal, Depends(require(READ))]
    ) -> Task:
        return owned(task_id, p)

    @app.post("/v1/tasks/{task_id}:cancel", responses=err(401, 403, 404, 409))
    async def Cancel(
        task_id: str, p: Annotated[Principal, Depends(require(WRITE))]
    ) -> Task:
        task = owned(task_id, p)

        if task.state == TaskState.CANCELLED:
            return task

        if task.state in TERMINAL or not can_transition(
            task.state, TaskState.CANCELLED
        ):
            raise task_already_finished(task_id, task.state)

        updated = task.model_copy(
            update={"state": TaskState.CANCELLED, "updated_at": now()}
        )
        tasks[task_id] = updated
        return updated

    @app.get("/v1/tasks/{task_id}/events", responses=err(401, 403, 404, 501))
    async def Events(
        task_id: str, p: Annotated[Principal, Depends(require(READ))]
    ) -> None:
        owned(task_id, p)
        raise not_implemented("The events stream")

    app.state.tasks = tasks  # lets tests put a task in a state no route can reach yet
    app.state.owners = owners
    return app
