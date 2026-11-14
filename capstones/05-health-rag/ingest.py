"""Load the six guideline booklets into the `paragraphs` table.

    export HEALTH_RAG_DATABASE_URL=postgresql://postgres:dev@localhost:5432/health_rag
    uv run python capstones/05-health-rag/load.py

Safe to run more than once: an existing (booklet, para_no) has its text replaced, nothing is
duplicated. The files stay in data/, which git ignores (the licence forbids sharing them).
"""

import os
import re
from pathlib import Path

import openpyxl
import psycopg

DATA = Path(__file__).parent / "data"
BOOKLETS = range(1, 7)

# Found by reading the files (5 Nov 2026):
NONCHARACTER = "﷐"  # stands where the source document had a line break
IMAGE_MARK = "￼"  # stands where the source document had a picture
SPACES = re.compile(r"\s+")


def clean(text: object) -> str:
    """Text fit to search: no placeholder characters, single spaces, no padding."""
    if text is None:
        return ""
    value = str(text).replace(NONCHARACTER, " ").replace(IMAGE_MARK, " ")
    return SPACES.sub(" ", value).strip()


def booklet_file(booklet: int) -> Path:
    """The booklet's .xlsx file in data/ (or a folder inside it), however spaces or case vary."""
    wanted = re.compile(rf"booklet[\s_-]*{booklet}\.xlsx$", re.IGNORECASE)
    matches = sorted(p for p in DATA.rglob("*.xlsx") if wanted.search(p.name))
    if len(matches) != 1:
        found = sorted(p.name for p in DATA.rglob("*.xlsx"))
        raise FileNotFoundError(
            f"expected one file for booklet {booklet} in {DATA}, found {len(matches)}; "
            f".xlsx files there: {found}"
        )
    return matches[0]


def read_booklet(booklet: int) -> list[tuple[int, int, str]]:
    """(booklet, paragraph number, cleaned text) for every numbered row.

    The sheets have no header row: column A is the paragraph number, column B the text.
    Booklet 2 writes numbers as 1.0, 2.0, ... and ends with 59 rows that have no number.
    """
    sheet = openpyxl.load_workbook(booklet_file(booklet), read_only=True).worksheets[0]
    rows: list[tuple[int, int, str]] = []
    for number, text, *_ in sheet.iter_rows(values_only=True):
        if number is None:
            continue
        rows.append((booklet, int(float(str(number))), clean(text)))
    return rows


UPSERT = """
INSERT INTO paragraphs (booklet, para_no, text) VALUES (%s, %s, %s)
ON CONFLICT (booklet, para_no) DO UPDATE SET text = EXCLUDED.text
"""


def main() -> None:
    url = os.environ["HEALTH_RAG_DATABASE_URL"]
    all_rows = [row for booklet in BOOKLETS for row in read_booklet(booklet)]
    with psycopg.connect(url) as conn, conn.cursor() as cur:
        cur.executemany(UPSERT, all_rows)
        conn.commit()
        cur.execute(
            "SELECT booklet, count(*) FROM paragraphs GROUP BY booklet ORDER BY booklet"
        )
        for booklet, count in cur.fetchall():
            print(f"booklet {booklet}: {count} paragraphs")
        cur.execute("SELECT count(*) FROM paragraphs WHERE text = ''")
        empty = cur.fetchone()
        print(f"empty after cleaning (images only): {empty[0] if empty else 0}")


if __name__ == "__main__":
    main()
