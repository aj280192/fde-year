"""Re-order retrieved chunks with a cross-encoder.

The embedding model scores the question and each chunk separately; a
cross-encoder reads the question and one chunk together, which is more accurate
but far slower, so it only re-sorts the first retriever's top 20.
"""

from __future__ import annotations

from typing import Any, cast

from retrieve_chunks import ChunkHit
from sentence_transformers import CrossEncoder

RERANK_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"


def load_reranker() -> CrossEncoder:
    return CrossEncoder(RERANK_MODEL, device="mps")  # "cpu" also works, more slowly


def rerank(
    model: CrossEncoder, question: str, hits: list[ChunkHit], texts: dict[int, str]
) -> list[ChunkHit]:
    """The same hits, best first by cross-encoder score; ties keep their original order."""
    if not hits:
        return []
    raw: Any = cast(Any, model).predict(
        [(question, texts[h.chunk_id]) for h in hits], show_progress_bar=False
    )
    scores = [float(s) for s in raw]
    order = sorted(range(len(hits)), key=lambda i: (-scores[i], i))
    return [hits[i] for i in order]
