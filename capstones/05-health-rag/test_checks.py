"""The abstain rules (step 5): no model and no database needed."""

from __future__ import annotations

import pytest
from checks import Source, check_answer, check_retrieval


def source(id_: str = "B6:154", score: float = 5.0) -> Source:
    booklet, paragraph = id_.removeprefix("B").split("#")[0].split(":")
    return Source(id_, int(booklet), int(paragraph), "text", score)


# ---- after generation: check_answer ----


def test_a_valid_answer_is_kept() -> None:
    assert check_answer("Report within 24 hours [B6:154].", {"B6:154"}) == (
        None,
        ["B6:154"],
    )


def test_an_answer_without_citations_abstains() -> None:
    assert check_answer("Report within 24 hours.", {"B6:154"}) == ("no_citations", [])


def test_an_invented_id_abstains() -> None:
    reason, cited = check_answer("Report within 24 hours [B6:999].", {"B6:154"})
    assert reason == "unknown_citation"
    assert cited == ["B6:999"]


def test_one_invented_id_among_valid_ones_still_abstains() -> None:
    reason, _ = check_answer("A [B6:154]. B [B6:999].", {"B6:154"})
    assert reason == "unknown_citation"


@pytest.mark.parametrize(
    "text",
    ["cannot find in sources", "Cannot find in sources.", "  CANNOT FIND IN SOURCES\n"],
)
def test_the_model_abstaining_is_recognised(text: str) -> None:
    assert check_answer(text, {"B6:154"}) == ("model_abstained", [])


def test_citations_are_unique_and_in_order_of_first_mention() -> None:
    text = "a [B3:2]. b [B1:5]. c [B3:2][B1:5]."
    assert check_answer(text, {"B3:2", "B1:5"}) == (None, ["B3:2", "B1:5"])


def test_a_second_piece_of_a_paragraph_is_a_valid_id() -> None:
    assert check_answer("From the table [B6:154#2].", {"B6:154", "B6:154#2"}) == (
        None,
        ["B6:154#2"],
    )


@pytest.mark.parametrize(
    "text", ["see (B6:154)", "see B6:154", "see [6:154]", "see [B6-154]"]
)
def test_malformed_citations_do_not_count(text: str) -> None:
    assert check_answer(text, {"B6:154"}) == ("no_citations", [])


# ---- before generation: check_retrieval ----


def test_no_sources_abstains() -> None:
    assert check_retrieval([], threshold=0.0) == "no_sources"


def test_a_low_top_score_abstains() -> None:
    assert check_retrieval([source(score=-3.0)], threshold=0.0) == "low_retrieval_score"


def test_a_score_equal_to_the_threshold_answers() -> None:
    assert check_retrieval([source(score=0.0)], threshold=0.0) is None


def test_only_the_top_score_matters() -> None:
    sources = [source("B6:154", score=4.0), source("B3:22", score=-8.0)]
    assert check_retrieval(sources, threshold=0.0) is None
