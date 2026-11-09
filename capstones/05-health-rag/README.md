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

## Reading the data (8 to 9 Nov 2026)

Before changing the chunking, I read a random sample of paragraphs and a set of misses, to see why
retrieval fails. Only ids, counts and lengths are recorded here; no question or paragraph text, because
of the dataset's licence.

### 50 random paragraphs (`setseed(0.7)`)

| Kind | Count | What it looks like | Examples (booklet, paragraph) |
| --- | --- | --- | --- |
| Depends on context | 20 | a list item, a checklist question or an instruction that never names its topic; 3 of them are half a sentence, cut where a line break was | (4,389) (3,755) (2,745) (3,1138) |
| Self-contained | 10 | a full sentence or passage that names its own topic | (1,76) (3,1262) (2,190) |
| Heading | 10 | a short section or disease title, often numbered like "8.6.6 …" | (4,383) (3,528) (6,242) |
| Contents entry | 5 | a heading followed by a page number: a line from a table of contents | (6,65) (4,72) (2,57) |
| Long table or form | 3 | rows flattened into one paragraph, 766 to 5,496 characters | (4,92) (6,183) (6,404) |
| Form field or reference | 2 | a blank to fill in, or a document title | (3,1961) (3,2063) |

Only **1 in 5** paragraphs makes sense on its own. Across the whole table:

- **227 paragraphs start in lower case:** they're the second half of a sentence that the source split
  across two paragraphs.
- **About 256 look like contents entries** (a number, a title, a page number). 95 of them are in booklet 3.

| Booklet | Paragraphs | Heading-like | Over 1,000 characters | Median length |
| --- | --- | --- | --- | --- |
| 1 | 695 | 18% | 1.6% | 89 |
| 2 | 941 | 15% | 2.0% | 91 |
| 3 | 2,064 | 17% | 0.5% | 72 |
| 4 | 740 | 19% | 1.8% | 76 |
| 5 | 271 | 26% | 1.1% | 76 |
| 6 | 515 | 28% | **22.3%** | 65 |

**Booklet 3** (paragraphs 400 to 425): a list of annex titles, followed by the annexes themselves, so each
title appears twice; then short list items under one heading. Many paragraphs look alike, and few name
their subject.

### Misses

From run 3 (`keyword_norm`, any word, rank divided by length), which misses 439 of 596 tuning questions
in the top 5. I read 5, spread across booklets:

| Question | Booklet | Right paragraph's rank | The labelled paragraph | Cause |
| --- | --- | --- | --- | --- |
| Q798 | 6 | not in top 20 | a 7-character disease heading | label is a heading |
| Q516 | 6 | not in top 20 | a contents entry with a page number | label is a heading |
| Q336 | 3 | not in top 20 | a numbered section heading | label is a heading |
| Q328 | 3 | not in top 20 | a one-line checklist question | different words |
| Q83 | 2 | 18 | a self-contained 319-character passage | crowded out by long tables |

In **all 5**, the top 3 results were **huge table paragraphs** from other topics (4,000 to 18,600
characters), not the paragraphs near the answer. Counting that across every tuning question:

- **Paragraphs over 1,000 characters are 3% of the table, but take 85% of all top-5 slots.**
- **One paragraph, (1,309) at 16,206 characters, is in the top 5 for 331 of 596 questions.** The next
  five are (4,410), (4,412), (6,228), (6,180) and (6,308), each in the top 5 for 150 to 288 questions.
  They contain nearly every word, so they match nearly every question.
- They can't simply be removed: **258 of the 1,251 labelled paragraphs are over 1,000 characters**, so
  long paragraphs are often the right answer.

**Labels on headings:** 188 labelled paragraphs (15%) are under 40 characters. For 34 questions (6%),
*every* label is a short heading; Recall@5 on those is 0.029, against 0.238 on the rest. The labeller
seems to have pointed at a section's heading when the answer is the section under it.

### Prediction for Monday

**Change 2, splitting long paragraphs, will help most: about +8 points of Recall@5 for keyword search,
most in booklets 2 and 3.** Most misses come from a few huge tables crowding out the top 5. Split into
800-character pieces, each piece matches only the questions about its own rows.

Change 1, attaching headings, should help the questions labelled on a heading. **The heading's paragraph
must count as covered by the chunk it's attached to** (`para_from` = the heading), or those 34
questions still can't score. I expect a smaller gain, about +2 to +3 points.

Vector search should suffer less from the big tables, because the model reads only their first 256
tokens. Hybrid misses (run 5) still to read, to check this.
**Checked on 10 Nov (runs 8, 11 and 14):** right about splitting, and it helped more than predicted:
+12.3 points for keyword search, not +8, and booklet 3 gained most. Headings alone gained 5.8, more than
predicted, but they paid off most on top of splitting (+8.4 more). Since `covers` is a list, a chunk
covers its heading's paragraph and its own, not the paragraphs in between.
For hybrid search the order was different: splitting added nothing (run 10), and headings added most
(+4.0, run 13). The final setup (run 19) reached Recall@5 0.649 on tuning and 0.691 held-out (run 20).

## Part 2 · Chunking, reranking and results (week 5)

