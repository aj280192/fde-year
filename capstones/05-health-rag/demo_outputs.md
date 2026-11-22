# Health RAG · demo outputs

Run Sun 22 Nov 2026 through the Streamlit demo page (`demo_page.py`) against `POST /v1/ask`, with
sources sorted best first. Questions 1 to 9 are from the **tuning** set (`Train.csv`), referred to by their id. Question 10 is my
own, written to test abstaining. The held-out set was not used.

**Licence:** the booklets may not be shared in altered form, so this file holds no booklet text,
no answer text and no question text from the data: only ids and what I observed. Question 10 is my
own wording, so it is quoted. "Labelled" means the paragraphs
`Train.csv` marks as the answer.

---

## Results

| # | Question | Outcome | Cited more than one? | Labelled paragraph retrieved? | What I saw | Failure type |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | q962 | answered | — | yes, but ranked near the bottom | the labelled paragraph was cited, but paragraphs about fatality and measles scored higher | ranking |
| 2 | q232 | answered | — | **no** | none of the labelled paragraphs were retrieved; the top results were about data collection in general | retrieval miss |
| 3 | q155 | answered | yes | yes | correct citation, plus a similar booklet 6 paragraph about line lists | extra similar paragraph |
| 4 | q289 | answered | no | partly | only one paragraph cited | under-citation |
| 5 | q200 | answered | yes (3) | yes, 3 of the labelled paragraphs | three labelled paragraphs retrieved and cited | ✅ good |
| 6 | q498 | answered | yes | yes | cited correctly, plus a paragraph that reads like a definition of the question's main term | extra related paragraph |
| 7 | q1094 | answered | yes | yes | cited correctly, plus a paragraph explaining terms used in the question | extra related paragraph |
| 8 | q1238 | answered | yes | yes | about reporting: found the right paragraph, plus one that uses the word "reporting" many times | keyword bias |
| 9 | q283 | answered | — | partly | could not retrieve all the labelled paragraphs; the answer seems split across chunks | chunking |
| 10 | "How often should an adult taking a statin for high cholesterol have the dose reviewed?" | **abstained** | — | not applicable: a health question the booklets don't cover | the page showed the calm "can't find this" message with its reason and the sources it searched | ✅ correct abstain |

**Counts:** 10 questions, 9 answered, **1 abstained** (question 10, correctly), 5 cited more than one paragraph (q155, q200,
q498, q1094, q1238; q289 cited one). 7 of 9 retrieved at least one labelled paragraph; q232
missed completely and q283 only partly.

**Abstaining:** question 10 is the hard kind, a health question close to the booklets' subject but
not in them, and the system declined, as it should. The plan asks for at least 2 abstentions. Still
to add: one clearly off-topic question ("What is the capital of France?"), with its top score.

**Not recorded:** seconds per question and the top-3 scores. Add them on the next run; the
abstain explanation in the demo video needs the score gap between an in-scope and an off-topic
question.

---

## What the nine show

1. **Extra related paragraphs are the most common pattern** (q155, q498, q1094, q1238). The right
   paragraph is found, but a neighbour about the same topic (a definition, a line list, a paragraph
   explaining a term) is cited too. For a user this is mostly harmless: the extra paragraph is on
   topic. Against the labels it lowers citation precision.
2. **Keyword pull from the hybrid search** (q1238). A paragraph that repeats a word from the question
   ranks high even when it doesn't answer it. This is the keyword half of hybrid retrieval doing
   what it does, the same effect I measured in week 6 with long tables taking the top-5 slots.
3. **Ranking, not recall, in q962.** The right paragraph was retrieved but ranked low. The
   reranker should push it up; worth checking its score against the ones above it.
4. **One real retrieval miss** (q232). Nothing labelled came back. This is the dangerous case,
   because the system answered anyway from general paragraphs instead of abstaining. Question 10
   shows the abstain rule does work when the matches are weak enough, so q232's matches must have
   scored above the threshold: comparing the two top scores is the next check.
5. **Chunking limits multi-paragraph answers** (q283, maybe q289). When an answer spans
   consecutive paragraphs, retrieval finds only part of it.

## What I would change, in order

| Change | Fixes | How I would measure it |
| --- | --- | --- |
| Check why q232 answered instead of abstaining: compare its top score with the abstain threshold | answering without support | the abstain rule fires on q232, without new abstentions on the other eight |
| Report **citation precision** (cited and labelled ÷ cited) beside Recall@5 | makes the extra-paragraph pattern visible as a number | the metric on the full tuning set |
| Drop near-duplicate sources before generation (for example, maximal marginal relevance) | extra similar paragraphs (q155, q498, q1094) | citation precision up, Recall@5 not down by more than 2 points |
| Lower the keyword weight in the fusion, or rerank more candidates | keyword bias (q1238), ranking (q962) | MRR@5 on the tuning set |
| Chunk with neighbouring paragraphs attached | answers split across paragraphs (q283, q289) | recall on questions with more than one labelled paragraph |

The first row matters most: a wrong answer stated confidently is worse than "I can't find this".