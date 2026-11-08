from __future__ import annotations

from pathlib import Path

import pytest
from build_testset import (
    Record,
    load_rows,
    normalise,
    parse_booklet,
    parse_label,
    split,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("140", {140}),
        ("154, 166", {154, 166}),
        ("1, 2, 3", {1, 2, 3}),
        ("439-440", {439, 440}),
        ("439 - 440", {439, 440}),
        ("10-12, 20-21", {10, 11, 12, 20, 21}),
        ("12, 14-16", {12, 14, 15, 16}),
        (" 140 ", {140}),
        ("140.0", {140}),
        ("5-5", {5}),
    ],
)
def test_parse_label(text: str, expected: set[int]) -> None:
    assert parse_label(text) == expected


@pytest.mark.parametrize("text", ["", "   ", "12-10", "abc", "1,,2", "1-2-3"])
def test_parse_label_rejects(text: str) -> None:
    with pytest.raises(ValueError):
        parse_label(text)


def test_parse_booklet() -> None:
    assert parse_booklet("TG Booklet 6") == 6
    assert parse_booklet("TG Booklet 12 ") == 12
    with pytest.raises(ValueError):
        parse_booklet("TG Booklet")


def test_normalise() -> None:
    assert normalise("  What IS   anthrax? ") == "what is anthrax?"


def _rec(i: int, question: str) -> Record:
    return {"id": f"q{i}", "question": question, "booklet": 1, "relevant": [i]}


def test_split_keeps_copies_together() -> None:
    rows = [_rec(i, f"question {i}") for i in range(40)]
    rows += [
        _rec(100, "Question 7"),
        _rec(101, "  question   7 "),
    ]  # copies of question 7
    heldout, tuning = split(rows, n_heldout=10, seed=1)
    in_heldout = {normalise(r["question"]) for r in heldout}
    in_tuning = {normalise(r["question"]) for r in tuning}
    assert not in_heldout & in_tuning
    assert len(heldout) == 10
    assert len(heldout) + len(tuning) == len(rows)


def test_split_is_repeatable() -> None:
    rows = [_rec(i, f"question {i}") for i in range(40)]
    assert split(rows, n_heldout=10, seed=42) == split(rows, n_heldout=10, seed=42)
    assert split(rows, n_heldout=10, seed=42) != split(rows, n_heldout=10, seed=7)


HEADER = (
    "ID,Question Text,Question Answer,Reference Document,Paragraph(s) Number,Keywords\n"
)


def test_load_rows_skips_only_empty_labels(tmp_path: Path) -> None:
    csv_file = tmp_path / "Train.csv"
    csv_file.write_text(
        "﻿"
        + HEADER  # the BOM Excel adds
        + 'a,Q one,A,TG Booklet 6,"139-140",k\n'
        + "b,Q two,A,TG Booklet 2,,k\n",
        encoding="utf-8",
    )
    rows, skipped = load_rows(csv_file)
    assert skipped == 1
    assert rows == [
        {"id": "a", "question": "Q one", "booklet": 6, "relevant": [139, 140]}
    ]


def test_load_rows_raises_on_a_bad_label(tmp_path: Path) -> None:
    csv_file = tmp_path / "Train.csv"
    csv_file.write_text(HEADER + "a,Q,A,TG Booklet 6,see table,k\n", encoding="utf-8")
    with pytest.raises(ValueError, match="line 2"):
        load_rows(csv_file)


def test_load_rows_applies_a_known_label_fix(tmp_path: Path) -> None:
    csv_file = tmp_path / "Train.csv"
    csv_file.write_text(HEADER + "Q893,Q,A,TG Booklet 6,203204,k\n", encoding="utf-8")
    rows, _ = load_rows(csv_file)
    assert rows[0]["relevant"] == [203, 204]


def test_load_rows_refuses_a_stale_label_fix(tmp_path: Path) -> None:
    csv_file = tmp_path / "Train.csv"
    csv_file.write_text(HEADER + "Q893,Q,A,TG Booklet 6,203,k\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected label"):
        load_rows(csv_file)
