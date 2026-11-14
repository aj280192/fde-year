"""Tests for the abstain rule: no model, no database, no network.

The rule lives in two pure functions in rag.py:
- check_retrieval runs BEFORE the model: abstain when retrieval found nothing good enough
- check_answer runs AFTER the model: abstain when the answer isn't backed by the sources
Each returns a reason (a short string) to abstain, or None to carry on.
"""

from __future__ import annotations

import pytest
from config import ABSTAIN_TEXT
from rag import Source, check_answer, check_retrieval


def source(id_: str, score: float) -> Source:
    """A retrieved source with only the fields the checks look at filled in meaningfully."""
    booklet, rest = id_.removeprefix("B").split(":")
    paragraph = int(rest.split("#")[0])
    return Source(
        id=id_, booklet=int(booklet), paragraph=paragraph, text="…", score=score
    )


ALLOWED = {"B6:154", "B6:155", "B3:22", "B6:154#2"}


# ---------------------------------------------------------------- before the model


def test_no_sources_abstains() -> None:
    assert check_retrieval([], threshold=0.0) == "no_sources"


def test_best_score_below_threshold_abstains() -> None:
    sources = [source("B6:154", -3.2), source("B3:22", -5.0)]
    assert check_retrieval(sources, threshold=0.0) == "low_retrieval_score"


def test_only_the_best_score_matters() -> None:
    # Sources come best first: one strong source is enough, even if the rest are weak.
    sources = [source("B6:154", 4.1), source("B3:22", -7.0)]
    assert check_retrieval(sources, threshold=0.0) is None


def test_score_exactly_at_threshold_answers() -> None:
    # "Below the threshold" abstains; equal to it does not.
    assert check_retrieval([source("B6:154", 1.5)], threshold=1.5) is None


# ---------------------------------------------------------------- after the model


def test_answer_citing_retrieved_sources_is_kept() -> None:
    reason, cited = check_answer(
        "Report every suspected case within 24 hours [B6:154].", ALLOWED
    )
    assert reason is None
    assert cited == ["B6:154"]


def test_several_citations_in_one_bracket_run() -> None:
    reason, cited = check_answer(
        "Collect blood before antibiotics [B6:154][B3:22].", ALLOWED
    )
    assert reason is None
    assert cited == ["B6:154", "B3:22"]


def test_cited_ids_are_unique_and_in_order_of_first_mention() -> None:
    text = "First [B3:22]. Then [B6:155]. Again [B3:22]."
    assert check_answer(text, ALLOWED) == (None, ["B3:22", "B6:155"])


def test_a_split_piece_id_is_accepted() -> None:
    assert check_answer("From the second piece [B6:154#2].", ALLOWED) == (
        None,
        ["B6:154#2"],
    )


def test_answer_without_citations_abstains() -> None:
    reason, cited = check_answer(
        "Report every suspected case within 24 hours.", ALLOWED
    )
    assert reason == "no_citations"
    assert cited == []


def test_invented_citation_abstains() -> None:
    reason, cited = check_answer(
        "Report within 24 hours [B6:154]. Isolate the patient [B6:999].", ALLOWED
    )
    assert reason == "unknown_citation"
    assert cited == [
        "B6:154",
        "B6:999",
    ]  # kept, so --trace can show which id was invented


def test_one_invented_citation_is_enough_to_abstain() -> None:
    # Nine good citations don't excuse one made-up one.
    text = " ".join(["Fact [B6:154]."] * 9 + ["Made up [B1:1]."])
    assert check_answer(text, ALLOWED)[0] == "unknown_citation"


@pytest.mark.parametrize(
    "text",
    [
        ABSTAIN_TEXT,
        "Cannot find in sources.",
        "  cannot find in sources  ",
        "CANNOT FIND IN SOURCES",
    ],
)
def test_model_abstaining_is_recognised(text: str) -> None:
    assert check_answer(text, ALLOWED) == ("model_abstained", [])


@pytest.mark.parametrize(
    "text",
    [
        "Report within 24 hours [b6:154].",  # lower-case b
        "Report within 24 hours (B6:154).",  # round brackets
        "Report within 24 hours [B6 154].",  # no colon
        "Report within 24 hours [Booklet 6, para 154].",  # free text
    ],
)
def test_malformed_citations_do_not_count(text: str) -> None:
    # Anything not in the exact [B<booklet>:<paragraph>] form is not a citation, so the answer has none.
    assert check_answer(text, ALLOWED)[0] == "no_citations"
