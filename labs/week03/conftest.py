"""Shared fixtures: one real fake server per test session, reset before every test."""

import threading
import time
from collections.abc import Iterator

import fake_upstream
import pytest
import uvicorn
from app import create_app
from client import LLMClient

PORT = 8765


@pytest.fixture(scope="session")
def base_url() -> Iterator[str]:
    """Run the fake upstream on a real port, so streaming and disconnects behave as in production."""
    server = uvicorn.Server(
        uvicorn.Config(
            fake_upstream.app,
            host="127.0.0.1",
            port=PORT,
            log_level="warning",
            timeout_graceful_shutdown=1,  # don't wait out the 60 s "hang" requests
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{PORT}/v1"
    server.should_exit = True
    thread.join()


@pytest.fixture(autouse=True)
def reset_fake() -> None:
    """Every test starts in "ok" mode with the request counter at zero."""
    fake_upstream.FAKE.mode = "ok"
    fake_upstream.FAKE.requests = 0


APP_PORT = 8766


@pytest.fixture(scope="session")
def app_url(base_url: str) -> Iterator[str]:
    """Run our /ask app on a real port, talking to the fake upstream with fast retry settings."""
    client = LLMClient(
        base_url,
        model="fake",
        max_attempts=3,
        base_delay=0.01,
        max_delay=0.05,
        total_budget=2.0,
        read_timeout=0.3,
    )
    server = uvicorn.Server(
        uvicorn.Config(
            create_app(client, heartbeat_seconds=0.1),
            host="127.0.0.1",
            port=APP_PORT,
            log_level="warning",
            timeout_graceful_shutdown=1,
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    while not server.started:
        time.sleep(0.01)
    yield f"http://127.0.0.1:{APP_PORT}"
    server.should_exit = True
    thread.join()
