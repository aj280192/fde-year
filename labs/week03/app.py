"""POST /ask: stream a model's answer to the browser as server-sent events.

Events, in order:
    event: token   data: {"text": "..."}          one per piece of answer
    : ping                                         heartbeat while the model is thinking
    event: done    data: {"usage": {...} | null}   the answer finished
    event: error   data: {"code": "...", "message": "..."}   the answer failed

Every stream ends with exactly one `done` or one `error`.
"""

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator, AsyncIterator
from contextlib import asynccontextmanager

import anyio
from client import LLMClient, TextDelta, Usage
from errors import UpstreamError
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

SSE_PING = ": ping\n\n"

# What the browser is told. Never send str(err): it holds internal URLs and httpx details.
MESSAGES = {
    "rate_limited": "The model is busy. Try again shortly.",
    "upstream_timeout": "The model took too long to answer.",
    "upstream_dropped": "The answer was cut off. Try again.",
    "upstream_error": "The model is unavailable right now.",
}

# What the producer puts in the queue. None marks the end.
Item = TextDelta | Usage | UpstreamError | None


class AskRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    question: str


def sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def error_event(err: UpstreamError) -> str:
    message = MESSAGES.get(err.code, MESSAGES["upstream_error"])
    return sse_event("error", {"code": err.code, "message": message})


async def produce(client: LLMClient, question: str, queue: asyncio.Queue[Item]) -> None:
    """Read the model's stream into the queue. Errors become queue items, not crashes."""
    try:
        async for item in client.stream(question):
            await queue.put(item)
    except UpstreamError as err:
        await queue.put(err)
    finally:
        await queue.put(None)


async def event_stream(
    request: Request, client: LLMClient, question: str, heartbeat_seconds: float
) -> AsyncIterator[str]:
    queue: asyncio.Queue[Item] = asyncio.Queue()
    producer = asyncio.create_task(produce(client, question, queue))
    usage: Usage | None = None
    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                # Safe to time out: only the wait on the queue is cancelled, never the stream.
                item = await asyncio.wait_for(queue.get(), heartbeat_seconds)
            except TimeoutError:
                yield SSE_PING
                continue
            if isinstance(item, TextDelta):
                yield sse_event("token", {"text": item.text})
            elif isinstance(item, Usage):
                usage = item  # sent with `done`, once the answer is complete
            elif isinstance(item, UpstreamError):
                yield error_event(item)
                break
            else:
                yield sse_event(
                    "done", {"usage": usage.model_dump() if usage else None}
                )
                break
    finally:
        # Runs on finish, error and disconnect: stop reading from the model.
        # On disconnect Starlette cancels this request through anyio and keeps re-cancelling,
        # which would interrupt httpx while it closes the upstream connection. The shield
        # lets the clean-up finish, so the model really stops generating.
        with anyio.CancelScope(shield=True):
            producer.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await producer


def create_app(client: LLMClient, heartbeat_seconds: float = 15.0) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
        yield
        await client.aclose()  # close the shared connection pool once, at shutdown

    app = FastAPI(lifespan=lifespan)

    @app.post("/ask")
    async def ask(body: AskRequest, request: Request) -> StreamingResponse:
        return StreamingResponse(
            event_stream(request, client, body.question, heartbeat_seconds),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache"},
        )

    return app
