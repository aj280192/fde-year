"""Print results.csv as a markdown table, for the capstone README.

Usage (from capstones/05-health-rag):
    uv run python results_table.py > /tmp/table.md

"Kept?" comes from the notes: write "kept" or "dropped" in a run's --notes.
"""

from __future__ import annotations

import csv
from pathlib import Path

RESULTS = Path(__file__).parent / "results.csv"


def kept(notes: str) -> str:
    n = notes.lower()
    if "final" in n:
        return "**final**"
    if "dropped" in n:
        return "no"
    if "kept" in n:
        return "yes"
    if "baseline" in n or "check" in n:
        return "baseline"
    return ""


def main() -> None:
    with RESULTS.open(newline="") as f:
        rows = list(csv.DictReader(f))
    print(
        "| Run | Split | Method | Chunking | Recall@5 | MRR@5 | Recall@20 | ms/question | Kept? | Notes |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for r in rows:
        print(
            f"| {r['run_id']} | {r['split']} | {r['method']} | {r['chunking']} | "
            f"{float(r['recall_at_5']):.3f} | {float(r['mrr_at_5']):.3f} | {float(r['recall_at_20']):.3f} | "
            f"{r['ms_per_question']} | {kept(r['notes'])} | {r['notes']} |"
        )


if __name__ == "__main__":
    main()
