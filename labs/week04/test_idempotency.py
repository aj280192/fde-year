"""The body fingerprint on its own, with no HTTP involved."""

from idempotency import fingerprint
from models import CreateTaskRequest


def make(text: str) -> CreateTaskRequest:
    return CreateTaskRequest.model_validate({"input": text})


def test_same_body_same_fingerprint() -> None:
    assert fingerprint(make("Diagnose pods")) == fingerprint(make("Diagnose pods"))


def test_different_body_different_fingerprint() -> None:
    assert fingerprint(make("Diagnose pods")) != fingerprint(make("Diagnose nodes"))


def test_spacing_in_the_raw_json_does_not_matter() -> None:
    compact = CreateTaskRequest.model_validate_json('{"input":"x"}')
    spaced = CreateTaskRequest.model_validate_json('{ "input" :  "x" }')
    assert fingerprint(compact) == fingerprint(spaced)


def test_fingerprint_is_a_sha256_hex_string() -> None:
    value = fingerprint(make("x"))
    assert len(value) == 64
    assert set(value) <= set("0123456789abcdef")
