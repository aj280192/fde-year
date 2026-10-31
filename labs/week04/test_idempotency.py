"""The body fingerprint on its own, with no HTTP involved."""

from domain.idempotency import fingerprint


def make(text: str) -> str:
    return text


def test_same_body_same_fingerprint() -> None:
    assert fingerprint(make("Diagnose pods")) == fingerprint(make("Diagnose pods"))


def test_different_body_different_fingerprint() -> None:
    assert fingerprint(make("Diagnose pods")) != fingerprint(make("Diagnose nodes"))


def test_fingerprint_is_a_sha256_hex_string() -> None:
    value = fingerprint(make("x"))
    assert len(value) == 64
    assert set(value) <= set("0123456789abcdef")
