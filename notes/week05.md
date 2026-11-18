# Week 5 · 2 to 8 November 2026 · Data and SQL, and retrieval you can measure

Two halves: the task API moved onto Postgres, and the first measured retrieval for the health guidelines assistant. The full retrieval write-up is [Q1_Retrieval_Design.md](../capstones/05-health-rag/Q1_Retrieval_Design.md); the database work is in [labs/week05](../labs/week05) and its [DESIGN.md](../labs/week05/DESIGN.md).

## 1 · The task API on Postgres

| What | Result |
| --- | --- |
| Schema | `tenants`, `tasks`, `runs`, `tool_calls`, `idempotency_keys`, built with Alembic migrations (never `create_all`) |
| Repository | a Postgres repository that passes the **same** tests as the in-memory one, so the service code didn't change |
| Index lab, 1 million tasks | list query 28.2 → 0.12 ms with a composite index (235× faster); count of active tasks 28.6 → 0.69 ms with a partial index (42× faster). The partial index is 744 kB against 55 MB for a full one |
| Lost update | reproduced with two `psql` sessions, then prevented with `SELECT ... FOR UPDATE`. It only helps when the read, the check and the write are **one transaction**; in the API they aren't yet (DESIGN.md section 14, row 6) |
| Claiming work | `FOR UPDATE SKIP LOCKED`: two workers never get the same task. Reused in capstone 3 |

**What I'd tell someone else**

- An index is judged by `EXPLAIN (ANALYZE, BUFFERS)`, not by whether it exists. Look for the scan type and the row estimate.
- A partial index is small because it holds only the rows the query wants. It's only used when the query's `WHERE` implies the index's.
- Time zones: the repository converts every time to UTC on the way in and out. Three tests failed on Postgres until it did, because the server returned its own zone.
- A lock doesn't fix a race if the check happens outside it.

## 2 · Retrieval for the health assistant

The numbers below are from [Q1_Retrieval_Design.md](../capstones/05-health-rag/Q1_Retrieval_Design.md); each is a row of `capstones/05-health-rag/results.csv`.

| Step | Recall@5 | MRR@5 |
| --- | --- | --- |
| keyword, every word must match (run 1) | 0.144 | 0.161 |
| vector, all-MiniLM-L6-v2 (run 4) | 0.473 | 0.390 |
| hybrid, reciprocal rank fusion (run 5) | 0.531 | 0.468 |
| hybrid with the length-penalised keyword list (run 6) | 0.558 | 0.504 |
| + headings on each paragraph, long ones split (run 16) | 0.590 | 0.539 |
| + cross-encoder reranker over the top 20 (run 19, **final**) | **0.649** | **0.650** |
| held-out, 150 questions, run once (run 20) | 0.691 | 0.668 |

**What I'd tell someone else**

- Build the test set first, split it by question text, fix the seed, and open the held-out set once.
- Change one thing at a time, and treat a gain under 2 points as noise.
- Chunking mattered more than the search method: splitting the 16,000-character tables cut the text sent to the model from about 41,600 characters to 3,100.
- An idea that sounds good can hurt: the heading as weighted metadata dropped hybrid by 9.2 points.
- Hybrid beat vector even though the keyword list is weak alone, because the two lists find different paragraphs.

## 3 · Open items from this week

- DESIGN.md row 6: make the cancel/complete race safe (a conditional update, or one transaction across the service call).
- Retrieval is measured, but answers aren't: faithfulness and citation accuracy need a judge (week 21).
- Table rows, each with its header, is the next chunking idea to test.