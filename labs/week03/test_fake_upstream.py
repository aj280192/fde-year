"""Part A: the fake server's failure modes, checked with plain httpx (no retries, no client)."""

import fake_upstream
import httpx
import pytest
from fake_upstream import FAKE

BODY = {"model": "fake", "messages": [{"role": "user", "content": "hi"}]}
STREAM_BODY = {**BODY, "stream": True}


def post(base_url: str, timeout: float = 5.0) -> httpx.Response:
    return httpx.post(f"{base_url}/chat/completions", json=BODY, timeout=timeout)


def read_stream(base_url: str, lines: list[str], read_timeout: float = 5.0) -> None:
    """Append every SSE data line to `lines`, so a test can count them even after an error."""
    timeout = httpx.Timeout(5.0, read=read_timeout)
    with httpx.stream(
        "POST", f"{base_url}/chat/completions", json=STREAM_BODY, timeout=timeout
    ) as response:
        for line in response.iter_lines():
            if line.startswith("data: "):
                lines.append(line)


def test_ok_mode_answers(base_url: str) -> None:
    response = post(base_url)
    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == fake_upstream.ANSWER
    assert FAKE.requests == 1


def test_server_error_returns_503(base_url: str) -> None:
    FAKE.mode = "server_error"
    assert post(base_url).status_code == 503


def test_rate_limited_returns_429_with_retry_after(base_url: str) -> None:
    FAKE.mode = "rate_limited"
    response = post(base_url)
    assert response.status_code == 429
    assert response.headers["retry-after"] == "1"


def test_rate_limited_twice_then_succeeds(base_url: str) -> None:
    FAKE.mode = "rate_limited_twice"
    codes = [post(base_url).status_code for _ in range(3)]
    assert codes == [429, 429, 200]
    assert FAKE.requests == 3


def test_hang_complete_times_out(base_url: str) -> None:
    FAKE.mode = "hang"
    with pytest.raises(httpx.ReadTimeout):
        post(base_url, timeout=0.3)


def test_stream_ok_ends_with_usage_and_done(base_url: str) -> None:
    lines: list[str] = []
    read_stream(base_url, lines)
    assert lines[-1] == "data: [DONE]"
    assert '"completion_tokens"' in lines[-2]  # catches the old "competion" typo
    assert FAKE.requests == 1


def test_stream_hang_sends_one_word_then_stalls(base_url: str) -> None:
    FAKE.mode = "hang"
    lines: list[str] = []
    with pytest.raises(httpx.ReadTimeout):
        read_stream(base_url, lines, read_timeout=0.3)
    assert len(lines) == 1


def test_stream_drop_cuts_after_three_words(base_url: str) -> None:
    FAKE.mode = "drop"
    lines: list[str] = []
    with pytest.raises(httpx.RemoteProtocolError):
        read_stream(base_url, lines)
    assert len(lines) == 3
