from datetime import UTC, datetime, timedelta

from api.ask import AskResult, Citation, Source

# Raw test keys. Real keys come from auth.py's new_key(); simple strings are fine in tests.
KEYS = {"alice": "sk_test_alice", "bob": "sk_test_bob", "reader": "sk_test_reader"}


class FakeClock:
    """A clock the test controls, passed to create_app as `now`."""

    def __init__(self) -> None:
        self.current = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: float) -> None:
        self.current += timedelta(**kwargs)


def as_user(who: str) -> dict[str, str]:
    """Headers for a request made with that user's API key."""
    return {"X-API-Key": KEYS[who]}


SOURCES = [
    Source(id="B6:140", booklet=6, paragraph=140, score=0.91, text="Made-up text one."),
    Source(id="B2:40", booklet=2, paragraph=40, score=0.33, text="Made-up text two."),
]


async def answers(question: str) -> AskResult:
    return AskResult(
        text=f"Collect blood before antibiotics [B6:140]. ({question})",
        abstained=False,
        reason=None,
        citations=[Citation(id="B6:140", booklet=6, paragraph=140)],
        sources=SOURCES,
    )


async def abstains(question: str) -> AskResult:
    return AskResult(
        text="cannot find in sources",
        abstained=True,
        reason="low_retrieval_score",
        citations=[],
        sources=SOURCES,
    )


async def breaks(question: str) -> AskResult:
    raise RuntimeError("the model is down")
