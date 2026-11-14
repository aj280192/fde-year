"""POST /v1/ask, with fake answerers: no models, no database, no network."""

from __future__ import annotations

import json

from api.app import create_app
from api.ask import AskResult, Citation
from api.auth import READ, Principal, hash_key
from fastapi.testclient import TestClient

KEY = "sk_test_reader"
HEADERS = {"X-API-Key": KEY}
KEYS = {hash_key(KEY): Principal(key_id="reader", scopes=frozenset({READ}))}


async def answers(question: str) -> AskResult:
    return AskResult(
        text=f"Collect blood before antibiotics [B6:140]. ({question})",
        abstained=False,
        reason=None,
        citations=[Citation(id="B6:140", booklet=6, paragraph=140)],
    )


async def abstains(question: str) -> AskResult:
    return AskResult(
        text="cannot find in sources",
        abstained=True,
        reason="low_retrieval_score",
        citations=[],
    )


async def breaks(question: str) -> AskResult:
    raise RuntimeError("the model is down")


def events(body: str) -> list[tuple[str, dict[str, object]]]:
    """Parse an SSE body into (event, data) pairs."""
    out: list[tuple[str, dict[str, object]]] = []
    for block in body.strip().split("\n\n"):
        lines = dict(line.split(": ", 1) for line in block.splitlines())
        out.append((lines["event"], json.loads(lines["data"])))
    return out


def test_an_answer_streams_answer_then_citations_then_done() -> None:
    client = TestClient(create_app(KEYS, answerer=answers))
    res = client.post(
        "/v1/ask", json={"question": "anthrax specimens?"}, headers=HEADERS
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/event-stream")
    assert [e for e, _ in events(res.text)] == ["answer", "citations", "done"]
    assert events(res.text)[1][1] == {
        "citations": [{"id": "B6:140", "booklet": 6, "paragraph": 140}]
    }


def test_an_abstention_streams_abstain_then_done() -> None:
    client = TestClient(create_app(KEYS, answerer=abstains))
    res = client.post(
        "/v1/ask", json={"question": "capital of France?"}, headers=HEADERS
    )
    assert events(res.text) == [
        (
            "abstain",
            {"text": "cannot find in sources", "reason": "low_retrieval_score"},
        ),
        ("done", {}),
    ]


def test_a_failure_is_an_error_event_not_a_broken_stream() -> None:
    client = TestClient(create_app(KEYS, answerer=breaks))
    res = client.post("/v1/ask", json={"question": "anything"}, headers=HEADERS)
    assert [e for e, _ in events(res.text)] == ["error", "done"]


def test_without_an_answerer_it_is_501() -> None:
    res = TestClient(create_app(KEYS)).post(
        "/v1/ask", json={"question": "anything"}, headers=HEADERS
    )
    assert res.status_code == 501
    assert res.json()["error"]["details"][0]["reason"] == "NOT_IMPLEMENTED"


def test_it_needs_an_api_key() -> None:
    res = TestClient(create_app(KEYS, answerer=answers)).post(
        "/v1/ask", json={"question": "anything"}
    )
    assert res.status_code == 401


def test_an_empty_question_is_rejected() -> None:
    res = TestClient(create_app(KEYS, answerer=answers)).post(
        "/v1/ask", json={"question": ""}, headers=HEADERS
    )
    assert res.status_code == 422
