"""An async client for any OpenAI-compatible chat endpoint, with retries and a concurrency limit."""

import asyncio
import random
import time
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Self

import httpx
from errors import (
    RateLimitedError,
    UpstreamDroppedError,
    UpstreamError,
    UpstreamTimeoutError,
)
from pydantic import BaseModel, ConfigDict

# Providers add fields over time, so responses ignore unknown fields rather than reject them.
LENIENT = ConfigDict(extra="ignore")

# Server errors worth retrying. 501 (not implemented) and 505 will never succeed, so they are left out.
RETRYABLE_STATUS = {500, 502, 503, 504}


class Message(BaseModel):
    model_config = LENIENT
    content: str


class Choice(BaseModel):
    model_config = LENIENT
    message: Message


class Completion(BaseModel):
    model_config = LENIENT
    choices: list[Choice]


class Delta(BaseModel):
    model_config = LENIENT
    content: str | None = None


class ChunkChoice(BaseModel):
    model_config = LENIENT
    delta: Delta


class Usage(BaseModel):
    """Token counts for one answer. The server sends them in the last chunk."""

    model_config = LENIENT
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class TextDelta(BaseModel):
    """One piece of answer text, as stream() hands it to the caller."""

    text: str


class Chunk(BaseModel):
    model_config = LENIENT
    choices: list[ChunkChoice]
    usage: Usage | None = None


def classify(exc: httpx.HTTPError) -> type[UpstreamError] | None:
    """Return the error to raise if retries run out, or None when retrying cannot help."""
    if isinstance(exc, httpx.HTTPStatusError):
        status_code = exc.response.status_code
        if status_code == 429:
            return RateLimitedError
        if status_code in RETRYABLE_STATUS:
            return UpstreamError
        return None
    if isinstance(exc, httpx.TimeoutException):
        return UpstreamTimeoutError
    if isinstance(exc, (httpx.ConnectError, httpx.RemoteProtocolError)):
        return UpstreamError
    return None


class LLMClient:
    def __init__(
        self,
        base_url: str,
        model: str,
        api_key: str = "not-needed",
        max_attempts: int = 4,
        base_delay: float = 0.5,
        max_delay: float = 8.0,
        total_budget: float = 30.0,
        read_timeout: float = 30.0,
        max_in_flight: int = 10,
    ) -> None:
        self.model = model
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.total_budget = total_budget
        self._limit = asyncio.Semaphore(max_in_flight)
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(connect=5.0, read=read_timeout, write=10.0, pool=5.0),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Close the connection pool. Call once, when the app shuts down."""
        await self._http.aclose()

    def _body(self, prompt: str, *, stream: bool) -> dict[str, object]:
        body: dict[str, object] = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }
        if stream:
            # OpenAI and Ollama only send the final usage chunk when asked.
            body["stream_options"] = {"include_usage": True}
        return body

    def _backoff(self, attempt: int) -> float:
        """Full jitter: a random wait between 0 and a ceiling that doubles each attempt."""
        ceiling = min(self.max_delay, self.base_delay * 2**attempt)
        return random.uniform(0, ceiling)

    def _retry_after(self, response: httpx.Response) -> float | None:
        """Seconds the server asked us to wait, capped at max_delay, or None."""
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            seconds = float(value)
        except ValueError:
            return None  # an HTTP date rather than seconds: fall back to backoff
        return min(seconds, self.max_delay)

    async def _wait_or_give_up(
        self, exc: httpx.HTTPError, attempt: int, deadline: float
    ) -> None:
        """Sleep before the next attempt, or raise if this failure should not be retried."""
        error_class = classify(exc)
        if error_class is None:
            raise UpstreamError(f"upstream rejected the request: {exc}") from exc
        wait = self._backoff(attempt)
        if isinstance(exc, httpx.HTTPStatusError):
            server_wait = self._retry_after(exc.response)
            if server_wait is not None:
                wait = server_wait
        if attempt == self.max_attempts - 1 or time.monotonic() + wait > deadline:
            raise error_class(f"gave up after {attempt + 1} attempts: {exc}") from exc
        await asyncio.sleep(wait)  # no semaphore slot held while waiting

    async def complete(self, prompt: str) -> str:
        deadline = time.monotonic() + self.total_budget
        body = self._body(prompt, stream=False)
        for attempt in range(self.max_attempts):
            try:
                async with self._limit:
                    response = await self._http.post("/chat/completions", json=body)
                response.raise_for_status()
                return (
                    Completion.model_validate_json(response.content)
                    .choices[0]
                    .message.content
                )
            except httpx.HTTPError as exc:
                await self._wait_or_give_up(exc, attempt, deadline)
        raise AssertionError("unreachable")

    async def stream(self, prompt: str) -> AsyncIterator[TextDelta | Usage]:
        deadline = time.monotonic() + self.total_budget
        body = self._body(prompt, stream=True)
        for attempt in range(self.max_attempts):
            yielded = False
            try:
                async with (
                    self._limit,
                    self._http.stream(
                        "POST", "/chat/completions", json=body
                    ) as response,
                ):
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue  # blank lines and comments separate events
                        data = line.removeprefix("data: ")
                        if data == "[DONE]":
                            return
                        chunk = Chunk.model_validate_json(data)
                        if chunk.choices and chunk.choices[0].delta.content:
                            yield TextDelta(text=chunk.choices[0].delta.content)
                            yielded = True
                        if chunk.usage is not None:
                            yield chunk.usage
                raise UpstreamDroppedError("stream ended without [DONE]")
            except httpx.HTTPError as exc:
                if yielded:
                    # Text already reached the caller: a retry would repeat it, so never retry.
                    if isinstance(exc, httpx.TimeoutException):
                        raise UpstreamTimeoutError("stream stalled mid-answer") from exc
                    raise UpstreamDroppedError("stream cut mid-answer") from exc
                await self._wait_or_give_up(exc, attempt, deadline)
        raise AssertionError("unreachable")
