import argparse
import asyncio
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import psycopg
from checks import Source, check_answer, check_retrieval
from config import (
    ABSTAIN_TEXT,
    ABSTAIN_THRESHOLD,
    FINAL_STRATEGY,
    HEALTH_DB,
    LLM_BASE_URL,
    LLM_MODEL,
    POOL,
    TOP_K,
)
from embed import encode, load_model
from pgvector.psycopg import register_vector
from rerank import load_reranker, rerank_scored
from retrieve_chunks import chunk_texts, hybrid_c, keyword_norm_c
from sentence_transformers import CrossEncoder, SentenceTransformer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "labs" / "week03"))
from client import LLMClient

SYSTEM_PROMPT = """You answer questions about public health guidelines using ONLY the numbered sources provided.
Rules:
1. Use only facts stated in the sources. Do not add outside knowledge.
2. After every sentence that uses a source, cite it in square brackets with its exact id, e.g. [BX:XXX].
   Cite several like [BX:XXX][BX:XX]. Never invent an id.
3. If the sources do not contain the answer, reply with exactly: cannot find in sources
4. Be brief: at most five sentences."""


@dataclass(frozen=True)
class Answer:
    text: str
    abstained: bool
    reason: str | None  # see step 5
    citations: list[Source]  # the sources the answer cited, in order of first mention
    sources: list[Source]  # everything retrieved, for --trace
    retrieval_ms: float
    generation_ms: float  # 0 when the model wasn't called
    system_prompt: str | None = None  # None when the model wasn't called
    user_prompt: str | None = None
    model_text: str | None = None  # the raw reply, kept when an after-check rejects it


def print_answer(result: Answer) -> None:
    print(result.text)
    if result.abstained:
        print(f"(reason: {result.reason})")
        return
    print("\nSources:")
    for s in result.citations:
        snippet = " ".join(s.text.split())[:100]  # squeeze whitespace, then cut
        print(f"  [{s.id}] booklet {s.booklet}, paragraph {s.paragraph}: {snippet}…")


def print_trace(result: Answer) -> None:
    def out(line: str = "") -> None:
        print(line, file=sys.stderr)

    out("RETRIEVED")
    for i, s in enumerate(result.sources, start=1):
        snippet = " ".join(s.text.split())[:80]
        flag = "  ← below threshold" if s.score < ABSTAIN_THRESHOLD else ""
        out(f'  {i}. [{s.id}]  score {s.score:6.2f}  "{snippet}…"{flag}')

    out("\nPROMPT")
    if result.system_prompt is None or result.user_prompt is None:
        out("  (not sent: abstained before generation)")
    else:
        out(result.system_prompt)
        out("-" * 60)
        out(result.user_prompt)

    total = result.retrieval_ms + result.generation_ms
    out(
        f"\nTIMING  retrieval {result.retrieval_ms:,.0f} ms · "
        f"generation {result.generation_ms:,.0f} ms · total {total:,.0f} ms"
    )
    if result.abstained and result.model_text is not None:
        out("\nMODEL OUTPUT (rejected)")
        out(result.model_text)

    if result.abstained:
        out(f"DECISION  abstained: {result.reason}")
    else:
        out("DECISION  answered, citing " + ", ".join(s.id for s in result.citations))
    out()


def _abstain(
    reason: str,
    sources: list[Source],
    retrieval_ms: float,
    generation_ms: float,
    *,
    system_prompt: str | None = None,
    user_prompt: str | None = None,
    model_text: str | None = None,
) -> Answer:
    return Answer(
        text=ABSTAIN_TEXT,
        abstained=True,
        reason=reason,
        citations=[],
        sources=sources,
        retrieval_ms=retrieval_ms,
        generation_ms=generation_ms,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        model_text=model_text,
    )


