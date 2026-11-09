from __future__ import annotations

from itertools import pairwise

import pytest
from build_chunks import (
    LONG,
    Chunk,
    Paragraph,
    heading_meta,
    headings,
    headings_split,
    is_heading,
    split,
    split_text,
    whole,
)

# A made-up booklet with the shape described in the README: two headings, a table.
TABLE = " ".join(
    f"Row {i} lists a value and an action to take." for i in range(60)
)  # ~2,700 chars
BOOK = [
    Paragraph(6, 1, "Cholera"),
    Paragraph(6, 2, "Report every suspected case within 24 hours."),
    Paragraph(6, 3, "Give oral rehydration salts to all patients."),
    Paragraph(6, 4, "Measles"),
    Paragraph(6, 5, TABLE),
    Paragraph(2, 1, "Wash hands before and after seeing a patient."),
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Cholera", True),
        ("Standard case definition:", True),
        ("8.6.6 Update plans for improvements", True),
        ("Report every case within 24 hours.", False),  # ends with a full stop
        ("improve community participation;", False),  # mid-sentence and ends with ;
        ("", False),
        ("x" * 61, False),  # too long
    ],
)
def test_is_heading(text: str, expected: bool) -> None:
    assert is_heading(text) is expected


def test_split_text_short_text_is_one_piece() -> None:
    assert split_text("A short paragraph.") == ["A short paragraph."]


def test_split_text_pieces_are_bounded_overlap_and_cover_everything() -> None:
    pieces = split_text(TABLE)
    assert len(pieces) >= 3
    assert all(len(p) <= 800 for p in pieces)
    for a, b in pairwise(pieces):
        assert a[-40:].split()[-1] in b  # neighbours share text
    words = set(TABLE.split())
    assert words == set(" ".join(pieces).split())  # nothing lost


def test_split_text_never_cuts_a_word() -> None:
    words = set(TABLE.split())
    for piece in split_text(TABLE):
        assert piece.split()[0] in words and piece.split()[-1] in words


def test_whole_is_one_chunk_per_paragraph() -> None:
    chunks = whole(BOOK)
    assert [c.covers for c in chunks] == [(1,), (2,), (3,), (4,), (5,), (1,)]
    assert [c.text for c in chunks] == [p.text for p in BOOK]


def test_split_cuts_only_long_paragraphs_and_keeps_covers() -> None:
    chunks = split(BOOK)
    table_pieces = [c for c in chunks if c.covers == (5,)]
    assert len(table_pieces) >= 3
    assert [c.piece for c in table_pieces] == list(range(1, len(table_pieces) + 1))
    assert all(len(c.text) <= LONG for c in chunks)
    assert len([c for c in chunks if c.covers != (5,)]) == 5


def test_headings_prefixes_text_and_covers_the_heading() -> None:
    chunks = headings(BOOK)
    by_covers = {(c.booklet, c.covers): c.text for c in chunks}
    assert by_covers[(6, (1,))] == "Cholera"
    assert (
        by_covers[(6, (1, 2))]
        == "Cholera: Report every suspected case within 24 hours."
    )
    assert (
        by_covers[(6, (1, 3))]
        == "Cholera: Give oral rehydration salts to all patients."
    )
    assert by_covers[(6, (4, 5))].startswith("Measles: Row 0")


def test_headings_reset_at_a_new_booklet() -> None:
    chunks = headings(BOOK)
    booklet2 = [c for c in chunks if c.booklet == 2]
    assert booklet2 == [Chunk(2, (1,), "Wash hands before and after seeing a patient.")]


def test_headings_does_not_double_a_colon() -> None:
    chunks = headings(
        [Paragraph(1, 1, "Case definition:"), Paragraph(1, 2, "Fever and rash.")]
    )
    assert chunks[1].text == "Case definition: Fever and rash."


def test_headings_split_keeps_the_heading_in_every_piece_cover() -> None:
    pieces = [c for c in headings_split(BOOK) if c.covers == (4, 5)]
    assert len(pieces) >= 3
    assert pieces[0].text.startswith("Measles: ")


def test_heading_meta_keeps_text_and_stores_heading_separately() -> None:
    chunks = heading_meta(BOOK)
    assert [c.text for c in chunks] == [p.text for p in BOOK]
    assert [c.covers for c in chunks] == [(1,), (2,), (3,), (4,), (5,), (1,)]
    assert [c.heading for c in chunks] == [
        None,
        "Cholera",
        "Cholera",
        None,
        "Measles",
        None,
    ]
