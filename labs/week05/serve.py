"""Run the task API on localhost:8000 with one dev key.

uv run python labs/week05/auth.py     # once: prints a new key and its hash
TASKS_API_KEY_HASH=<hash> uv run python labs/week05/serve.py

With HEALTH_RAG_DATABASE_URL also set, POST /v1/ask answers from the health booklets
(capstones/05-health-rag); without it, POST /v1/ask answers 501.
"""

import asyncio
import os
import sys
from pathlib import Path

import uvicorn
from api.app import create_app
from api.ask import Answerer, AskResult, Citation
from api.auth import READ, WRITE, Principal


def build_answerer() -> Answerer | None:
    """The health RAG pipeline as an Answerer, or None (POST /v1/ask then answers 501).

    Only built when HEALTH_RAG_DATABASE_URL is set, so the task API still runs
    without the capstone's database or models.
    """
    url = os.environ.get("HEALTH_RAG_DATABASE_URL")
    if not url:
        return None
    sys.path.insert(
        0, str(Path(__file__).resolve().parents[2] / "capstones" / "05-health-rag")
    )
    import psycopg
    from embed import load_model
    from pgvector.psycopg import register_vector
    from rag import answer
    from rerank import load_reranker

    embedder, reranker = load_model(), load_reranker()  # once, at startup
    conn = psycopg.connect(url, autocommit=True)
    register_vector(conn)
    lock = asyncio.Lock()  # one connection: one question at a time uses it

    async def answerer(question: str) -> AskResult:
        async with lock:
            a = await answer(question, conn=conn, embedder=embedder, reranker=reranker)
        return AskResult(
            text=a.text,
            abstained=a.abstained,
            reason=a.reason,
            citations=[Citation(c.id, c.booklet, c.paragraph) for c in a.citations],
        )

    return answerer


app = create_app(
    {
        os.environ["TASKS_API_KEY_HASH"]: Principal(
            key_id="me", scopes=frozenset({READ, WRITE})
        )
    },
    answerer=build_answerer(),
)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
