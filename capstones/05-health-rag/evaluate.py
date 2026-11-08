"""Score one retrieval method on the tuning questions, and record the run.

Usage (from capstones/05-health-rag):
    uv run python evaluate.py --method hybrid --notes "RRF k=60, top 50 each"

Each run appends one row to results.csv (numbers only, safe to commit) and
writes every question's hits to data/runs/run_<id>.jsonl (ignored by git),
for reading the misses.

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
from metrics import mean, mrr_at_k, recall_at_k
from numpy.typing import NDArray
from pgvector.psycopg import register_vector
from retrieve import Hit, hybrid, keyword, keyword_all, keyword_norm, vector

HERE = Path(__file__).parent
DATA = HERE / "data"
RESULTS = HERE / "results.csv"
POOL = 20  # every method returns its top 20; the metrics read the top 5 and 20

Vec = NDArray[np.float32]
Retriever = Callable[[psycopg.Connection[Any], str, Vec | None, int], list[Hit]]


def _need_vec(qv: Vec | None) -> Vec:
    if qv is None:
        raise RuntimeError("this method needs the question's vector")
    return qv


METHODS: dict[str, Retriever] = {
    "keyword_all": lambda c, q, qv, k: keyword_all(c, q, k),
    "keyword": lambda c, q, qv, k: keyword(c, q, k),
    "keyword_norm": lambda c, q, qv, k: keyword_norm(c, q, k),
    "vector": lambda c, q, qv, k: vector(c, _need_vec(qv), k),
    "hybrid": lambda c, q, qv, k: hybrid(c, q, _need_vec(qv), k),
}
NEEDS_VECTOR = {"vector", "hybrid"}

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
    path = DATA / f"{name}.jsonl"
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def next_run_id() -> int:
    if not RESULTS.exists():
        return 1
    with RESULTS.open(newline="") as f:
        ids = [int(r["run_id"]) for r in csv.DictReader(f)]
    return max(ids, default=0) + 1


def append_result(row: dict[str, Any]) -> None:
    new_file = not RESULTS.exists()
    with RESULTS.open("a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        if new_file:
            writer.writeheader()
        writer.writerow(row)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--method", required=True, choices=sorted(METHODS))
    p.add_argument("--chunking", default="paragraphs")
    p.add_argument("--split", default="tuning", choices=["tuning", "heldout"])
    p.add_argument(
        "--final", action="store_true", help="required to run on the held-out split"
    )
    p.add_argument("--notes", default="")
    args = p.parse_args()
    if args.split == "heldout" and not args.final:
        p.error(
            "the held-out split is used once, for the final run: add --final to confirm"
        )
    return args


def main() -> None:
    args = parse_args()
    rows = load_split(args.split)
    retrieve = METHODS[args.method]

    vectors: list[Vec | None] = [None] * len(rows)
    if args.method in NEEDS_VECTOR:
        model = load_model()
        encoded = encode(
            model, [r["question"] for r in rows]
        )  # one batch for all questions
        vectors = [encoded[i] for i in range(len(rows))]

    per_question: list[dict[str, Any]] = []
    by_booklet: dict[int, list[float]] = defaultdict(list)
    started = time.perf_counter()

    with psycopg.connect(os.environ["HEALTH_RAG_DATABASE_URL"]) as conn:
        register_vector(conn)
        for row, qv in zip(rows, vectors, strict=True):
            hits = retrieve(conn, row["question"], qv, POOL)
            relevant = {Hit(row["booklet"], p) for p in row["relevant"]}
            scores = {
                "recall_at_5": recall_at_k(hits, relevant, 5),
                "mrr_at_5": mrr_at_k(hits, relevant, 5),
                "recall_at_20": recall_at_k(hits, relevant, 20),
            }
            by_booklet[row["booklet"]].append(scores["recall_at_5"])
            per_question.append(
                {
                    "id": row["id"],
                    "booklet": row["booklet"],
                    "relevant": sorted(row["relevant"]),
                    "hits": [[h.booklet, h.para_no] for h in hits],
                    **scores,
                }
            )

    elapsed_ms = (time.perf_counter() - started) * 1000
    run_id = next_run_id()
    result: dict[str, Any] = {
        "run_id": run_id,
        "date": datetime.now().astimezone().date().isoformat(),  # your local date
        "split": args.split,
        "method": args.method,
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
        "ms_per_question": round(elapsed_ms / max(len(per_question), 1), 1),
        "notes": args.notes,
    }
    append_result(result)

    runs_dir = DATA / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)
    with (runs_dir / f"run_{run_id}.jsonl").open("w", encoding="utf-8") as f:
        for q in per_question:
            f.write(json.dumps(q) + "\n")

    print(
        f"run {run_id} · {args.method} · {args.chunking} · {args.split} · {len(per_question)} questions\n"
        f"  Recall@5 {result['recall_at_5']:.3f}   MRR@5 {result['mrr_at_5']:.3f}   "
        f"Recall@20 {result['recall_at_20']:.3f}\n"
        f"  by booklet: {result['per_booklet_recall_at_5']}\n"
        f"  empty results: {result['empty_results']}   {result['ms_per_question']} ms per question\n"
        f"  per-question hits: data/runs/run_{run_id}.jsonl"
    )


if __name__ == "__main__":
    main()
