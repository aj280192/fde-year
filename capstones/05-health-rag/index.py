import os
from dataclasses import dataclass
from typing import Any

import config
import psycopg
from build_chunks import read_paragraphs
from embed import load_model
from snippets_q1 import build_index, chunk_documents


@dataclass(frozen=True)
class ReadCounts:
    chunk_count: int
    embed_count: int


COUNT_QUERY = """SELECT count(*), count(embedding) FROM chunks WHERE strategy = %s"""


def read_count(conn: psycopg.Connection[Any], strategy: str) -> ReadCounts:
    row = conn.execute(COUNT_QUERY, (strategy,)).fetchone()
    if row is None:
        return ReadCounts(0, 0)

    chunk_count, embed_count = row
    return ReadCounts(int(chunk_count), int(embed_count))


def main() -> None:
    with psycopg.connect(os.environ["HEALTH_RAG_DATABASE_URL"]) as conn:
        paragraphs = read_paragraphs(conn)
        chunks = chunk_documents(paragraphs, config.FINAL_STRATEGY)
        build_index(conn, chunks, load_model(), config.FINAL_STRATEGY)
        counts = read_count(conn, config.FINAL_STRATEGY)
        print(f"{counts.chunk_count} chunks, {counts.embed_count} with a vector")


if __name__ == "__main__":
    main()
