"""Build one chunking strategy's rows in the `chunks` table from `paragraphs`.

Usage (from capstones/05-health-rag):
    uv run python build_chunks.py --strategy whole
    uv run python build_chunks.py --strategy split

Strategies:
    whole           one chunk per paragraph, unchanged (must reproduce the paragraph runs)
    split           paragraphs over 1,000 characters cut into ~800-character overlapping pieces
    headings        each paragraph prefixed with the heading above it; covers the heading too
    headings_split  headings, then any chunk over 1,000 characters split
    heading_meta    like whole, with the nearest heading stored in its own column (for keyword weighting)

Every chunk records `covers`: the paragraphs it counts as finding when it's retrieved.
Re-running a strategy replaces only that strategy's rows.
"""

from __future__ import annotations

import argparse
import os
import statistics
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import psycopg

LONG = 1_000  # split anything longer than this
SIZE = 800  # target piece size
OVERLAP = 100  # characters shared by neighbouring pieces
HEADING_MAX = 60  # a heading is at most this long


@dataclass(frozen=True)
class Paragraph:
    booklet: int
    para_no: int
    text: str


@dataclass(frozen=True)
class Chunk:
    booklet: int
    covers: tuple[int, ...]
    text: str
    piece: int = 1
    heading: str | None = None


# ---------------------------------------------------------------- pure rules


def is_heading(text: str) -> bool:
    """Short, no sentence-ending punctuation, and not starting mid-sentence."""
    t = text.strip()
    return 0 < len(t) <= HEADING_MAX and t[-1] not in ".;," and not t[0].islower()


def split_text(text: str, size: int = SIZE, overlap: int = OVERLAP) -> list[str]:
    """Pieces of at most `size` characters, neighbours sharing about `overlap`.

    Each cut moves back to the last ". " (or else the last space) in the second
    half of the window, so pieces end at a sentence or a word, never mid-word.
    """
    text = text.strip()
    if len(text) <= size:
        return [text]

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        if end < len(text):
            window_mid = start + size // 2
            cut = text.rfind(". ", window_mid, end)
            if cut != -1:
                end = cut + 1  # keep the full stop
            else:
                space = text.rfind(" ", window_mid, end)
                if space != -1:
                    end = space
        pieces.append(text[start:end].strip())
        if end >= len(text):
            break
        next_start = max(end - overlap, start + 1)
        space = text.find(" ", next_start, end)  # start the next piece on a word
        start = space + 1 if space != -1 else next_start
    return [p for p in pieces if p]


def split_long(chunks: Iterable[Chunk]) -> list[Chunk]:
    """Split any chunk over LONG characters; every piece keeps the chunk's covers."""
    out: list[Chunk] = []
    for c in chunks:
        if len(c.text) <= LONG:
            out.append(c)
            continue
        for i, piece in enumerate(split_text(c.text), start=1):
            out.append(Chunk(c.booklet, c.covers, piece, piece=i, heading=c.heading))
    return out


# ---------------------------------------------------------------- strategies


def whole(paragraphs: list[Paragraph]) -> list[Chunk]:
    return [Chunk(p.booklet, (p.para_no,), p.text) for p in paragraphs]


def split(paragraphs: list[Paragraph]) -> list[Chunk]:
    return split_long(whole(paragraphs))


def _walk_headings(
    paragraphs: list[Paragraph],
) -> Iterable[tuple[Paragraph, Paragraph | None]]:
    """Yield (paragraph, the heading above it), or (heading, None) for a heading itself."""
    current: Paragraph | None = None
    booklet: int | None = None
    for p in paragraphs:
        if p.booklet != booklet:  # a new booklet: forget the last one's heading
            booklet, current = p.booklet, None
        if is_heading(p.text):
            current = p
            yield p, None
        else:
            yield p, current


def headings(paragraphs: list[Paragraph]) -> list[Chunk]:
    out: list[Chunk] = []
    for p, h in _walk_headings(paragraphs):
        if h is None:
            out.append(Chunk(p.booklet, (p.para_no,), p.text))
        else:
            title = h.text.strip().rstrip(":")
            out.append(Chunk(p.booklet, (h.para_no, p.para_no), f"{title}: {p.text}"))
    return out


def headings_split(paragraphs: list[Paragraph]) -> list[Chunk]:
    return split_long(headings(paragraphs))


def heading_meta(paragraphs: list[Paragraph]) -> list[Chunk]:
    return [
        Chunk(
            p.booklet,
            (p.para_no,),
            p.text,
            heading=h.text.strip().rstrip(":") if h else None,
        )
        for p, h in _walk_headings(paragraphs)
    ]


STRATEGIES: dict[str, Callable[[list[Paragraph]], list[Chunk]]] = {
    "whole": whole,
    "split": split,
    "headings": headings,
    "headings_split": headings_split,
    "heading_meta": heading_meta,
}

# ---------------------------------------------------------------- database

READ = """
    SELECT booklet, para_no, text FROM paragraphs
    WHERE text <> '' ORDER BY booklet, para_no
"""
DELETE = "DELETE FROM chunks WHERE strategy = %s"
INSERT = """
    INSERT INTO chunks (strategy, booklet, covers, piece, heading, text)
    VALUES (%s, %s, %s, %s, %s, %s)
"""


def read_paragraphs(conn: psycopg.Connection[Any]) -> list[Paragraph]:
    return [Paragraph(int(b), int(n), str(t)) for b, n, t in conn.execute(READ)]


def write_chunks(
    conn: psycopg.Connection[Any], strategy: str, chunks: list[Chunk]
) -> None:
    """Replace this strategy's rows, all or nothing."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(DELETE, (strategy,))
        cur.executemany(
            INSERT,
            [
                (strategy, c.booklet, list(c.covers), c.piece, c.heading, c.text)
                for c in chunks
            ],
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--strategy", required=True, choices=sorted(STRATEGIES))
    args = parser.parse_args()

    with psycopg.connect(os.environ["HEALTH_RAG_DATABASE_URL"]) as conn:
        paragraphs = read_paragraphs(conn)
        chunks = STRATEGIES[args.strategy](paragraphs)
        write_chunks(conn, args.strategy, chunks)

    lengths = [len(c.text) for c in chunks]
    with_heading = sum(1 for c in chunks if len(c.covers) > 1 or c.heading)
    print(
        f"{args.strategy}: {len(chunks):,} chunks from {len(paragraphs):,} paragraphs; "
        f"length median {statistics.median(lengths):,.0f}, max {max(lengths):,}; "
        f"chunks carrying a heading: {with_heading:,}"
    )


if __name__ == "__main__":
    main()
