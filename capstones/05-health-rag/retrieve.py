"""Three retrievers over `paragraphs`: keyword, vector, and hybrid (RRF).

Each returns a ranked list of Hit(booklet, para_no), best first.

The connection must have had `register_vector(conn)` called on it, so the
question's numpy vector is sent as a `vector` (a Python list is sent as
`double precision[]`, and `vector <=> double precision[]` doesn't exist).

Quick look (step 0.4):
    uv run python retrieve.py "How should specimens be collected for suspected anthrax?"
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from typing import Any, LiteralString, NamedTuple

import numpy as np
import psycopg
from embed import encode, load_model
from numpy.typing import NDArray
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer


class Hit(NamedTuple):
    booklet: int  # an int, like the column and the labels: ("6", 140) != (6, 140)
    para_no: int


# Any word may match. The final ORDER BY columns break ties, so runs are repeatable.
KEYWORD_ANY_QUERY = """
    SELECT booklet, para_no
    FROM paragraphs,
         CAST(replace(plainto_tsquery('english', %(q)s)::text, '&', '|') AS tsquery) AS q
    WHERE tsv @@ q
    ORDER BY ts_rank_cd(tsv, q) DESC, booklet, para_no
    LIMIT %(k)s
"""

KEYWORD_ANY_QUERY_NORM = """
    SELECT booklet, para_no
    FROM paragraphs,
         CAST(replace(plainto_tsquery('english', %(q)s)::text, '&', '|') AS tsquery) AS q
    WHERE tsv @@ q
    ORDER BY ts_rank_cd(tsv, q, 1) DESC, booklet, para_no
    LIMIT %(k)s
"""

# Every word must match.
KEYWORD_ALL_QUERY = """
    SELECT booklet, para_no
    FROM paragraphs, plainto_tsquery('english', %(q)s) AS q
    WHERE tsv @@ q
    ORDER BY ts_rank_cd(tsv, q) DESC, booklet, para_no
    LIMIT %(k)s
"""

VECTOR_QUERY = """
    SELECT booklet, para_no
    FROM paragraphs
    WHERE embedding IS NOT NULL
    ORDER BY embedding <=> %(e)s, booklet, para_no
    LIMIT %(k)s
"""


def _hits(
    conn: psycopg.Connection[Any], query: LiteralString, params: dict[str, Any]
) -> list[Hit]:
    rows = conn.execute(query, params).fetchall()
    return [Hit(int(r[0]), int(r[1])) for r in rows]


def embed_query(model: SentenceTransformer, question: str) -> NDArray[np.float32]:
    """The same model and normalisation as the paragraphs (embed.encode)."""
    return encode(model, [question])[0]


def keyword(conn: psycopg.Connection[Any], question: str, k: int = 10) -> list[Hit]:
    """Full-text search; any word of the question may match."""
    return _hits(conn, KEYWORD_ANY_QUERY, {"q": question, "k": k})


def keyword_norm(
    conn: psycopg.Connection[Any], question: str, k: int = 10
) -> list[Hit]:
    """Full-text search; any word of the question may match."""
    return _hits(conn, KEYWORD_ANY_QUERY_NORM, {"q": question, "k": k})


def keyword_all(conn: psycopg.Connection[Any], question: str, k: int = 10) -> list[Hit]:
    """Full-text search; every word of the question must match."""
    return _hits(conn, KEYWORD_ALL_QUERY, {"q": question, "k": k})


def vector(
    conn: psycopg.Connection[Any], query_vec: NDArray[np.float32], k: int = 10
) -> list[Hit]:
    """Nearest paragraphs by cosine distance (<=>; smaller is closer)."""
    return _hits(conn, VECTOR_QUERY, {"e": query_vec, "k": k})


def rrf[T: tuple[Any, ...]](
    ranked_lists: list[list[T]], k: int, rrf_k: int = 60
) -> list[T]:
    """Reciprocal rank fusion: score = sum over lists of 1 / (rrf_k + rank).

    Works on any tuple-like hit (a Hit, or a ChunkHit from retrieve_chunks.py).
    """
    scores: dict[T, float] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked, start=1):
            scores[hit] = scores.get(hit, 0.0) + 1.0 / (rrf_k + rank)
    # Highest score first; ties broken by the hit itself, so runs are repeatable.
    return sorted(scores, key=lambda h: (-scores[h], h))[:k]


KeywordFn = Callable[[psycopg.Connection[Any], str, int], list[Hit]]


def hybrid(
    conn: psycopg.Connection[Any],
    question: str,
    query_vec: NDArray[np.float32],
    k: int = 10,
    pool_size: int = 50,
    keyword_fn: KeywordFn = keyword,
) -> list[Hit]:
    """A keyword list (any word, by default) and vector, top `pool_size` each, merged by RRF."""
    return rrf(
        [keyword_fn(conn, question, pool_size), vector(conn, query_vec, pool_size)], k
    )


def main() -> None:
    question = (
        " ".join(sys.argv[1:])
        or "How should specimens be collected for suspected anthrax?"
    )
    model = load_model()
    with psycopg.connect(os.environ["HEALTH_RAG_DATABASE_URL"]) as conn:
        register_vector(conn)
        qv = embed_query(model, question)
        results = {
            "keyword_all": keyword_all(conn, question, 5),
            "keyword": keyword(conn, question, 5),
            "vector": vector(conn, qv, 5),
            "hybrid": hybrid(conn, question, qv, 5),
        }
    print(question)
    for name, hits in results.items():
        print(f"  {name:<12} " + "  ".join(f"({h.booklet},{h.para_no})" for h in hits))


if __name__ == "__main__":
    main()