| File | Does |
| --- | --- |
| `schema_chunks.sql` | the `chunks` table: one set of rows per strategy, each chunk with `covers` (the paragraphs it stands for), a generated `tsvector` (plain and heading-weighted) and a `vector(384)` |
| `build_chunks.py` | builds one strategy's chunks from `paragraphs`: `whole`, `split`, `headings`, `headings_split`, `heading_meta` |
| `embed_chunks.py` | embeds one strategy's chunks; reports how many still exceed 256 tokens |
| `retrieve_chunks.py` | keyword, vector and hybrid search over one strategy's chunks |
| `rerank.py` | re-orders the top 20 with a cross-encoder |
| `build_testset.py` | the tuning and held-out question sets from `Train.csv` (written to `data/`, not committed) |
| `metrics.py` | Recall@k and MRR@k, for paragraphs and for chunks covering several paragraphs |
| `evaluate.py` | scores one setup and appends a row to `results.csv` |
| `run_experiments.sh` | every chunking run, in a fixed order |
| `results_table.py` | prints `results.csv` as the table below |
| `snippets_q1.py` | `chunk_documents`, `build_index` and `retrieve` for the final configuration |
| `show_miss.py` | prints one question's labelled paragraphs and top hits from a run (terminal only) |

```bash
cd capstones/05-health-rag
export HEALTH_RAG_DATABASE_URL=postgresql://postgres:dev@localhost:5432/health_rag
uv run python build_testset.py                 # data/tuning.jsonl and data/heldout.jsonl
uv run python embed.py                         # paragraph vectors
bash run_experiments.sh check                  # runs 6 and 7
bash run_experiments.sh chunks hybrid_norm     # runs 8 to 18 (or: chunks hybrid)
```

### Results (tuning set: 596 questions; held-out: 150, run once)

Every run is a row of `results.csv`. Recall@5 and MRR@5 are cut at the top 5 chunks; a difference under
2 points (about 12 questions) counts as no change. The design and the reasoning are in
[Q1_Retrieval_Design.md](Q1_Retrieval_Design.md).

| Run | Split | Method | Chunking | Recall@5 | MRR@5 | Recall@20 | ms/question | Kept? | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | tuning | keyword_all | paragraphs | 0.144 | 0.161 | 0.145 | 0.2 | no | every word must match: no result for 428 questions |
| 2 | tuning | keyword | paragraphs | 0.168 | 0.117 | 0.330 | 3.1 | no | any word |
| 3 | tuning | keyword_norm | paragraphs | 0.226 | 0.156 | 0.474 | 3.2 | yes | any word, rank divided by length |
| 4 | tuning | vector | paragraphs | 0.473 | 0.390 | 0.621 | 1.9 | baseline | MiniLM, cosine |
| 5 | tuning | hybrid | paragraphs | 0.531 | 0.468 | 0.654 | 5.0 | no | RRF k=60, top 50 each, keyword any word |
| 6 | tuning | hybrid_norm | paragraphs | 0.558 | 0.504 | 0.679 | 5.1 | yes | RRF on keyword_norm + vector |
| 7 | tuning | hybrid | whole | 0.531 | 0.468 | 0.654 | 7.5 | check | chunk path on whole paragraphs: equals run 5 |
| 8 | tuning | keyword_norm | split | 0.349 | 0.288 | 0.546 | 7.4 | | ctx 3,081 |
| 9 | tuning | vector | split | 0.516 | 0.440 | 0.662 | 4.1 | | ctx 1,385 |
| 10 | tuning | hybrid_norm | split | 0.558 | 0.492 | 0.680 | 11.7 | no | hybrid unchanged; ctx 2,186 |
| 11 | tuning | keyword_norm | headings | 0.284 | 0.195 | 0.539 | 7.0 | | ctx 41,302 |
| 12 | tuning | vector | headings | 0.473 | 0.378 | 0.646 | 3.3 | | ctx 2,486 |
| 13 | tuning | hybrid_norm | headings | 0.598 | 0.548 | 0.714 | 7.7 | yes | +4.0; ctx 9,274 |
| 14 | tuning | keyword_norm | headings_split | 0.433 | 0.357 | 0.605 | 5.0 | | ctx 3,086 |
| 15 | tuning | vector | headings_split | 0.529 | 0.440 | 0.684 | 4.0 | | ctx 1,532 |
| 16 | tuning | hybrid_norm | headings_split | 0.590 | 0.539 | 0.724 | 9.3 | **yes** | ties run 13; highest Recall@20, a quarter of the context (2,352) |
| 17 | tuning | keyword_weighted | heading_meta | 0.197 | 0.156 | 0.353 | 4.3 | no | heading weighted A, text D |
| 18 | tuning | hybrid_weighted | heading_meta | 0.466 | 0.385 | 0.648 | 7.5 | no | heading weighted A, text D |
| 19 | tuning | hybrid_norm+rerank | headings_split | 0.649 | 0.650 | 0.724 | 36.7 | **yes** | cross-encoder over top 20 |
| 20 | heldout | hybrid_norm+rerank | headings_split | **0.691** | **0.668** | **0.752** | 36.0 | **final** | run once |

**Final setup:** headings + split chunks, hybrid on the length-penalised keyword list and vectors, reranked by
a cross-encoder (run 19 on tuning, run 20 held out).