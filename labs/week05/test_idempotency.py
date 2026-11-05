"""The idempotency fingerprint on its own."""

from domain.idempotency import fingerprint


def test_same_input_same_fingerprint() -> None:
    assert fingerprint("Diagnose pods") == fingerprint("Diagnose pods")


def test_different_input_different_fingerprint() -> None:
    assert fingerprint("Diagnose pods") != fingerprint("Diagnose nodes")


def test_fingerprint_is_a_sha256_hex_string() -> None:
    value = fingerprint("x")
    assert len(value) == 64
    assert set(value) <= set("0123456789abcdef")
