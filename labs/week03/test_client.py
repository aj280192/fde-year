import asyncio
import threading
import time
from collections.abc import Iterator

import fake_upstream
import pytest
import uvicorn
from client import LLMClient

PORT = 8765


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    """Run the fake upstream on a real port, so streaming and disconnects behave as in production."""
    server = uvicorn.Server(
        uvicorn.Config(
            fake_upstream.app, host="127.0.0.1", port=PORT, log_level="warning"
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{PORT}/v1"
    server.should_exit = True
    thread.join()


def test_complete_returns_the_whole_answer(base_url: str) -> None:
    async def run() -> str:
        async with LLMClient(base_url, model="fake") as client:
            return await client.complete("Why do pods restart?")

    assert asyncio.run(run()) == fake_upstream.ANSWER


def test_stream_yields_pieces_in_order(base_url: str) -> None:
    async def run() -> list[str]:
        async with LLMClient(base_url, model="fake") as client:
            return [piece async for piece in client.stream("Why do pods restart?")]

    pieces = asyncio.run(run())
    assert len(pieces) == len(fake_upstream.ANSWER.split(" "))
    assert "".join(pieces) == fake_upstream.ANSWER


def test_cancelling_a_stream_closes_the_connection(base_url: str) -> None:
    async def run() -> list[str]:
        received: list[str] = []

        async def consume() -> None:
            async with LLMClient(base_url, model="fake") as client:
                async for piece in client.stream("Why do pods restart?"):
                    received.append(piece)

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
    assert fake_upstream.last_stream["words_sent"] == len(received)
