from dataclasses import dataclass, field

from rag_adapter import to_ask_result


@dataclass
class S:
    id: str
    booklet: int
    paragraph: int
    score: float
    text: str = "made-up text"


@dataclass
class A:
    text: str = "answer"
    abstained: bool = False
    reason: str | None = None
    citations: list[S] = field(default_factory=list[S])
    sources: list[S] = field(default_factory=list[S])


def test_sources_come_back_best_first() -> None:
    low, high = S("B2:40", 2, 40, 0.3), S("B6:140", 6, 140, 0.9)
    result = to_ask_result(A(sources=[low, high]))  # out of order on purpose
    assert [s.id for s in result.sources] == ["B6:140", "B2:40"]


def test_citations_keep_their_order() -> None:
    a, b = S("B1:1", 1, 1, 0.5), S("B1:2", 1, 2, 0.9)
    result = to_ask_result(A(citations=[a, b]))
    assert [c.id for c in result.citations] == ["B1:1", "B1:2"]
