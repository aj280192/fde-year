"""Part C: the /ask endpoint, end to end: our app on one port, the fake model on another."""

import asyncio
import json

import fake_upstream
import httpx
from fake_upstream import FAKE

Event = tuple[str, dict[str, object]]


def parse_sse(lines: list[str]) -> tuple[list[Event], int]:
    """Turn raw SSE lines into (event name, data) pairs, and count the heartbeats."""
    events: list[Event] = []
    pings = 0
    name = ""
    for line in lines:
        if line == ": ping":
            pings += 1
        elif line.startswith("event: "):
            name = line.removeprefix("event: ")
        elif line.startswith("data: "):
            events.append((name, json.loads(line.removeprefix("data: "))))
    return events, pings


def ask(
    app_url: str, question: str = "Why do pods restart?"
) -> tuple[list[Event], int]:
    with httpx.stream(
        "POST", f"{app_url}/ask", json={"question": question}, timeout=5.0
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        return parse_sse(list(response.iter_lines()))


def texts(events: list[Event]) -> list[str]:
    return [str(data["text"]) for name, data in events if name == "token"]


def assert_ends_once(events: list[Event], name: str) -> None:
    """The last event is `done` or `error`, and there is exactly one of either."""
    endings = [n for n, _ in events if n in ("done", "error")]
    assert endings == [name]
    assert events[-1][0] == name


def test_happy_path_streams_tokens_then_done(app_url: str) -> None:
    events, _ = ask(app_url)
    assert "".join(texts(events)) == fake_upstream.ANSWER
    assert_ends_once(events, "done")
    usage = events[-1][1]["usage"]
    assert isinstance(usage, dict)
    assert usage["completion_tokens"] == len(fake_upstream.ANSWER.split(" "))


def test_rate_limited_becomes_one_error_event(app_url: str) -> None:
    FAKE.mode = "rate_limited"
    events, _ = ask(app_url)
    assert texts(events) == []
    assert_ends_once(events, "error")
    assert events[-1][1]["code"] == "rate_limited"
    assert FAKE.requests == 3  # the client retried before giving up


def test_error_message_hides_internal_details(app_url: str) -> None:
    FAKE.mode = "server_error"
    events, _ = ask(app_url)
    message = str(events[-1][1]["message"])
    assert "127.0.0.1" not in message
    assert "httpx" not in message


def test_drop_sends_tokens_then_error(app_url: str) -> None:
    FAKE.mode = "drop"
    events, _ = ask(app_url)
    assert len(texts(events)) == 3
    assert_ends_once(events, "error")
    assert events[-1][1]["code"] == "upstream_dropped"


def test_hang_sends_heartbeats_then_timeout(app_url: str) -> None:
    FAKE.mode = "hang"
    events, pings = ask(app_url)
    assert len(texts(events)) == 1
    assert pings >= 1  # heartbeat 0.1 s, read timeout 0.3 s
    assert_ends_once(events, "error")
    assert events[-1][1]["code"] == "upstream_timeout"


def test_bad_request_is_rejected_before_calling_the_model(app_url: str) -> None:
    response = httpx.post(f"{app_url}/ask", json={"q": "x"}, timeout=5.0)
    assert response.status_code == 422
    assert FAKE.requests == 0


def test_browser_leaving_stops_the_model(app_url: str) -> None:
    async def run() -> int:
        tokens = 0
        async with (
            httpx.AsyncClient(timeout=5.0) as http,
            http.stream("POST", f"{app_url}/ask", json={"question": "hi"}) as response,
        ):
            async for line in response.aiter_lines():
                if line.startswith("event: token"):
                    tokens += 1
                if tokens == 3:
                    break  # leaving the `async with` closes the connection
        await asyncio.sleep(0.5)  # let the app cancel its producer and the fake notice
        return tokens

    assert asyncio.run(run()) == 3
    total_words = len(fake_upstream.ANSWER.split(" "))
    assert fake_upstream.last_stream["closed_early"] is True
    assert fake_upstream.last_stream["words_sent"] < total_words
