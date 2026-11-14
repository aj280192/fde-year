"""Choose ABSTAIN_THRESHOLD from data, without calling the language model.

    uv run python calibrate.py

For every tuning question (answerable: each has a labelled paragraph) and every
line of unanswerable.txt (questions the booklets can't answer), run retrieval
exactly as rag.py does and record the top reranker score. Then show both
distributions, what each candidate threshold would keep and reject, and the
highest threshold that still keeps TARGET of the answerable questions.

The held-out questions are never used. Raw scores go to data/calibration.csv
(ignored by git: it holds question ids from the dataset).
"""

from __future__ import annotations

import csv
import json
import math
import os
import statistics
from pathlib import Path
from typing import Any

import psycopg
from config import ABSTAIN_THRESHOLD
from embed import load_model
from pgvector.psycopg import register_vector
from rag import retrieve_sources
from rerank import load_reranker

HERE = Path(__file__).parent
DATA = HERE / "data"
TARGET = 0.95  # keep at least this share of answerable questions
STEP = 0.5  # spacing of the candidate thresholds


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def frange(lo: float, hi: float, step: float) -> list[float]:
    """lo, lo + step, … up to hi (range() only does integers)."""
    return [round(lo + i * step, 6) for i in range(round((hi - lo) / step) + 1)]


def keeps(scores: list[float], t: float) -> float:
    """Share answered at threshold t: the same rule as check_retrieval (below t abstains)."""
    return sum(s >= t for s in scores) / len(scores)


def rejects(scores: list[float], t: float) -> int:
    return sum(s < t for s in scores)


def summarise(name: str, scores: list[float]) -> None:
    p5 = (
        statistics.quantiles(scores, n=20, method="inclusive")[0]
        if len(scores) >= 2
        else scores[0]
    )
    print(
        f"{name:<13} n={len(scores):<4} min {min(scores):7.2f}   p5 {p5:7.2f}   "
        f"median {statistics.median(scores):7.2f}   max {max(scores):7.2f}"
    )


def main() -> None:
    # 1 · Load everything once.
    embedder, reranker = load_model(), load_reranker()
    conn = psycopg.connect(os.environ["HEALTH_RAG_DATABASE_URL"])
    register_vector(conn)

    # 2 · The two groups.
    answerable = [
        (str(r["id"]), str(r["question"])) for r in load_jsonl(DATA / "tuning.jsonl")
    ]
    lines = (HERE / "unanswerable.txt").read_text(encoding="utf-8").splitlines()
    unanswerable = [
        (f"U{i}", q.strip()) for i, q in enumerate(lines, start=1) if q.strip()
    ]
    if not unanswerable:
        raise SystemExit(
            "unanswerable.txt is empty: write the ten questions first (step 6.1)"
        )

    # 3 · Score every question: retrieval only, exactly as rag.py retrieves.
    rows: list[tuple[str, str, str, float | None]] = []
    everything = [("answerable", i, q) for i, q in answerable] + [
        ("unanswerable", i, q) for i, q in unanswerable
    ]
    for n, (group, qid, question) in enumerate(everything, start=1):
        sources = retrieve_sources(conn, embedder, reranker, question)
        rows.append((group, qid, question, sources[0].score if sources else None))
        if n % 100 == 0:
            print(f"  scored {n}/{len(everything)}")
    conn.close()

    found = [(g, i, q, s) for g, i, q, s in rows if s is not None]
    nothing = [qid for _, qid, _, score in rows if score is None]
    if nothing:
        print(
            f"retrieval returned nothing for {len(nothing)} questions: {nothing[:10]}"
        )
    ans = [s for g, _, _, s in found if g == "answerable"]
    una = [s for g, _, _, s in found if g == "unanswerable"]

    # 4 · Each group's distribution, and every unanswerable question.
    print()
    summarise("ANSWERABLE", ans)
    summarise("UNANSWERABLE", una)
    print("\nunanswerable questions, lowest score first:")
    for _, qid, question, s in sorted(
        (r for r in found if r[0] == "unanswerable"), key=lambda r: r[3]
    ):
        print(f"  {s:7.2f}  {qid:<4} {question}")

    # 5 · What each candidate threshold would do.
    lo, hi = math.floor(min(ans + una)), math.ceil(max(ans + una))
    thresholds = frange(lo, hi, STEP)
    print(
        f"\n{'threshold':>9}   {'answerable kept':>15}   {'unanswerable rejected':>21}"
    )
    for t in thresholds:
        marker = "   <- current" if math.isclose(t, ABSTAIN_THRESHOLD) else ""
        print(
            f"{t:9.1f}   {keeps(ans, t):15.1%}   {rejects(una, t):>13} of {len(una)}{marker}"
        )

    # 6 · The rule: the highest threshold that keeps at least TARGET of answerable questions.
    ok = [t for t in thresholds if keeps(ans, t) >= TARGET]
    if ok:
        best = max(ok)
        print(
            f"\nsuggested ABSTAIN_THRESHOLD = {best}  "
            f"(keeps {keeps(ans, best):.1%} of answerable, rejects {rejects(una, best)} of {len(una)} unanswerable)"
        )
    else:
        print(f"\nno threshold in range keeps {TARGET:.0%} of answerable questions")

    # 7 · Raw scores, for later (data/ is ignored by git).
    out = DATA / "calibration.csv"
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["group", "id", "top_score"])
        for g, qid, _, s in rows:
            w.writerow([g, qid, "" if s is None else f"{s:.4f}"])
    print(f"raw scores: {out.relative_to(HERE)}")


if __name__ == "__main__":
    main()
