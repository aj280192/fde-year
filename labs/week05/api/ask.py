"""POST /v1/ask: answer a question from the health booklets, as server-sent events.

The API doesn't know how answers are made. It depends on the `Answerer` contract
below; serve.py plugs in the real pipeline (capstones/05-health-rag/rag.py) and
the tests plug in a fake. Same idea as TaskRepository: the API stays independent
of the storage, and now of the answering pipeline too.

The answer is checked before any of it is sent (DESIGN.md section 14, row 19):
the whole answer is generated, the citation checks run, and only then are the
events sent. Slower to the first word, but unsupported text never reaches a user.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Citation:
    id: str  # "B6:154"
    booklet: int
    paragraph: int


@dataclass(frozen=True)
class AskResult:
    text: str
    abstained: bool
    reason: str | None  # why it abstained; None when it answered
    citations: list[Citation]


class Answerer(Protocol):
    async def __call__(self, question: str) -> AskResult: ...


def sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def ask_events(answerer: Answerer, question: str) -> AsyncIterator[str]:
    """answer + citations, or abstain; then done. Errors become an `error` event."""
    try:
        result = await answerer(question)
    except (
        Exception
    ):  # the stream has started: report in-band, not as a broken connection
        logger.exception("answering failed")
        yield sse_event(
            "error",
            {
                "code": "answer_failed",
                "message": "Couldn't produce an answer. Try again.",
            },
        )
        yield sse_event("done", {})
        return
    if result.abstained:
        yield sse_event("abstain", {"text": result.text, "reason": result.reason})
    else:
        yield sse_event("answer", {"text": result.text})
        yield sse_event(
            "citations",
            {
                "citations": [
                    {"id": c.id, "booklet": c.booklet, "paragraph": c.paragraph}
                    for c in result.citations
                ]
            },
        )
    yield sse_event("done", {})
