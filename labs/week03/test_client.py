"""Thursday's client tests, plus Part B: retries, backoff caps and the no-retry-after-text rule."""

import asyncio
import time

import fake_upstream
import httpx
import pytest
from client import LLMClient, TextDelta, Usage, classify
from errors import (
    RateLimitedError,
    UpstreamDroppedError,
    UpstreamError,
    UpstreamTimeoutError,
)
from fake_upstream import FAKE


def fast_client(base_url: str) -> LLMClient:
    """Tiny delays and timeouts, so retry tests take milliseconds, not seconds."""
    return LLMClient(
        base_url,
        model="fake",
        max_attempts=3,
        base_delay=0.01,
        max_delay=0.05,
        total_budget=2.0,
        read_timeout=0.3,
    )


def run_complete(base_url: str) -> str:
    async def run() -> str:
        async with fast_client(base_url) as client:
            return await client.complete("hi")

    return asyncio.run(run())


def run_stream(base_url: str, pieces: list[str]) -> None:
    """Append each piece to `pieces`, so a test can count them even after an error."""

    async def run() -> None:
        async with fast_client(base_url) as client:
            async for item in client.stream("hi"):
                if isinstance(item, TextDelta):
                    pieces.append(item.text)

    asyncio.run(run())


# ---- Thursday ----


def test_complete_returns_the_whole_answer(base_url: str) -> None:
    async def run() -> str:
        async with LLMClient(base_url, model="fake") as client:
            return await client.complete("Why do pods restart?")

    assert asyncio.run(run()) == fake_upstream.ANSWER


def test_stream_yields_pieces_in_order(base_url: str) -> None:
    pieces: list[str] = []
    run_stream(base_url, pieces)
    assert len(pieces) == len(fake_upstream.ANSWER.split(" "))
    assert "".join(pieces) == fake_upstream.ANSWER


def test_cancelling_a_stream_closes_the_connection(base_url: str) -> None:
    async def run() -> list[str]:
        received: list[str] = []

        async def consume() -> None:
            async with LLMClient(base_url, model="fake") as client:
                async for item in client.stream("Why do pods restart?"):
                    if isinstance(item, TextDelta):
                        received.append(item.text)

        task = asyncio.create_task(consume())
        while len(received) < 3:
            await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        await asyncio.sleep(0.3)  # give the server time to notice the disconnect
        return received

    received = asyncio.run(run())
    total_words = len(fake_upstream.ANSWER.split(" "))
    assert fake_upstream.last_stream["closed_early"] is True
    assert fake_upstream.last_stream["words_sent"] < total_words
    assert len(received) < total_words


def test_stream_ends_with_usage(base_url: str) -> None:
    async def run() -> list[TextDelta | Usage]:
        async with fast_client(base_url) as client:
            return [item async for item in client.stream("hi")]

    items = asyncio.run(run())
    last = items[-1]
    assert isinstance(last, Usage)
    assert last.completion_tokens == len(fake_upstream.ANSWER.split(" "))


# ---- Part B: classify, as a plain unit test (no server) ----


def status_error(code: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "http://x")
    response = httpx.Response(code, request=request)
    return httpx.HTTPStatusError("x", request=request, response=response)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (status_error(429), RateLimitedError),
        (status_error(503), UpstreamError),
        (status_error(501), None),
        (status_error(400), None),
        (status_error(401), None),
        (httpx.ReadTimeout("x"), UpstreamTimeoutError),
        (httpx.ConnectError("x"), UpstreamError),
        (httpx.RemoteProtocolError("x"), UpstreamError),
    ],
)
def test_classify(exc: httpx.HTTPError, expected: type[UpstreamError] | None) -> None:
    assert classify(exc) is expected


# ---- Part B: complete() retries ----


def test_retry_recovers_after_two_429s(base_url: str) -> None:
    FAKE.mode = "rate_limited_twice"
    assert run_complete(base_url) == fake_upstream.ANSWER
    assert FAKE.requests == 3


def test_gives_up_on_repeated_429(base_url: str) -> None:
    FAKE.mode = "rate_limited"
    with pytest.raises(RateLimitedError) as info:
        run_complete(base_url)
    assert info.value.code == "rate_limited"
    assert isinstance(info.value.__cause__, httpx.HTTPStatusError)  # raised `from exc`
    assert FAKE.requests == 3


def test_retry_after_is_capped_at_max_delay(base_url: str) -> None:
    # The fake says "Retry-After: 1". Uncapped, two waits would take 2 s.
    FAKE.mode = "rate_limited"
    start = time.monotonic()
    with pytest.raises(RateLimitedError):
        run_complete(base_url)
    assert time.monotonic() - start < 1.0


def test_server_error_retries_then_fails(base_url: str) -> None:
    FAKE.mode = "server_error"
    with pytest.raises(UpstreamError) as info:
        run_complete(base_url)
    assert type(info.value) is UpstreamError  # not a subclass
    assert FAKE.requests == 3


def test_hang_before_anything_arrives_retries(base_url: str) -> None:
    FAKE.mode = "hang"
    with pytest.raises(UpstreamTimeoutError):
        run_complete(base_url)
    assert FAKE.requests == 3


# ---- Part B: stream() never retries once text has gone out ----


def test_stream_retries_before_first_piece(base_url: str) -> None:
    FAKE.mode = "rate_limited_twice"
    pieces: list[str] = []
    run_stream(base_url, pieces)
    assert "".join(pieces) == fake_upstream.ANSWER  # no repeated words
    assert FAKE.requests == 3


def test_stream_hang_after_first_piece(base_url: str) -> None:
    FAKE.mode = "hang"
    pieces: list[str] = []
    with pytest.raises(UpstreamTimeoutError):
        run_stream(base_url, pieces)
    assert len(pieces) == 1
    assert FAKE.requests == 1


def test_stream_drop_mid_answer(base_url: str) -> None:
    FAKE.mode = "drop"
    pieces: list[str] = []
    with pytest.raises(UpstreamDroppedError):
        run_stream(base_url, pieces)
    assert len(pieces) == 3
    assert FAKE.requests == 1
