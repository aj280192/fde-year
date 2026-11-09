"""Question 1: the three retrieval functions, in one place.

The final configuration (Q1_Retrieval_Design.md; results.csv for the numbers):
- chunking: each paragraph carries the heading above it, and any chunk over 1,000
  characters is split into ~800-character pieces with 100 overlapping (`headings_split`)
- index: Postgres full text (GIN over a generated tsvector) and pgvector
  (all-MiniLM-L6-v2, 384 dimensions, normalised, cosine distance)
- retrieval: keyword (rank divided by length) and vector, top 50 each, merged by
  reciprocal rank fusion; the top 20 re-ordered by a cross-encoder
- results: Recall@5 0.649 on tuning (run 19), 0.691 on the held-out questions (run 20)

The full code: build_chunks.py, embed_chunks.py, retrieve_chunks.py, rerank.py.
If the final configuration changes, change FINAL_STRATEGY, the keyword function in
`retrieve`, and USE_RERANKER to match the kept rows of the results table.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import psycopg
from build_chunks import STRATEGIES, Chunk, Paragraph, write_chunks
from embed import encode
from numpy.typing import NDArray
from pgvector.psycopg import register_vector
from retrieve_chunks import ChunkHit, chunk_texts, hybrid_c, keyword_norm_c
from sentence_transformers import SentenceTransformer

FINAL_STRATEGY = "headings_split"
USE_RERANKER = True  # kept: +5.9 Recall@5, +11.1 MRR@5 (run 19)
TOP_K = 5
POOL = 20  # candidates for the reranker


def chunk_documents(
    paragraphs: list[Paragraph], strategy: str = FINAL_STRATEGY
) -> list[Chunk]:
    """Turn ordered paragraphs into searchable chunks.

    Each chunk records `covers`: the paragraphs it stands for, so a retrieved chunk
    can be cited as (booklet, paragraph). With `headings_split`, a paragraph is
    prefixed with the heading above it (and covers that heading too), and anything
    over 1,000 characters is split into overlapping ~800-character pieces.
    """
    return STRATEGIES[strategy](paragraphs)


def build_index(
    conn: psycopg.Connection[Any],
    chunks: list[Chunk],
    model: SentenceTransformer,
    strategy: str = FINAL_STRATEGY,
    batch_size: int = 128,
) -> None:
    """Store the chunks and their vectors.

    The keyword index needs no code: `tsv` is a generated column with a GIN index
    (schema_chunks.sql), so Postgres keeps it up to date on insert. Vectors are
    added in batches, one transaction each, so a failure loses at most one batch.
    """
    register_vector(conn)
    # Replaces this strategy's rows, all or nothing.
    write_chunks(conn, strategy, chunks)
    rows = conn.execute(
        "SELECT id, text FROM chunks WHERE strategy = %s AND embedding IS NULL ORDER BY id",
        (strategy,),
    ).fetchall()
    for start in range(0, len(rows), batch_size):
        batch = rows[start : start + batch_size]
        vectors = encode(model, [str(r[1]) for r in batch])
        with conn.transaction(), conn.cursor() as cur:
            cur.executemany(
                "UPDATE chunks SET embedding = %s WHERE id = %s",
                [(v, int(r[0])) for v, r in zip(vectors, batch, strict=True)],
            )


def retrieve(
    conn: psycopg.Connection[Any],
    model: SentenceTransformer,
    question: str,
    k: int = TOP_K,
    strategy: str = FINAL_STRATEGY,
    reranker: Any = None,
) -> list[tuple[ChunkHit, str]]:
    """The top k chunks for a question, best first, each with its text.

    Hybrid search: keyword (rank divided by length) and vector, top 50 each,
    merged by reciprocal rank fusion. With a reranker (USE_RERANKER), the top 20
    are re-ordered by a cross-encoder before the cut to k.
    """
    register_vector(conn)
    query_vec: NDArray[np.float32] = encode(model, [question])[0]
    hits = hybrid_c(
        conn, question, query_vec, strategy, POOL, keyword_fn=keyword_norm_c
    )
    texts = chunk_texts(conn, hits)
    if reranker is not None:
        from rerank import rerank

        hits = rerank(reranker, question, hits, texts)
    return [(h, texts[h.chunk_id]) for h in hits[:k]]
