# Q1 · Retrieval design for the health guidelines assistant

**Status:** draft, 9 Nov 2026. Sections marked ⏳ are filled in after Monday's chunking and reranker runs.
Every number points at a row of `results.csv` (shown as *run N*).

## The problem

Answer questions about six disease-surveillance guideline booklets, citing the paragraph that holds the
answer. This page covers the retrieval half: finding the right paragraphs for a question. Generation,
citations and abstaining come in week 6.

## The data

- **5,226 numbered paragraphs** in six booklets, identified by (booklet, paragraph number). 71 are empty
  (images only).
- **Very uneven:** the median is 77 characters, but 172 paragraphs are over 1,000 and the longest is 18,621
  (flattened tables). About 1 in 5 makes sense on its own; the rest are headings, contents entries, list
  items or half-sentences that depend on what's around them (*Reading the data*, capstone README).
- **The embedding model reads 256 tokens,** so the text past that point in long paragraphs is never
  embedded (`embed.py` reports how many: ⏳ add your count).

## How retrieval is measured

- **Test set:** `Train.csv`, 746 labelled questions (2 unlabelled rows skipped). Every label was checked
  against the database; **one was malformed** (`203204`, booklet 6 has 515 paragraphs) and corrected to
  `203, 204`, in code, by question id.
- **Split:** 596 for tuning, 150 held out, grouped by question text so a repeated question can't fall on
  both sides; seed 42. The held-out set is used once, for the final configuration.
- **Metrics:** Recall@5 (the share of labelled paragraphs in the top 5), MRR@5 (how high the first one
  is) and Recall@20 (the ceiling for a reranker). A hit must match the booklet as well as the number.
  Also Recall@5 per booklet, because booklet 6 holds 45% of the questions.
- **Noise:** one question changes Recall@5 by about 0.17 points, so **a difference under 2 points counts
  as no change**, and the simpler setup is kept.

## Keyword, vector, and how they're merged

| Run | Method | Recall@5 | MRR@5 | Recall@20 | Note |
| --- | --- | --- | --- | --- | --- |
| 1 | keyword, every word must match | 0.144 | 0.161 | 0.145 | no result at all for 428 of 596 questions |
| 2 | keyword, any word | 0.168 | 0.117 | 0.330 | |
| 3 | keyword, any word, rank divided by length | 0.226 | 0.156 | 0.474 | |
| 4 | vector (all-MiniLM-L6-v2, cosine) | 0.473 | 0.390 | 0.621 | |
| 5 | hybrid: runs 2 and 4 merged by reciprocal rank fusion | 0.531 | 0.461 | 0.654 | |

- **Requiring every word fails:** it finds nothing for 72% of questions (*run 1*). Real questions use words
  the paragraph doesn't.
- **Long paragraphs dominate keyword search.** Paragraphs over 1,000 characters are 3% of the table but
  take 85% of the top-5 slots in *run 3*; one 16,206-character table is in the top 5 for 331 questions.
  Penalising length gains 5.8 points of Recall@5 and 14.4 of Recall@20 (*run 2 → run 3*), but the
  underlying fix is to stop retrieving 16,000-character units at all (chunking, below).
- **Merging by rank, not score:** keyword scores (`ts_rank_cd`) and cosine distances are on different
  scales, so they can't be added. Reciprocal rank fusion adds 1 / (60 + rank) from each list, so a
  paragraph ranked well by *both* rises to the top. Each list contributes its top 50. ⏳ Result: *run 5*
  against *runs 3 and 4*.

## top_k

**Retrieve 20, pass 5 to the model.** Five keeps the prompt short and the citations checkable. The gap
between Recall@5 and Recall@20 is large (0.226 against 0.474 in *run 3*): many right answers are found
but ranked 6 to 20, which is exactly what a reranker over the top 20 can fix. ⏳ Confirm with *run 5*.

## Chunking and metadata ⏳

Planned, one change at a time, kept only if it gains 2 points or more:

1. **Split long paragraphs** into about 800-character pieces with 100 overlapping. Expected to help most,
   because the big tables are what crowd out the top 5.
2. **Attach each heading to the paragraphs under it.** 15% of labelled paragraphs are headings under
   40 characters, and for 34 questions every label is one (Recall@5 0.029 on them, against 0.238 on the
   rest, *run 3*). So a chunk records the paragraphs it covers **including its heading**, and a hit on the
   chunk counts for both.
3. **The nearest heading as metadata,** weighted higher in keyword search.

Each chunk carries: booklet, the range of paragraphs it covers, its heading, the strategy that made it.

## What the reranker adds ⏳

A cross-encoder (`ms-marco-MiniLM-L-6-v2`) re-scores the best setup's top 20. Report the gain in Recall@5
and MRR@5, and the added time per question, next to the ceiling set by Recall@20.

## Held-out result ⏳

The final configuration, run once on the 150 held-out questions, beside its tuning score. Booklets 1 and
4 have only 5 held-out questions each, so their per-booklet numbers aren't meaningful.

## Limits and next steps

- Labels are paragraph numbers chosen by people. Some point at a heading rather than the answer, and
  some answers span several paragraphs, so Recall can't reach 1.0 even for a perfect retriever.
- Tables are flattened into text. Chunking helps, but the table structure is lost.
- Retrieval is measured, but answers aren't yet: faithfulness and citation accuracy need a judge
  (week 21).
- Next (week 6): `rag.py`, with numbered sources, citations, and an abstain rule enforced in code.