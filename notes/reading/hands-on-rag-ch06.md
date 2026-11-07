# Hands-On RAG for Production · ch. 6 · Evaluating RAG

Read Fri 6 Nov 2026, before writing `evaluate.py` for the health RAG project.

## The key idea: the rank comes from my retriever, not from the labels

Train.csv says *which* paragraphs answer each question. My retriever produces a *ranked list*.
A retrieval metric compares the two. So every metric that needs only "relevant: yes or no" can be
computed from Train.csv; only metrics that need *graded* relevance, or judge an *answer*, can't.

## Metrics the chapter names

| Metric | Measures | Retrieval or generation | Needs labels? | Needs a judge? | From Train.csv alone? |
| --- | --- | --- | --- | --- | --- |
| Recall@k | the share of the labelled paragraphs found in the top k (1 of 2 found → 0.5) | retrieval | yes: which paragraphs are relevant | no | ✅ |
| MRR | 1 ÷ the rank of the *first* relevant paragraph (0 if none in the top k), averaged over questions | retrieval | yes: which are relevant | no | ✅ |
| MAP | per question, the precision at the rank of *each* relevant hit, averaged; then averaged over questions. Rewards finding all of them, early | retrieval | yes: which are relevant | no | ✅ |
| nDCG | ranking quality with *graded* relevance (0 to 3); a hit counts less the lower it's ranked | retrieval | yes: graded relevance | no | ⚠️ binary nDCG only: Train.csv has yes or no, not grades |
| UMBRELA | an LLM judge grades each retrieved passage's relevance to the question, creating relevance labels where none exist | retrieval | no | yes | ❌, but Train.csv can **validate** the judge: check its grades against the known labels |
| Contextual utilisation | how well the answer uses the retrieved context | generation | no | yes | ❌ |
| Answer accuracy | how close the generated answer is to a reference answer | generation | yes: a reference answer | a model: embedding similarity or a judge | ⚠️ the reference is in Train.csv ("Question Answer"); scoring needs a model |
| Faithfulness | whether every claim in the answer is supported by the retrieved paragraphs | generation | no | yes | ❌ |
| Citation precision | the share of the answer's citations that really support what they're attached to | generation | no | yes | ⚠️ a cheap partial check: does a cited (booklet, paragraph) appear in Train.csv's labels? |

## What Train.csv can and can't tell me

- It gives, per question: the question, a reference answer, the booklet, the paragraph numbers
  (single, lists like `154, 166`, or ranges like `439-440`), and keywords. Two rows have no
  paragraph label, and 11 questions appear twice.
- **I can compute now:** every retrieval metric with yes-or-no relevance: Recall@k, MRR, MAP,
  binary nDCG.
- **Partly now:** answer accuracy (the reference answers are there; scoring needs an embedding
  model or a judge), and a partial citation check against the labelled paragraphs.
- **Needs a judge, so week 21:** faithfulness, contextual utilisation, full citation precision,
  and UMBRELA (which Train.csv can help validate).

## For tomorrow's evaluate.py

- **k = 5** for the headline numbers: Recall@5 and MRR, as the plan asks. Also record
  **Recall@20**, because the reranker picks from the top 20 and can't recover what isn't there.
- **MRR is cut off at 5:** a question scores 0 if no relevant paragraph is in the top 5.
- **The split:** group by question text, so a repeated question can't fall on both sides;
  150 held out, fixed seed; skip the 2 unlabelled rows; never open the held-out file until Sunday.
- **Run for:** keyword only, vector only, hybrid, then each chunking change and the reranker,
  one at a time; every run is one row of the results table.
- **One thing from the chapter I'll add:** report results **per booklet** as well as overall, so
  a change that helps one booklet but hurts another is visible.