"""The page-token helpers on their own, with no HTTP involved."""

from datetime import UTC, datetime

import pytest
from errors import ApiError
from pagination import decode_cursor, encode_cursor

WHEN = datetime(2026, 10, 30, 21, 15, 30, 123456, tzinfo=UTC)


def test_round_trip() -> None:
    assert decode_cursor(encode_cursor(WHEN, "t_abc")) == (WHEN, "t_abc")


def test_token_is_url_safe() -> None:
    token = encode_cursor(WHEN, "t_" + "?/+" * 10)
    assert not set(token) & set("+/ ")  # safe to put in a query string unescaped


def test_bad_token_raises_api_error_with_400() -> None:
    with pytest.raises(ApiError) as info:
        decode_cursor("garbage")
    assert info.value.http == 400
    assert info.value.reason == "INVALID_PAGE_TOKEN"
