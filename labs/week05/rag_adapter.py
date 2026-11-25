"""Convert the health RAG's Answer into the API's AskResult."""

from collections.abc import Sequence
from typing import Protocol

from api.ask import AskResult, Citation, Source


class RagSource(Protocol):
    @property
    def id(self) -> str: ...
    @property
    def booklet(self) -> int: ...
    @property
    def paragraph(self) -> int: ...
    @property
    def score(self) -> float: ...
    @property
    def text(self) -> str: ...


class RagAnswer(Protocol):
    @property
    def text(self) -> str: ...
    @property
    def abstained(self) -> bool: ...
    @property
    def reason(self) -> str | None: ...
    @property
    def citations(self) -> Sequence[RagSource]: ...
    @property
    def sources(self) -> Sequence[RagSource]: ...


def to_ask_result(a: RagAnswer) -> AskResult:
    ranked = sorted(a.sources, key=lambda s: s.score, reverse=True)
    return AskResult(
        text=a.text,
        abstained=a.abstained,
        reason=a.reason,
        citations=[Citation(c.id, c.booklet, c.paragraph) for c in a.citations],
        sources=[Source(s.id, s.booklet, s.paragraph, s.score, s.text) for s in ranked],
    )
