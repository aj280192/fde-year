"""Every error the task API can return, in one place, in one shape (AIP-193).

Each helper matches one row of DESIGN.md section 8b. Routes raise them; the handlers at the
bottom turn them, and FastAPI's own validation errors and unexpected bugs, into ErrorResponse.
"""

import logging

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from models import ErrorBody, ErrorDetail, ErrorResponse, TaskState

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """An error with a known HTTP code, status and reason. Routes raise it; a handler renders it."""

    def __init__(self, http: int, status: str, reason: str, message: str) -> None:
        super().__init__(message)
        self.http = http
        self.status = status
        self.reason = reason
        self.message = message


# ---- Raised by routes ----


def not_implemented(feature: str) -> ApiError:
    return ApiError(
        http=501,
        status="UNIMPLEMENTED",
        reason="NOT_IMPLEMENTED",
        message=f"{feature} is not implemented yet.",
    )


def task_not_found(task_id: str) -> ApiError:
    # Also used for another key's task, so the API never confirms that it exists.
    return ApiError(
        http=404,
        status="NOT_FOUND",
        reason="TASK_NOT_FOUND",
        message=f"Task '{task_id}' does not exist.",
    )


def task_already_finished(task_id: str, state: TaskState) -> ApiError:
    return ApiError(
        http=409,
        status="FAILED_PRECONDITION",
        reason="TASK_ALREADY_FINISHED",
        message=f"Task '{task_id}' is already {state.value} and can no longer be cancelled.",
    )


def invalid_page_token() -> ApiError:
    return ApiError(
        http=400,
        status="INVALID_ARGUMENT",
        reason="INVALID_PAGE_TOKEN",
        message="The page_token is not valid. Use the next_page_token from a previous response.",
    )


def api_key_invalid() -> ApiError:
    return ApiError(
        http=401,
        status="UNAUTHENTICATED",
        reason="API_KEY_INVALID",
        message="A valid API key is required in the X-API-Key header.",
    )


def insufficient_permission(scope: str) -> ApiError:
    return ApiError(
        http=403,
        status="PERMISSION_DENIED",
        reason="INSUFFICIENT_PERMISSION",
        message=f"This API key does not have the '{scope}' permission.",
    )


def idempotency_key_reused() -> ApiError:
    return ApiError(
        http=422,
        status="INVALID_ARGUMENT",
        reason="IDEMPOTENCY_KEY_REUSED",
        message="This Idempotency-Key was already used with a different request body.",
    )


# ---- Built from FastAPI's validation errors (see validation_error_handler) ----


def invalid_request_body(detail: str) -> ApiError:
    return ApiError(
        http=422,
        status="INVALID_ARGUMENT",
        reason="INVALID_REQUEST_BODY",
        message=f"The request body is not valid: {detail}",
    )


def invalid_query_parameter(detail: str) -> ApiError:
    return ApiError(
        http=422,
        status="INVALID_ARGUMENT",
        reason="INVALID_QUERY_PARAMETER",
        message=f"A query parameter is not valid: {detail}",
    )


def invalid_header(detail: str) -> ApiError:
    return ApiError(
        http=422,
        status="INVALID_ARGUMENT",
        reason="INVALID_HEADER",
        message=f"A request header is not valid: {detail}",
    )


# ---- Used only by the catch-all handler ----


def internal_error() -> ApiError:
    # A fixed message: nothing from the real exception may reach the client.
    return ApiError(
        http=500,
        status="INTERNAL",
        reason="INTERNAL_ERROR",
        message="Something went wrong on our side. Please try again later.",
    )


# ---- Rendering ----


def to_response(err: ApiError) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorBody(
            code=err.http,
            status=err.status,
            message=err.message,
            details=[ErrorDetail(reason=err.reason)],
        )
    )
    return JSONResponse(status_code=err.http, content=body.model_dump())


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    """Errors our own code raised."""
    return to_response(exc)


async def validation_error_handler(
    _: Request, exc: RequestValidationError
) -> JSONResponse:
    """FastAPI rejected the request before our route ran. Report the first problem only."""
    first = exc.errors()[0]
    location = first[
        "loc"
    ]  # e.g. ("body", "input"), ("query", "page_size"), ("header", "idempotency-key")
    where = str(location[0]) if location else "body"
    field = ".".join(str(part) for part in location[1:]) or where
    detail = f"{field}: {first['msg']}"  # never the submitted value: it could be 10,000 characters
    if where == "query":
        return to_response(invalid_query_parameter(detail))
    if where == "header":
        return to_response(invalid_header(detail))
    return to_response(invalid_request_body(detail))


async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
    """An unexpect bug. Full details go to the server log; the client gets a generic 500."""
    logger.exception("Unhandled error", exc_info=exc)
    return to_response(internal_error())
