"""Print one question, its labelled paragraphs, and the top hits from a run.

uv run python show_miss.py 5 Q1040          # run 5, question Q1040
uv run python show_miss.py 5 --list 3       # misses in run 5, booklet 3
"""

import json
import os
import sys
from pathlib import Path

import psycopg

DATA = Path(__file__).parent / "data"


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def main() -> None:
    run_id, arg = sys.argv[1], sys.argv[2]
    run = load(DATA / "runs" / f"run_{run_id}.jsonl")

    if arg == "--list":
        booklet = int(sys.argv[3])
        ids = [
            q["id"] for q in run if q["recall_at_5"] == 0 and q["booklet"] == booklet
        ]
        print(f"{len(ids)} misses in booklet {booklet}:", " ".join(ids[:15]))
        return

    q = next(q for q in run if q["id"] == arg)
    question = next(
        r["question"] for r in load(DATA / "tuning.jsonl") if r["id"] == arg
    )

    with psycopg.connect(os.environ["HEALTH_RAG_DATABASE_URL"]) as conn:

        def text(b: int, p: int) -> str:
            row = conn.execute(
                "SELECT text FROM paragraphs WHERE booklet = %s AND para_no = %s",
                (b, p),
            ).fetchone()
            return row[0] if row else "(missing)"

        print(f"QUESTION: {question}\n")
        for p in q["relevant"]:
            t = text(q["booklet"], p)
            print(f"LABELLED ({q['booklet']},{p}) · {len(t)} chars\n  {t[:400]}\n")
        rank_of = {tuple(h): i for i, h in enumerate(q["hits"], start=1)}
        found = [rank_of.get((q["booklet"], p)) for p in q["relevant"]]
        print(
            f"labelled paragraph ranks in the top 20: {found}  (None = not in the top 20)\n"
        )
        for i, (b, p) in enumerate(q["hits"][:3], start=1):
            t = text(b, p)
            print(f"HIT {i} ({b},{p}) · {len(t)} chars\n  {t[:250]}\n")


if __name__ == "__main__":
    main()
