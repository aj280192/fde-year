"""Score one retrieval setup on the tuning questions, and record the run.

Usage (from capstones/05-health-rag):
    uv run python evaluate.py --method hybrid --notes "RRF k=60, top 50 each"
    uv run python evaluate.py --method hybrid --chunking split --notes "long paragraphs split"
    uv run python evaluate.py --method hybrid --chunking split --rerank --notes "cross-encoder"

--chunking paragraphs (the default) searches the `paragraphs` table, as in runs 1 to 5.
Any other value is a strategy in the `chunks` table (build_chunks.py, embed_chunks.py).
A chunk covers one or more paragraphs; the top k *chunks* are what the model would
receive, so Recall@k and MRR@k are cut by chunk rank and scored on the paragraphs
those chunks cover.

Each run appends one row to results.csv (numbers only, safe to commit) and
writes every question's hits to data/runs/run_<id>.jsonl (ignored by git).
The held-out set is refused unless --final is given: it is used once.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
from collections import defaultdict
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
from embed import encode, load_model
from metrics import mean, mrr_groups_at_k, recall_groups_at_k
from numpy.typing import NDArray
from pgvector.psycopg import register_vector
from retrieve import Hit, hybrid, keyword, keyword_all, keyword_norm, vector
from retrieve_chunks import (
    ChunkHit,
    chunk_texts,
    hybrid_c,
    keyword_c,
    keyword_norm_c,
    keyword_weighted_c,
    vector_c,
)

HERE = Path(__file__).parent
DATA = HERE / "data"
RESULTS = HERE / "results.csv"
POOL = 20  # every method returns its top 20; the metrics read the top 5 and 20

Vec = NDArray[np.float32]
Conn = psycopg.Connection[Any]
ParagraphRetriever = Callable[[Conn, str, Vec | None], list[Hit]]
ChunkRetriever = Callable[[Conn, str, Vec | None, str], list[ChunkHit]]


def _vec(qv: Vec | None) -> Vec:
    if qv is None:
        raise RuntimeError("this method needs the question's vector")
    return qv


PARAGRAPH_METHODS: dict[str, ParagraphRetriever] = {
    "keyword_all": lambda c, q, qv: keyword_all(c, q, POOL),
    "keyword": lambda c, q, qv: keyword(c, q, POOL),
    "keyword_norm": lambda c, q, qv: keyword_norm(c, q, POOL),
    "vector": lambda c, q, qv: vector(c, _vec(qv), POOL),
    "hybrid": lambda c, q, qv: hybrid(c, q, _vec(qv), POOL),
    "hybrid_norm": lambda c, q, qv: hybrid(
        c, q, _vec(qv), POOL, keyword_fn=keyword_norm
    ),
}

CHUNK_METHODS: dict[str, ChunkRetriever] = {
    "keyword": lambda c, q, qv, s: keyword_c(c, q, s, POOL),
    "keyword_norm": lambda c, q, qv, s: keyword_norm_c(c, q, s, POOL),
    "keyword_weighted": lambda c, q, qv, s: keyword_weighted_c(c, q, s, POOL),
    "vector": lambda c, q, qv, s: vector_c(c, _vec(qv), s, POOL),
    "hybrid": lambda c, q, qv, s: hybrid_c(c, q, _vec(qv), s, POOL),
    "hybrid_norm": lambda c, q, qv, s: hybrid_c(
        c, q, _vec(qv), s, POOL, keyword_fn=keyword_norm_c
    ),
    "hybrid_weighted": lambda c, q, qv, s: hybrid_c(
        c, q, _vec(qv), s, POOL, keyword_fn=keyword_weighted_c
    ),
}

NEEDS_VECTOR = {"vector", "hybrid", "hybrid_norm", "hybrid_weighted"}

COLUMNS = [
    "run_id",
    "date",
    "split",
    "method",
    "chunking",
    "k",
    "n_questions",
    "recall_at_5",
    "mrr_at_5",
    "recall_at_20",
    "per_booklet_recall_at_5",
    "empty_results",
    "ms_per_question",
    "notes",
]


def load_split(name: str) -> list[dict[str, Any]]:
    with (DATA / f"{name}.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def next_run_id() -> int:
    if not RESULTS.exists():
        return 1
    with RESULTS.open(newline="") as f:
        ids = [int(r["run_id"]) for r in csv.DictReader(f)]
    return max(ids, default=0) + 1


def append_result(row: dict[str, Any]) -> None:
    new_file = not RESULTS.exists()
    if not new_file:
        # A hand-edited file may have lost its final newline; without one, this row
        # would be glued onto the last line and its run id read back wrongly.
        content = RESULTS.read_bytes()
        if content and not content.endswith(b"\n"):
            with RESULTS.open("ab") as f:
                f.write(b"\r\n")  # csv writes \r\n line endings
    with RESULTS.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--method",
        required=True,
        choices=sorted(set(PARAGRAPH_METHODS) | set(CHUNK_METHODS)),
    )
    p.add_argument(
        "--chunking",
        default="paragraphs",
        help="'paragraphs', or a strategy in the chunks table",
    )
    p.add_argument(
        "--rerank",
        action="store_true",
        help="re-order the top 20 with the cross-encoder (chunks only)",
    )
    p.add_argument("--split", default="tuning", choices=["tuning", "heldout"])
    p.add_argument(
        "--final", action="store_true", help="required to run on the held-out split"
    )
    p.add_argument("--notes", default="")
    args = p.parse_args()

    on_chunks = args.chunking != "paragraphs"
    if args.split == "heldout" and not args.final:
        p.error(
            "the held-out split is used once, for the final run: add --final to confirm"
        )
    if on_chunks and args.method not in CHUNK_METHODS:
        p.error(
            f"--method {args.method} isn't available on chunks; choose from {sorted(CHUNK_METHODS)}"
        )
    if not on_chunks and args.method not in PARAGRAPH_METHODS:
        p.error(f"--method {args.method} needs --chunking <strategy>")
    if args.rerank and not on_chunks:
        p.error(
            "--rerank works on chunks: use --chunking whole to rerank whole paragraphs"
        )
    return args


def check_strategy(conn: Conn, strategy: str, needs_vector: bool) -> None:
    """Fail early, rather than score an empty or half-embedded strategy."""
    row = conn.execute(
        "SELECT count(*), count(embedding) FROM chunks WHERE strategy = %s", (strategy,)
    ).fetchone()
    total, embedded = (int(row[0]), int(row[1])) if row else (0, 0)
    if total == 0:
        raise SystemExit(
            f"no chunks for strategy {strategy!r}: run build_chunks.py --strategy {strategy}"
        )
    if needs_vector and embedded < total:
        raise SystemExit(
            f"{strategy!r}: only {embedded} of {total} chunks have a vector: "
            f"run embed_chunks.py --strategy {strategy}"
        )


def main() -> None:
    args = parse_args()
    rows = load_split(args.split)
    on_chunks = args.chunking != "paragraphs"
    needs_vector = args.method in NEEDS_VECTOR

    vectors: list[Vec | None] = [None] * len(rows)
    if needs_vector:
        encoded = encode(
            load_model(), [r["question"] for r in rows]
        )  # one batch for all
        vectors = [encoded[i] for i in range(len(rows))]

    reranker: Any = None
    if args.rerank:
        from rerank import load_reranker  # loads a second model: only when asked

        reranker = load_reranker()

    per_question: list[dict[str, Any]] = []
    by_booklet: dict[int, list[float]] = defaultdict(list)
    context_chars: list[int] = []
    search_seconds = 0.0

    with psycopg.connect(os.environ["HEALTH_RAG_DATABASE_URL"]) as conn:
        register_vector(conn)
        if on_chunks:
            check_strategy(conn, args.chunking, needs_vector)

        for row, qv in zip(rows, vectors, strict=True):
            question = row["question"]
            started = time.perf_counter()
            if on_chunks:
                chunks = CHUNK_METHODS[args.method](conn, question, qv, args.chunking)
                texts: dict[int, str] = {}
                if args.rerank:
                    from rerank import rerank

                    texts = chunk_texts(conn, chunks)
                    chunks = rerank(reranker, question, chunks, texts)
                search_seconds += time.perf_counter() - started
                groups = [tuple(Hit(c.booklet, p) for p in c.covers) for c in chunks]
                top5 = chunks[:5]
                texts = texts or chunk_texts(conn, top5)
                context_chars.append(sum(len(texts[c.chunk_id]) for c in top5))
                chunk_record = [[c.chunk_id, c.booklet, list(c.covers)] for c in chunks]
            else:
                hits = PARAGRAPH_METHODS[args.method](conn, question, qv)
                search_seconds += time.perf_counter() - started
                groups = [(h,) for h in hits]
                chunk_record = None

            relevant = {Hit(row["booklet"], p) for p in row["relevant"]}
            scores = {
                "recall_at_5": recall_groups_at_k(groups, relevant, 5),
                "mrr_at_5": mrr_groups_at_k(groups, relevant, 5),
                "recall_at_20": recall_groups_at_k(groups, relevant, 20),
            }
            by_booklet[row["booklet"]].append(scores["recall_at_5"])

            paragraphs: list[
                list[int]
            ] = []  # covered paragraphs in rank order, each once
            for group in groups:
                for h in group:
                    if [h.booklet, h.para_no] not in paragraphs:
                        paragraphs.append([h.booklet, h.para_no])
            record: dict[str, Any] = {
                "id": row["id"],
                "booklet": row["booklet"],
                "relevant": sorted(row["relevant"]),
                "hits": paragraphs,  # show_miss.py reads this
                **scores,
            }
            if chunk_record is not None:
                record["chunks"] = chunk_record
            per_question.append(record)

    notes = args.notes
    if context_chars:
        notes = f"{notes} ctx={round(mean([float(c) for c in context_chars]))}".strip()

    run_id = next_run_id()
    result: dict[str, Any] = {
        "run_id": run_id,
        "date": datetime.now().astimezone().date().isoformat(),  # your local date
        "split": args.split,
        "method": f"{args.method}+rerank" if args.rerank else args.method,
        "chunking": args.chunking,
        "k": 5,
        "n_questions": len(per_question),
        **{
            m: round(mean([q[m] for q in per_question]), 3)
            for m in ("recall_at_5", "mrr_at_5", "recall_at_20")
        },
        "per_booklet_recall_at_5": " ".join(
            f"b{b}={mean(v):.3f}(n={len(v)})" for b, v in sorted(by_booklet.items())
        ),
        "empty_results": sum(1 for q in per_question if not q["hits"]),
        "ms_per_question": round(search_seconds * 1000 / max(len(per_question), 1), 1),
        "notes": notes,
    }
    append_result(result)

    runs_dir = DATA / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    with (runs_dir / f"run_{run_id}.jsonl").open("w", encoding="utf-8") as f:
        for q in per_question:
            f.write(json.dumps(q) + "\n")

    print(
        f"run {run_id} · {result['method']} · {args.chunking} · {args.split} · {len(per_question)} questions\n"
        f"  Recall@5 {result['recall_at_5']:.3f}   MRR@5 {result['mrr_at_5']:.3f}   "
        f"Recall@20 {result['recall_at_20']:.3f}\n"
        f"  by booklet: {result['per_booklet_recall_at_5']}\n"
        f"  empty results: {result['empty_results']}   {result['ms_per_question']} ms per question"
        + (
            f"   context: {notes.rsplit('ctx=', 1)[1]} characters in the top 5"
            if context_chars
            else ""
        )
        + f"\n  per-question hits: data/runs/run_{run_id}.jsonl"
    )


if __name__ == "__main__":
    main()
