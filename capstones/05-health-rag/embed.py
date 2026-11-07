"""Embed every paragraph that has text and no vector yet.

Usage (from capstones/05-health-rag):
    uv run python embed.py

Safe to re-run: only rows with `embedding IS NULL` are picked, and each batch
commits on its own, so a crash halfway loses at most one batch.
"""

from __future__ import annotations

import os
from typing import Any, NamedTuple, cast

import numpy as np
import psycopg
from numpy.typing import NDArray
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BATCH_SIZE = 128

READ_QUERY = """
    SELECT booklet, para_no, text
    FROM paragraphs
    WHERE embedding IS NULL AND text <> ''
    ORDER BY booklet, para_no
"""

UPDATE_QUERY = """
    UPDATE paragraphs
    SET embedding = %s
    WHERE booklet = %s AND para_no = %s
"""


class Paragraph(NamedTuple):
    booklet: int
    para_no: int
    text: str


def load_model() -> SentenceTransformer:
    return SentenceTransformer(
        MODEL_NAME, device="mps"
    )  # "cpu" also works, more slowly


def encode(model: SentenceTransformer, texts: list[str]) -> NDArray[np.float32]:
    """Unit-length float32 vectors, one row per text. Shared with retrieve.py."""
    raw: Any = cast(Any, model).encode(
        texts,
        batch_size=BATCH_SIZE,
        normalize_embeddings=True,  # so cosine distance (<=>) is the right comparison
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return np.asarray(raw, dtype=np.float32)


def token_counts(model: SentenceTransformer, texts: list[str]) -> list[int]:
    """Tokens per text, including [CLS] and [SEP], with no truncation."""
    out: Any = model.tokenizer(texts, truncation=False, verbose=False)
    return [len(ids) for ids in cast(list[list[int]], out["input_ids"])]


def read_pending(conn: psycopg.Connection[Any]) -> list[Paragraph]:
    rows = conn.execute(READ_QUERY).fetchall()
    return [Paragraph(int(r[0]), int(r[1]), str(r[2])) for r in rows]


def main() -> None:
    url = os.environ[
        "HEALTH_RAG_DATABASE_URL"
    ]  # libpq form: postgresql://user:pw@host:port/db
    model = load_model()
    max_tokens = model.max_seq_length  # 256 for this model; text past it is never seen
    if max_tokens is None:
        raise RuntimeError(f"{MODEL_NAME} reports no max_seq_length")

    with psycopg.connect(url) as conn:
        register_vector(conn)  # numpy arrays are sent as `vector`
        paragraphs = read_pending(conn)
        conn.commit()  # end the read transaction before the writes start
        print(f"{len(paragraphs)} paragraphs to embed")

        truncated: list[tuple[Paragraph, int]] = []
        done = 0
        for start in range(0, len(paragraphs), BATCH_SIZE):
            batch = paragraphs[start : start + BATCH_SIZE]
            texts = [p.text for p in batch]

            for p, n in zip(batch, token_counts(model, texts), strict=True):
                if n > max_tokens:
                    truncated.append((p, n))

            vectors = encode(model, texts)
            with conn.transaction(), conn.cursor() as cur:  # one transaction per batch
                cur.executemany(
                    UPDATE_QUERY,
                    [
                        (vec, p.booklet, p.para_no)
                        for vec, p in zip(vectors, batch, strict=True)
                    ],
                )
            done += len(batch)
            print(f"  embedded {done}/{len(paragraphs)}")

        stored = conn.execute(
            "SELECT count(*) FROM paragraphs WHERE embedding IS NOT NULL"
        ).fetchone()

    print(f"\nRows with a vector: {stored[0] if stored else 0} (expected 5,155)")
    print(f"Paragraphs over {max_tokens} tokens (cut off): {len(truncated)}")
    for p, n in sorted(truncated, key=lambda t: t[1], reverse=True)[:10]:
        print(
            f"  booklet {p.booklet}, paragraph {p.para_no}: {n} tokens, {n - max_tokens} lost"
        )


if __name__ == "__main__":
    main()
