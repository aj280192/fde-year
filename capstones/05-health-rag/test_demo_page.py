import httpx

from demo_page import error_message, is_retryable

REQ = httpx.Request("POST", "http://test/v1/ask")


def status_error(
    code: int, headers: dict[str, str] | None = None
) -> httpx.HTTPStatusError:
    resp = httpx.Response(code, headers=headers or {}, request=REQ)
    return httpx.HTTPStatusError(str(code), request=REQ, response=resp)


def test_429_says_how_long_to_wait() -> None:
    err = status_error(429, {"Retry-After": "5"})
    assert "5 seconds" in error_message(err)
    assert is_retryable(err)


def test_429_without_header_still_has_a_wait() -> None:
    assert "a few seconds" in error_message(status_error(429))


def test_api_down_is_retryable() -> None:
    err = httpx.ConnectError("refused", request=REQ)
    assert "isn't running" in error_message(err)
    assert is_retryable(err)


def test_bad_key_and_bad_question_are_not_retryable() -> None:
    for code in (401, 403, 422):
        assert not is_retryable(status_error(code))


def test_the_message_never_contains_the_raw_exception() -> None:
    err = httpx.ConnectError("secret-host.internal:8000 refused", request=REQ)
    assert "secret-host" not in error_message(err)
