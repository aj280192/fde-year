# Q1 · Retrieval design for the health guidelines assistant

**Status:** final, 10 Nov 2026.
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
  embedded (`embed.py` reported 156 paragraphs over 256 tokens).

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
| 5 | hybrid: runs 2 and 4 merged by reciprocal rank fusion | 0.531 | 0.468 | 0.654 | |

- **Requiring every word fails:** it finds nothing for 72% of questions (*run 1*). Real questions use words
  the paragraph doesn't.
- **Long paragraphs dominate keyword search.** Paragraphs over 1,000 characters are 3% of the table but
  take 85% of the top-5 slots in *run 3*; one 16,206-character table is in the top 5 for 331 questions.
  Penalising length gains 5.8 points of Recall@5 and 14.4 of Recall@20 (*run 2 → run 3*), but the
  underlying fix is to stop retrieving 16,000-character units at all (chunking, below).
- **Merging by rank, not score:** keyword scores (`ts_rank_cd`) and cosine distances are on different
  scales, so they can't be added. Reciprocal rank fusion adds 1 / (60 + rank) from each list, so a
  paragraph ranked well by *both* rises to the top. Each list contributes its top 50.
  **Result:** hybrid beats vector alone by 5.8 points of Recall@5 (0.473 → 0.531) and 7.8 points of
  MRR@5 (0.390 → 0.468) (*run 4 → run 5*), even though the keyword list it adds is weak on its own
  (0.168, *run 2*). The two lists find different paragraphs: keyword search catches exact terms
  (disease and drug names) that the embedding blurs, and a paragraph both rank well goes to the top.
  Vector search is the stronger half on this data: 0.473 against 0.226 for the best keyword run (*run 3*).
  Merging the length-penalised keyword list instead adds 2.7 more points (0.558, MRR@5 0.504, *run 6*),
  so that is the hybrid used from here on.

## top_k

**Retrieve 20, pass 5 to the model.** Five keeps the prompt short and the citations checkable. The gap
between Recall@5 and Recall@20 is large (0.226 against 0.474 in *run 3*): many right answers are found
but ranked 6 to 20, which is exactly what a reranker over the top 20 can fix. For hybrid (*run 5*),
Recall@5 is 0.531 and Recall@20 is 0.654: 12.3 points of labelled paragraphs are retrieved but ranked
too low, and that's the most a reranker can add. The other 35% aren't in the top 20 at all, so they
need better chunking, not reranking. That's why chunking is tried first.

## Chunking and metadata

Tried one change at a time, each kept only if it gained 2 points or more. A chunk is what the model
would receive, so the top 5 are cut by **chunk**, and a chunk counts as finding every paragraph it covers.

| Strategy | What changes | Chunks | Keyword (rank ÷ length): Recall@5 | Hybrid: Recall@5 · MRR@5 · Recall@20 | Keyword top-5 context | Kept? |
| --- | --- | --- | --- | --- | --- | --- |
| whole | one chunk per paragraph (the baseline) | 5,155 | 0.226 (*run 3*) | 0.558 · 0.504 · 0.679 (*run 6*) | 41,613 characters | baseline |
| split | paragraphs over 1,000 characters cut into ~800-character pieces, 100 overlapping | 5,881 | 0.349 (*run 8*) | 0.558 · 0.492 · 0.680 (*run 10*) | ~3,100 | no: hybrid unchanged |
| headings | each paragraph prefixed with the heading above it, and covering it | 5,155 | 0.284 (*run 11*) | 0.598 · 0.548 · 0.714 (*run 13*) | ~41,300 | yes: +4.0 |
| headings + split | both | 5,902 | **0.433** (*run 14*) | 0.590 · 0.539 · **0.724** (*run 16*) | ~3,100 | **yes: final** |
| heading as metadata | heading in its own column, weighted higher in keyword search | 5,155 | 0.197 (*run 17*) | 0.466 · 0.385 · 0.648 (*run 18*) | ~13,800 | no: hybrid fell 9.2 points |

- **Splitting long paragraphs worked, more than I predicted:** keyword Recall@5 rose 12.3 points (I
  expected 8), and the text sent to the model fell from about 41,600 characters to 3,100, because the
  16,000-character tables no longer fill the top 5.
