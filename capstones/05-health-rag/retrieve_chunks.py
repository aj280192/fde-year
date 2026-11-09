"""Retrievers over the `chunks` table: one chunking strategy at a time.

The same three searches as retrieve.py (keyword, vector, hybrid by RRF), but
each returns ChunkHit rows carrying the paragraphs the chunk covers, so
evaluate.py can score chunks against paragraph labels.

The connection must have had `register_vector(conn)` called on it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, LiteralString, NamedTuple

import numpy as np
import psycopg
from numpy.typing import NDArray
from retrieve import Hit, rrf


class ChunkHit(NamedTuple):
    chunk_id: int
    booklet: int
    covers: tuple[int, ...]


# Any word may match. `id` breaks ties, so runs are repeatable; chunks are
# inserted in (booklet, paragraph) order, so for `whole` this matches retrieve.py.
KEYWORD_QUERY = """
    SELECT id, booklet, covers
    FROM chunks,
         CAST(replace(plainto_tsquery('english', %(q)s)::text, '&', '|') AS tsquery) AS q
    WHERE strategy = %(s)s AND tsv @@ q
    ORDER BY ts_rank_cd(tsv, q) DESC, id
    LIMIT %(k)s
"""

KEYWORD_NORM_QUERY = """
    SELECT id, booklet, covers
    FROM chunks,
         CAST(replace(plainto_tsquery('english', %(q)s)::text, '&', '|') AS tsquery) AS q
    WHERE strategy = %(s)s AND tsv @@ q
    ORDER BY ts_rank_cd(tsv, q, 1) DESC, id
    LIMIT %(k)s
"""

# Heading words (weight A) count more than words in the text (weight D).
KEYWORD_WEIGHTED_QUERY = """
    SELECT id, booklet, covers
    FROM chunks,
         CAST(replace(plainto_tsquery('english', %(q)s)::text, '&', '|') AS tsquery) AS q
    WHERE strategy = %(s)s AND tsv_weighted @@ q
    ORDER BY ts_rank_cd(tsv_weighted, q, 1) DESC, id
    LIMIT %(k)s
"""

VECTOR_QUERY = """
    SELECT id, booklet, covers
    FROM chunks
    WHERE strategy = %(s)s AND embedding IS NOT NULL
    ORDER BY embedding <=> %(e)s, id
    LIMIT %(k)s
"""

TEXT_QUERY = "SELECT id, text FROM chunks WHERE id = ANY(%s)"

KeywordFn = Callable[[psycopg.Connection[Any], str, str, int], list[ChunkHit]]


def _hits(
    conn: psycopg.Connection[Any], query: LiteralString, params: dict[str, Any]
) -> list[ChunkHit]:
    rows = conn.execute(query, params).fetchall()
    return [ChunkHit(int(r[0]), int(r[1]), tuple(int(p) for p in r[2])) for r in rows]


def keyword_c(
    conn: psycopg.Connection[Any], question: str, strategy: str, k: int
) -> list[ChunkHit]:
    """Full text, any word, plain rank."""
    return _hits(conn, KEYWORD_QUERY, {"q": question, "s": strategy, "k": k})


def keyword_norm_c(
    conn: psycopg.Connection[Any], question: str, strategy: str, k: int
) -> list[ChunkHit]:
    """Full text, any word, rank divided by length."""
    return _hits(conn, KEYWORD_NORM_QUERY, {"q": question, "s": strategy, "k": k})


def keyword_weighted_c(
    conn: psycopg.Connection[Any], question: str, strategy: str, k: int
) -> list[ChunkHit]:
    """Full text over heading (weight A) and text (weight D), rank divided by length."""
    return _hits(conn, KEYWORD_WEIGHTED_QUERY, {"q": question, "s": strategy, "k": k})


def vector_c(
    conn: psycopg.Connection[Any], query_vec: NDArray[np.float32], strategy: str, k: int
) -> list[ChunkHit]:
    """Nearest chunks by cosine distance."""
    return _hits(conn, VECTOR_QUERY, {"e": query_vec, "s": strategy, "k": k})


def hybrid_c(
    conn: psycopg.Connection[Any],
    question: str,
    query_vec: NDArray[np.float32],
    strategy: str,
    k: int,
    keyword_fn: KeywordFn = keyword_c,
    pool_size: int = 50,
) -> list[ChunkHit]:
    """Keyword and vector, top `pool_size` each, merged by reciprocal rank fusion."""
    return rrf(
        [
            keyword_fn(conn, question, strategy, pool_size),
            vector_c(conn, query_vec, strategy, pool_size),
        ],
        k,
    )


def expand(hits: list[ChunkHit]) -> list[Hit]:
    """The paragraphs the chunks cover, in rank order, each once."""
    seen: set[Hit] = set()
    out: list[Hit] = []
    for h in hits:
        for p in h.covers:
            hit = Hit(h.booklet, p)
            if hit not in seen:
                seen.add(hit)
                out.append(hit)
    return out


def chunk_texts(conn: psycopg.Connection[Any], hits: list[ChunkHit]) -> dict[int, str]:
    """The text of each chunk, by id (for the reranker and the context size)."""
    rows = conn.execute(TEXT_QUERY, ([h.chunk_id for h in hits],)).fetchall()
    return {int(r[0]): str(r[1]) for r in rows}
