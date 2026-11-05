# Health RAG · questions on the Malawi health guidelines

A retrieval-augmented assistant over six technical-guideline booklets, built in parts alongside the
main plan (weeks 5 to 24).

**Data:** the Malawi health guidelines dataset on Zindi, under
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/). The files are **not** in this
repository: download them from Zindi into `data/`, which git ignores. No chunks, embeddings or
database dumps are published either.

## Part 1 · Storage and first retrieval (week 5)

| File | Does |
| --- | --- |
| `schema.sql` | the `paragraphs` table: booklet, paragraph number, cleaned text, a generated `tsvector` with a GIN index, and an empty `vector(384)` column |
| `load.py` | reads the six booklets and upserts every numbered paragraph; safe to run again |

```bash
docker exec -it pg psql -U postgres -c "CREATE DATABASE health_rag;"
docker exec -i pg psql -U postgres -d health_rag < capstones/05-health-rag/schema.sql
export HEALTH_RAG_DATABASE_URL=postgresql://postgres:dev@localhost:5432/health_rag
uv run python capstones/05-health-rag/load.py
```

### What the source files look like (found 5 Nov 2026)

- Two columns, **no header row**: paragraph number, then text. Numbers restart at 1 in each booklet,
  so a paragraph is identified by **(booklet, number)**, which is the table's primary key.
- Booklet 2 writes its numbers as `1.0`, `2.0`, … and ends with 59 rows that have no number.
- `U+FDD0` appears where the original had a line break (257 paragraphs), and `U+FFFC` where it had
  an image. Both are removed; **71 paragraphs are empty after cleaning** (images only). They're kept,
  because a label could point at one.
- Lengths range from 1 to 18,747 characters; most are 70 to 90. The longest are tables. This is the
  chunking decision for Saturday: the embedding model reads only about the first 256 tokens.

| Booklet | 1 | 2 | 3 | 4 | 5 | 6 | Total |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Paragraphs | 695 | 941 | 2,064 | 740 | 271 | 515 | **5,226** |

### First keyword search

```sql
SELECT booklet, para_no, ts_rank(tsv, q) AS rank, left(text, 70)
FROM paragraphs, plainto_tsquery('english', 'anthrax specimen collection') AS q
WHERE tsv @@ q ORDER BY rank DESC LIMIT 5;
```

`Train.csv` labels the Anthrax specimen question with **booklet 6, paragraph 140**. This query
returns it **first**, but returns only 2 rows in total: `plainto_tsquery` requires **every** word to
match, which is precise but misses paragraphs that use different words. That trade-off, between
keyword precision and the recall of vector search, is what the hybrid query (step 6) and
Saturday's Recall@5 measure.