- **Headings help only once the tables are split.** On their own they gain 5.8 points for keyword search,
  but the big tables still dominate (they even get longer). On top of splitting, they add another
  8.4 points (*run 8 → run 14*). The weakest booklet gained most: booklet 3 went from 0.065 to 0.390.
- **Heading as weighted metadata hurt** (0.197 against 0.226): a short heading matched in weight A
  outranks paragraphs that answer the question. Dropped.
- **For vector and hybrid search, the order was different.** Splitting helped vector search (+4.3,
  *run 9*), because text past the model's 256 tokens now gets embedded, but added nothing to hybrid
  (*run 10*). Headings added nothing to vector search alone (*run 12*), yet gave hybrid its biggest gain,
  +4.0 (*run 13*): with the topic in the text, the keyword and vector lists agree more often.
- **Why headings + split, when headings alone scored 0.8 higher:** by the 2-point rule the two are a
  tie, so the choice rests on what else they offer. Headings + split has the highest Recall@20 (0.724
  against 0.714), which is the reranker's ceiling, and sends a quarter of the text to the model
  (about 2,350 characters in the top 5 against 9,270, *runs 16 and 13*).

**Each chunk carries:** its booklet; `covers`, the paragraphs it stands for (with `headings`, the
paragraph and its heading), used for citing and for scoring; a piece number when a paragraph is split;
the strategy that built it; its text, a full-text vector and an embedding. Chunks are rebuilt from the
`paragraphs` table, which never changes.

## What the reranker adds

A cross-encoder (`ms-marco-MiniLM-L-6-v2`) re-scores the best setup's top 20 (*run 19*):
Recall@5 0.590 → 0.649 (+5.9), MRR@5 0.539 → 0.650 (+11.1), at about 27 ms per question more
(9.3 → 36.7 ms, on a laptop GPU). Recall@20 stays 0.724, as it must: the reranker only re-orders the
same 20 chunks, so that is its ceiling, and 7.5 points of it are still ranked 6 to 20. **Kept:** the
gain is well past the noise, the right paragraph moves to the top far more often (MRR), and 37 ms is
small next to the seconds a language model takes to answer.

## The final configuration

**Headings + split** chunks (each paragraph with the heading above it, anything over 1,000 characters
split into overlapping ~800-character pieces); **hybrid** retrieval (keyword with rank divided by length,
and vector, top 50 from each, merged by reciprocal rank fusion); the **cross-encoder** re-orders the top
20; the **top 5** chunks, about 2,400 characters, go to the model. Against the first hybrid (*run 5*):
Recall@5 0.531 → 0.649 and MRR@5 0.468 → 0.650, with about 7 times less text in the top 5
(16,001 → 2,384 characters, *runs 7 and 19*).

## Held-out result

Run once, on the 150 held-out questions (*run 20*):

| | Recall@5 | MRR@5 | Recall@20 |
| --- | --- | --- | --- |
| Tuning, 596 questions (*run 19*) | 0.649 | 0.650 | 0.724 |
| Held-out, 150 questions (*run 20*) | 0.691 | 0.668 | 0.752 |

The held-out score is 4.2 points *higher*, not lower. With 150 questions, one question moves Recall@5
by 0.67 points and the standard error is about 4 points, so the two agree within noise: there's no sign
that the choices were fitted to the tuning questions. Booklets 1 and 4 have only 5 held-out questions each, so their per-booklet
numbers aren't meaningful.

## Limits and next steps

- Labels are paragraph numbers chosen by people. Some point at a heading rather than the answer, and
  some answers span several paragraphs, so Recall can't reach 1.0 even for a perfect retriever.
- Tables are flattened into text. Splitting helps, but the table structure is lost; one chunk per table
  row, with its header repeated, is the next thing to try.
- The heading rule is a guess (short, no full stop, not starting lower case), so some list items are
  treated as headings.
- Retrieval is measured, but answers aren't yet: faithfulness and citation accuracy need a judge
  (week 21).
- Next (week 6): `rag.py`, with numbered sources, citations, and an abstain rule enforced in code.