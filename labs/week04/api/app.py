"""The agent task API: thin routes that check who is calling, call a service, and shape the reply."""

from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime
from typing import Annotated

import services
from domain.errors import DomainError
from fastapi import Depends, FastAPI, Header, Query, Response, Security
from fastapi.exceptions import RequestValidationError
from fastapi.security import APIKeyHeader
from repository import InMemoryTaskRepository, TaskRepository

from api.auth import READ, WRITE, Principal, hash_key
from api.errors import (
    ApiError,
    api_error_handler,
    api_key_invalid,
    domain_error_handler,
    insufficient_permission,
    not_implemented,
    unhandled_error_handler,
    validation_error_handler,
)
from api.pagination import decode_cursor, encode_cursor
from api.schemas import CreateTaskRequest, ErrorResponse, ListTasksResponse, TaskOut


def utc_now() -> datetime:
    return datetime.now(UTC)


def err(*codes: int) -> dict[int | str, dict[str, object]]:
    """The `responses=` value for a route: shows ErrorResponse in /docs for each error code."""
    return {code: {"model": ErrorResponse} for code in codes}


def create_app(
    api_keys: Mapping[str, Principal],
    now: Callable[[], datetime] = utc_now,
    repo: TaskRepository | None = None,
) -> FastAPI:
    """Build the app. `api_keys` maps sha256(key) to its owner; `now` and `repo` are injectable.

    With no `repo`, each app gets its own empty in-memory repository, so every test starts clean.
    """
    store: TaskRepository = repo if repo is not None else InMemoryTaskRepository()

    app = FastAPI(title="Agent task API", version="0.1.0")

    # One error shape for everything (DESIGN.md section 8). This form passes pyright strict;
    # app.add_exception_handler(...) does not.
    app.exception_handler(ApiError)(api_error_handler)
    app.exception_handler(RequestValidationError)(validation_error_handler)
    app.exception_handler(Exception)(unhandled_error_handler)
    app.exception_handler(DomainError)(domain_error_handler)

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

    @app.post("/v1/tasks", status_code=202, responses=err(401, 403, 422))
    async def create_task(
        body: CreateTaskRequest,
        p: Annotated[Principal, Depends(require(WRITE))],
        response: Response,
        idempotency_key: Annotated[
            str | None, Header(min_length=1, max_length=255)
        ] = None,
    ) -> TaskOut:
        """Create a task. Returns at once with the task queued.

        Send an Idempotency-Key header to make retries safe: the same key and body within
        24 hours returns the first task instead of creating another.
        """
        created = services.create_task(
            store, p.key_id, body.input, idempotency_key, now()
        )
        if created.replayed:
            response.headers["Idempotent-Replayed"] = "true"
        return TaskOut.from_domain(created.task)

    @app.get("/v1/tasks/{task_id}", responses=err(401, 403, 404))
    async def get_task(
        task_id: str, p: Annotated[Principal, Depends(require(READ))]
    ) -> TaskOut:
        """Get one task."""
        return TaskOut.from_domain(services.get_task(store, p.key_id, task_id))

    @app.post("/v1/tasks/{task_id}:cancel", responses=err(401, 403, 404, 409))
    async def cancel_task(
        task_id: str, p: Annotated[Principal, Depends(require(WRITE))]
    ) -> TaskOut:
        """Cancel a task. Cancelling twice is safe."""
        return TaskOut.from_domain(
            services.cancel_task(store, p.key_id, task_id, now())
        )

    @app.get("/v1/tasks/{task_id}/events", responses=err(401, 403, 404, 501))
    async def task_events(
        task_id: str, p: Annotated[Principal, Depends(require(READ))]
    ) -> None:
        """Stream a task's events (not built until there is a worker)."""
        services.get_task(
            store, p.key_id, task_id
        )  # 404 first, so an unknown id isn't a 501
        raise not_implemented("The events stream")

    @app.get("/v1/tasks", responses=err(400, 401, 403, 422))
    async def list_tasks(
        p: Annotated[Principal, Depends(require(READ))],
        page_size: Annotated[int, Query(ge=1, le=100)] = 20,
        page_token: str = "",
    ) -> ListTasksResponse:
        """List my tasks, newest first."""
        after = decode_cursor(page_token) if page_token else None
        page = services.list_tasks(store, p.key_id, page_size, after)
        token = encode_cursor(page.next_cursor) if page.next_cursor is not None else ""

        return ListTasksResponse(
            tasks=[TaskOut.from_domain(t) for t in page.tasks], next_page_token=token
        )

    app.state.repo = store
    return app
