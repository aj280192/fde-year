from __future__ import annotations

import pytest
from metrics import mean, mrr_at_k, mrr_groups_at_k, recall_at_k, recall_groups_at_k


def test_mrr_first_hit_at_rank_2() -> None:
    assert mrr_at_k(["a", "b", "c"], {"b"}, 5) == 0.5


def test_mrr_first_hit_at_rank_1() -> None:
    assert mrr_at_k(["a", "b", "c"], {"a"}, 5) == 1.0


def test_mrr_uses_the_first_relevant_hit_only() -> None:
    assert mrr_at_k(["x", "a", "b"], {"a", "b"}, 5) == 0.5


def test_mrr_hit_outside_k_scores_zero() -> None:
    assert mrr_at_k(["a", "b", "c", "d", "e", "f"], {"f"}, 5) == 0.0


def test_recall_hit_outside_5_but_inside_20() -> None:
    retrieved = ["a", "b", "c", "d", "e", "f"]
    assert recall_at_k(retrieved, {"f"}, 5) == 0.0
    assert recall_at_k(retrieved, {"f"}, 20) == 1.0


def test_recall_all_found() -> None:
    assert recall_at_k(["a", "x", "b"], {"a", "b"}, 5) == 1.0


def test_recall_half_found() -> None:
    assert recall_at_k(["a", "x", "y"], {"a", "b"}, 5) == 0.5


def test_recall_counts_a_duplicate_hit_once() -> None:
    assert recall_at_k(["a", "a", "a"], {"a", "b"}, 5) == 0.5


def test_booklet_must_match_as_well_as_the_number() -> None:
    assert recall_at_k([(3, 140)], {(6, 140)}, 5) == 0.0
    assert mrr_at_k([(3, 140)], {(6, 140)}, 5) == 0.0


def test_nothing_retrieved() -> None:
    assert recall_at_k([], {"a"}, 5) == 0.0
    assert mrr_at_k([], {"a"}, 5) == 0.0


def test_empty_relevant_is_an_error() -> None:
    with pytest.raises(ValueError):
        recall_at_k(["a"], set(), 5)


def test_mean() -> None:
    assert mean([1.0, 0.0, 0.5]) == 0.5
    assert mean([]) == 0.0


def test_groups_of_one_match_the_plain_metrics() -> None:
    retrieved = ["a", "b", "c", "d", "e", "f"]
    groups = [[x] for x in retrieved]
    for relevant in ({"b"}, {"f"}, {"a", "e"}, {"z"}):
        for k in (5, 20):
            assert recall_groups_at_k(groups, relevant, k) == recall_at_k(
                retrieved, relevant, k
            )
            assert mrr_groups_at_k(groups, relevant, k) == mrr_at_k(
                retrieved, relevant, k
            )


def test_a_chunk_covering_two_paragraphs_counts_for_both() -> None:
    groups = [["x"], ["h", "p"]]  # chunk 2 covers a heading and its paragraph
    assert recall_groups_at_k(groups, {"h", "p"}, 5) == 1.0
    assert mrr_groups_at_k(groups, {"p"}, 5) == 0.5  # ranked by chunk, not by paragraph


def test_groups_are_cut_by_chunk_rank() -> None:
    groups = [["a"], ["b"], ["c"], ["d"], ["e"], ["f", "g"]]
    assert recall_groups_at_k(groups, {"g"}, 5) == 0.0
    assert recall_groups_at_k(groups, {"g"}, 20) == 1.0
    assert mrr_groups_at_k(groups, {"g"}, 5) == 0.0


def test_groups_empty_relevant_is_an_error() -> None:
    with pytest.raises(ValueError):
        recall_groups_at_k([["a"]], set(), 5)
