"""Build the tuning and held-out question sets from Train.csv.

Usage (from the repo root):
    uv run python capstones/05-health-rag/build_testset.py

Writes data/tuning.jsonl and data/heldout.jsonl. Both are derived from the
licensed dataset, so they live in data/, which git ignores. Never open
heldout.jsonl: it is used once, for the final run.
"""

from __future__ import annotations

import csv
import json
import os
import random
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, TypedDict

import psycopg

DATA = Path(__file__).parent / "data"
LABEL_COLUMN = "Paragraph(s) Number"

# Labels that are wrong in Train.csv, found by checking every label against the database.
# Each fix is by question ID, with the reason, so the correction is visible and reviewable.
LABEL_FIXES: dict[str, tuple[str, str]] = {
    # booklet 6 has 515 paragraphs; 203 and 204 are both on lymphatic filariasis, as the keywords say
    "Q893": ("203204", "203, 204"),
}


class Record(TypedDict):
    id: str
    question: str
    booklet: int
    relevant: list[int]


def parse_label(text: str) -> set[int]:
    """Parse a paragraph label such as "140", "154, 166", "439 - 440" or "12, 14-16".

    Raises:
        ValueError: if the text is empty, a part isn't a number, or a range runs backwards.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("empty label")

    def _parse_num(val: str) -> int:
        try:
            return int(float(val.strip()))
        except ValueError as exc:
            raise ValueError(f"invalid label value: {text!r}") from exc

    labels: set[int] = set()
    for part in cleaned.split(","):
        item = part.strip()
        if not item:
            raise ValueError(f"empty part in label: {text!r}")

        if "-" in item:
            bounds = item.split("-")
            if len(bounds) != 2:
                raise ValueError(f"invalid range: {text!r}")
            start, end = _parse_num(bounds[0]), _parse_num(bounds[1])
            if end < start:
                raise ValueError(f"range ends before it starts: {text!r}")
            labels.update(range(start, end + 1))
        else:
            labels.add(_parse_num(item))

    return labels


def parse_booklet(text: str) -> int:
    """The booklet number from the Reference Document column: "TG Booklet 6" -> 6."""
    match = re.search(r"(\d+)\s*$", text)
    if not match:
        raise ValueError(f"no booklet number in: {text!r}")
    return int(match.group(1))


def normalise(question: str) -> str:
    """The grouping key: lower case, stripped, single spaces."""
    return " ".join(question.lower().split())


def find_train_csv(root: Path) -> Path:
    found = next(root.rglob("Train.csv"), None)
    if found is None:
        raise FileNotFoundError(f"Train.csv not found under {root}")
    return found


def load_rows(path: Path) -> tuple[list[Record], int]:
    """Read Train.csv. Returns (records, rows skipped for an empty label).

    Only an empty label is skipped. Any other bad label raises, so a parsing
    bug can't silently remove questions from the test set.
    """
    records: list[Record] = []
    skipped = 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        for line_no, row in enumerate(
            csv.DictReader(f), start=2
        ):  # line 1 is the header
            raw_label = (row.get(LABEL_COLUMN) or "").strip()
            fix = LABEL_FIXES.get(row.get("ID", ""))
            if fix is not None:
                wrong, right = fix
                if (
                    raw_label != wrong
                ):  # the file changed: re-check the fix rather than apply it blindly
                    raise ValueError(
                        f"{row['ID']}: expected label {wrong!r} to fix, found {raw_label!r}"
                    )
                raw_label = right
            if not raw_label:
                skipped += 1
                continue
            try:
                relevant = sorted(parse_label(raw_label))
                booklet = parse_booklet(row["Reference Document"])
            except (ValueError, KeyError) as exc:
                raise ValueError(f"Train.csv line {line_no}: {exc}") from exc
            records.append(
                {
                    "id": row["ID"],
                    "question": row["Question Text"],
                    "booklet": booklet,
                    "relevant": relevant,
                }
            )
    return records, skipped


def split(
    rows: list[Record], n_heldout: int = 150, seed: int = 42
) -> tuple[list[Record], list[Record]]:
    """Split into (heldout, tuning), keeping every copy of a question on one side."""
    grouped: dict[str, list[Record]] = defaultdict(list)
    for row in rows:
        grouped[normalise(row["question"])].append(row)

    keys = sorted(grouped)  # a fixed starting order, so the shuffle is repeatable
    random.Random(seed).shuffle(keys)

    heldout: list[Record] = []
    tuning: list[Record] = []
    for key in keys:
        group = grouped[key]
        if len(heldout) + len(group) <= n_heldout:
            heldout.extend(group)
        else:
            tuning.extend(group)
    return heldout, tuning


def check_against_db(
    conn: psycopg.Connection[Any], rows: list[Record]
) -> tuple[list[tuple[int, int]], list[tuple[int, int]]]:
    """Returns (labels missing from paragraphs, labels pointing at an empty paragraph)."""
    existing: dict[tuple[int, int], bool] = {
        (int(b), int(p)): bool(t)
        for b, p, t in conn.execute(
            "SELECT booklet, para_no, text <> '' FROM paragraphs"
        )
    }
    labels = {(r["booklet"], p) for r in rows for p in r["relevant"]}
    missing = sorted(lab for lab in labels if lab not in existing)
    empty = sorted(lab for lab in labels if existing.get(lab) is False)
    return missing, empty


def write_jsonl(path: Path, rows: list[Record]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def booklet_shares(rows: list[Record]) -> str:
    counts = Counter(r["booklet"] for r in rows)
    return "  ".join(
        f"b{b}={counts[b]} ({counts[b] / len(rows):.0%})" for b in sorted(counts)
    )


def main() -> None:
    rows, skipped = load_rows(find_train_csv(DATA))
    heldout, tuning = split(rows)

    with psycopg.connect(os.environ["HEALTH_RAG_DATABASE_URL"]) as conn:
        missing, empty = check_against_db(conn, rows)
    if missing:
        raise SystemExit(
            f"{len(missing)} labelled paragraphs don't exist, e.g. {missing[:5]}"
        )

    def unanswerable(subset: list[Record]) -> int:
        """Questions whose every labelled paragraph is empty, so retrieval can never find them."""
        empty_set = set(empty)
        return sum(
            all((r["booklet"], p) in empty_set for p in r["relevant"]) for r in subset
        )

    overlap = {normalise(r["question"]) for r in heldout} & {
        normalise(r["question"]) for r in tuning
    }

    write_jsonl(DATA / "tuning.jsonl", tuning)
    write_jsonl(DATA / "heldout.jsonl", heldout)

    print(
        f"rows kept: {len(rows)}, skipped (empty label): {skipped}, labels corrected: {len(LABEL_FIXES)}"
    )
    print(f"tuning: {len(tuning)}, held-out: {len(heldout)}")
    print(f"questions on both sides: {len(overlap)} (must be 0)")
    print(f"labelled paragraphs not in the database: {len(missing)} (must be 0)")
    print(f"labelled paragraphs that are empty (images): {len(empty)}")
    print(
        f"tuning questions that can never be found (all labels empty): {unanswerable(tuning)}"
    )
    print(f"tuning by booklet:   {booklet_shares(tuning)}")
    print(f"held-out by booklet: {booklet_shares(heldout)}")


if __name__ == "__main__":
    main()