def retrieve_sources(
    conn: psycopg.Connection[Any],
    embedder: SentenceTransformer,
    reranker: CrossEncoder,
    question: str,
) -> list[Source]:
    """The TOP_K best chunks for a question, best first, each with a citation id and its score."""
    # 1 · The question as a vector: the same model and normalisation as the chunks.
    query_vec = encode(embedder, [question])[0]

    # 2 · Hybrid search: keyword (rank divided by length) and vector, merged by rank. POOL = 20 candidates.
    hits = hybrid_c(
        conn, question, query_vec, FINAL_STRATEGY, POOL, keyword_fn=keyword_norm_c
    )

    # 3 · Their text, in one query.
    texts = chunk_texts(conn, hits)

    # 4 · The cross-encoder scores each (question, chunk) pair; keep the best TOP_K.
    scored = rerank_scored(reranker, question, hits, texts)[:TOP_K]

    # 5 · Citation ids: the content paragraph, plus #2, #3… if one paragraph appears twice.
    sources: list[Source] = []
    seen: dict[str, int] = {}
    for hit, score in scored:
        paragraph = hit.covers[-1]
        base = f"B{hit.booklet}:{paragraph}"
        seen[base] = seen.get(base, 0) + 1
        source_id = base if seen[base] == 1 else f"{base}#{seen[base]}"
        sources.append(
            Source(
                id=source_id,
                booklet=hit.booklet,
                paragraph=paragraph,
                text=texts[hit.chunk_id],
                score=score,
            )
        )

    return sources


def build_prompt(sources: list[Source], question: str) -> tuple[str, str]:
    """The (system, user) messages: the rules, then the numbered sources and the question."""
    blocks = [f"[{s.id}] {s.text.strip()}" for s in sources]
    user = "Sources:\n" + "\n\n".join(blocks) + f"\n\nQuestion: {question.strip()}"
    return SYSTEM_PROMPT, user


async def generate(system: str, user: str) -> str:
    async with LLMClient(
        LLM_BASE_URL, LLM_MODEL, total_budget=120.0, read_timeout=120.0
    ) as llm:
        return await llm.complete(user, system=system, temperature=0.0)


async def answer(
    question: str,
    *,
    conn: psycopg.Connection[Any],
    embedder: SentenceTransformer,
    reranker: CrossEncoder,
    threshold: float = ABSTAIN_THRESHOLD,
) -> Answer:
    # 1 · Retrieve, and time it.
    started = time.perf_counter()
    sources = retrieve_sources(conn, embedder, reranker, question)
    retrieval_ms = (time.perf_counter() - started) * 1000

    # 2 · Before-check: abstain without calling the model.
    reason = check_retrieval(sources, threshold)
    if reason is not None:
        return _abstain(reason, sources, retrieval_ms, generation_ms=0.0)

    # 3 · Prompt and generate, and time it.
    system, user = build_prompt(sources, question)
    started = time.perf_counter()
    text = await generate(system, user)
    generation_ms = (time.perf_counter() - started) * 1000

    # 4 · After-checks: the answer must cite only what it was given.
    by_id = {s.id: s for s in sources}
    reason, cited_ids = check_answer(text, set(by_id))
    if reason is not None:
        return _abstain(
            reason,
            sources,
            retrieval_ms,
            generation_ms,
            system_prompt=system,
            user_prompt=user,
            model_text=text,
        )

    # 5 · Success: the answer, and the sources it actually cited.
    return Answer(
        text=text.strip(),
        abstained=False,
        reason=None,
        citations=[by_id[i] for i in cited_ids],
        sources=sources,
        retrieval_ms=retrieval_ms,
        generation_ms=generation_ms,
        system_prompt=system,
        user_prompt=user,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Answer a question from the health booklets, with citations."
    )
    parser.add_argument("question")
    parser.add_argument(
        "--trace",
        action="store_true",
        help="print sources, prompt and timings to stderr",
    )
    args = parser.parse_args()
    asyncio.run(main_async(args.question, trace=args.trace))


async def main_async(question: str, *, trace: bool) -> None:
    embedder = load_model()  # from embed.py
    reranker = load_reranker()  # from rerank.py
    with psycopg.connect(HEALTH_DB) as conn:
        register_vector(conn)  # the question's vector must be sent as a `vector`
        result = await answer(question, conn=conn, embedder=embedder, reranker=reranker)
    if trace:
        print_trace(result)  # step 7: to stderr
    print_answer(result)  # to stdout


if __name__ == "__main__":
    main()
