"""Embed one strategy's chunks that have no vector yet.

Usage (from capstones/05-health-rag):
    uv run python embed_chunks.py --strategy split

Safe to re-run: only rows with `embedding IS NULL` are picked, and each batch
commits on its own. Uses the same model and normalisation as embed.py.
"""

from __future__ import annotations

import argparse
import os
from typing import Any, NamedTuple

import psycopg
from embed import BATCH_SIZE, MODEL_NAME, encode, load_model, token_counts
from pgvector.psycopg import register_vector

READ_QUERY = """
    SELECT id, booklet, covers, text
    FROM chunks
    WHERE strategy = %s AND embedding IS NULL
    ORDER BY id
"""

UPDATE_QUERY = """
    UPDATE chunks
    SET embedding = %s
    WHERE id = %s
"""

COUNT_QUERY = """
    SELECT count(*), count(embedding)
    FROM chunks
    WHERE strategy = %s
"""


class Chunk(NamedTuple):
    id: int
    booklet: int
    covers: list[int]
    text: str


def read_pending(conn: psycopg.Connection[Any], strategy: str) -> list[Chunk]:
    rows = conn.execute(READ_QUERY, (strategy,)).fetchall()
    return [Chunk(int(r[0]), int(r[1]), list(r[2]), str(r[3])) for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--strategy", required=True)
    args = parser.parse_args()

    url = os.environ[
        "HEALTH_RAG_DATABASE_URL"
    ]  # libpq form: postgresql://user:pw@host:port/db
    model = load_model()
    max_tokens = model.max_seq_length  # 256 for this model; text past it is never seen
    if max_tokens is None:
        raise RuntimeError(f"{MODEL_NAME} reports no max_seq_length")

    with psycopg.connect(url) as conn:
        register_vector(conn)  # numpy arrays are sent as `vector`
        chunks = read_pending(conn, args.strategy)
        conn.commit()  # end the read transaction before the writes start
        print(f"{args.strategy}: {len(chunks)} chunks to embed")

        truncated: list[tuple[Chunk, int]] = []
        done = 0
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            texts = [c.text for c in batch]

            for c, n in zip(batch, token_counts(model, texts), strict=True):
                if n > max_tokens:
                    truncated.append((c, n))

            vectors = encode(model, texts)
            with conn.transaction(), conn.cursor() as cur:  # one transaction per batch
                cur.executemany(
                    UPDATE_QUERY,
                    [(vec, c.id) for vec, c in zip(vectors, batch, strict=True)],
                )
            done += len(batch)
            print(f"  embedded {done}/{len(chunks)}")

        row = conn.execute(COUNT_QUERY, (args.strategy,)).fetchone()

    total, with_vector = (int(row[0]), int(row[1])) if row else (0, 0)
    print(
        f"\n{args.strategy}: {with_vector} of {total} chunks have a vector (must be equal)"
    )
    print(f"Chunks over {max_tokens} tokens (cut off): {len(truncated)}")
    for c, n in sorted(truncated, key=lambda t: t[1], reverse=True)[:10]:
        print(
            f"  chunk {c.id} (booklet {c.booklet}, covers {c.covers}): {n} tokens, {n - max_tokens} lost"
        )


if __name__ == "__main__":
    main()
