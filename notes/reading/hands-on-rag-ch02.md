# Hands-On RAG for Production · ch. 2 · The base RAG stack

*Hands-On RAG for Production*, Mendelevitch and Bao (O'Reilly). Read in week 3, before the health RAG project starts on Thu 5 Nov 2026.

> **How these notes are marked.** Sections headed "From the chapter" are what the chapter covers, in my words. Boxes marked **Added context** are general background I added to make the notes more useful; they are not claims about what the book says.

---

## The big picture: two flows

The chapter splits a RAG system into two separate flows that run at different times.

```text
INGESTION FLOW (offline, runs when documents arrive or change)
documents ──► parse ──► chunk ──► embed ──► store in a vector database
                                                     │
GENERATION FLOW (online, runs for every question)    │
question ──► embed ──► vector search ◄───────────────┘
                          │ top-k chunks
                          ▼
                 build the prompt ──► LLM ──► answer
```

Why the split matters:

- **Ingestion is done once per document, generation once per question.** Ingestion can be slow and thorough; generation has to be fast.
- **Most answer quality is decided at ingestion.** If a fact was split badly or parsed wrongly, no prompt can recover it. The generation flow can only use what retrieval hands it.
- **They fail differently.** An ingestion bug affects every question about that document; a generation bug affects how answers are written.

---

## Part 1 · The ingestion flow

### 1.1 Document parsing

**From the chapter:** documents come in many formats (PDFs, Word files, HTML, slides, scanned pages), and each needs its own way of extracting the information in it. The chapter doesn't treat cleaning as a separate step.

> **Added context: what goes wrong in parsing**
> - **Tables** are the biggest risk. Extracted as plain text, a dosage table loses which number belongs to which row and column. Keep tables as tables (for example as markdown), or as one row per line with its headers repeated.
> - **Repeated headers and footers** (page numbers, booklet titles) end up inside chunks and add noise to every search. This is where a cleaning step earns its place, even if the chapter folds it into parsing.
> - **Reading order** in multi-column PDFs can come out mixed up.
> - **Scanned pages** have no text layer, so they need OCR, which introduces errors.
> - **Keep metadata** while parsing: source file, page number and section heading. Generation needs it later for citations.

### 1.2 Text chunking

**From the chapter:** chunk size is a central choice, and the chapter compares five ways to split text.

| Method | How it splits | Strength | Weakness |
| --- | --- | --- | --- |
| **Fixed size** | Every N tokens or characters | Simple, fast, predictable | Cuts through sentences, tables and ideas |
| **Fixed size with overlap** | Every N tokens, each chunk repeating the last few tokens of the previous one | A fact on a boundary appears whole in at least one chunk | More chunks to store and search; near-duplicate results |
| **Recursive** | Tries the biggest natural break first (paragraphs), then smaller ones (sentences, then words) until each piece fits the size limit | Respects the text's own structure where it can; a good default | Still unaware of meaning; sizes vary |
| **Semantic** | Embeds sentences and starts a new chunk where the meaning shifts | Chunks hold one idea each | Slower and costlier (embeds everything twice); results depend on a threshold |
| **Document structure** | Uses the document's own headings, sections, lists and tables | Chunks match how the author organised the content; headings make good metadata | Needs reliable parsing; sections can be far too long or too short |

> **Added context: choosing a chunk size**
> - **Too small** and a chunk lacks the context to be understood ("give 5 mg" without saying for whom). **Too large** and one chunk mixes several topics, so its embedding is a blurry average and matches poorly.
> - A common starting range is a few hundred tokens with 10 to 20% overlap, but that's only a starting point. The right size depends on the documents and the questions, so it has to be **measured**.
> - **Chunk size and k are linked:** k chunks of size S must fit in the prompt with room for instructions and the answer.
> - Methods combine well: split by document structure first, then use recursive splitting inside any section that is still too long.

### 1.3 Choosing an embedding model

**From the chapter:** the chapter gives selection criteria for embedding models.

> **Added context: criteria worth checking**
> | Criterion | Why it matters |
> | --- | --- |
> | Quality on your kind of text | General benchmarks (such as the MTEB leaderboard) are a starting point, but medical guidelines aren't general text. Test on your own questions |
> | Maximum input length | Text beyond it is silently cut off, so it caps your chunk size |
> | Dimensions | More dimensions can mean better quality but more storage and slower search |
> | Language | Must match the documents and the questions |
> | Hosted or local, cost and latency | Every question is embedded at query time, so latency adds to every answer |
> | Licence | Matters for commercial use |
>
> Two rules that are easy to break: use the **same model for documents and questions**, and **re-embed everything** if you change models, because vectors from different models can't be compared.

### 1.4 Vector database and vector search

**From the chapter:** chunks and their embeddings are stored in a vector database. A question is embedded and compared against them, and the chapter lists the parameters to consider during vector search.

> **Added context: the parameters that matter**
> - **Distance metric:** cosine, inner product or Euclidean (L2). Use the one the embedding model was trained for.
> - **k (top-k):** how many chunks come back. See question 2 below.
> - **Similarity threshold:** drop results below a minimum score, so the system can say "I don't know" instead of answering from weak matches.
> - **Metadata filters:** search only within, say, one booklet or one section.
> - **Exact versus approximate search:** exact search compares the question with every chunk, which is accurate but slow at scale. Approximate nearest neighbour (ANN) indexes trade a little recall for a lot of speed.
> - **In pgvector**, which I use from 5 November, the two ANN index types are:
>   - **HNSW:** tuned with `m` and `ef_construction` when building, and `hnsw.ef_search` when querying. A higher `ef_search` gives better recall but slower queries.
>   - **IVFFlat:** tuned with `lists` when building, and `ivfflat.probes` when querying.
>
>   For six booklets (a few thousand chunks), exact search is fast enough, and an index isn't needed yet.

---

## Part 2 · The generation flow

### 2.1 Prompt engineering for RAG

**From the chapter:** the retrieved chunks are put into the prompt, with instructions on how to use them.

> **Added context: what a RAG prompt usually contains**
> 1. A role and task: "Answer the question using only the context below."
> 2. **Grounding rules:** use only the context, and don't add outside knowledge. This matters for medical guidelines.
> 3. **An abstain rule:** if the context doesn't contain the answer, say so. My health RAG project has this rule in Part 2.
> 4. **Citations:** each chunk is labelled with its source and page, and the model is asked to cite the labels it used.
> 5. The chunks, then the question, last.

### 2.2 Generating with RAG

**From the chapter:** how the model produces an answer from the question plus the retrieved context.

> **Added context: things that affect the answer**
> - **Order matters:** models tend to use the start and end of a long context better than the middle (the "lost in the middle" effect). Put the strongest chunks first.
> - **Token budget:** the instructions, k chunks, the question and the answer must all fit in the context window. More chunks isn't always better: irrelevant ones distract the model.
> - **Low temperature** keeps answers close to the context.

---

## Where I stand

I understand how RAG works, but I haven't built any part of it in code. Every stage above is new to me as an implementation, so the 5 November lab is my first one. The stages I most want to get right are **chunking**, because the chapter shows how many valid choices there are, and **retrieval**, because it decides what the model can see.

---

## Questions for the health RAG project, and how I'll answer them

These are questions to answer by **measuring on the Malawi guideline booklets**, not by reading more.

### 1 · Which chunking method works best for these booklets?

- **Why it's open:** no method is best in general. Guideline booklets have clear headings, numbered steps and dosage tables, which suggests that chunking by document structure should beat fixed-size chunking. That's a guess until it's measured.
- **How to answer it:** take 20 to 30 questions from `Train.csv` with known answers. Chunk the booklets two or three ways, for example fixed size with overlap, recursive, and by structure. For each method, count how often the chunk holding the answer is in the top k (recall@k).
- **Watch for:** tables being split across chunks.

### 2 · How should I choose k?

- **Why it's open:** too few chunks and the answer may be missing; too many and the prompt fills with noise and costs more.
- **How to answer it:** using the same labelled questions, plot recall@k for k = 1, 3, 5, 10 and 20, and pick the smallest k after which recall stops improving much. Check that k times the chunk size fits the model's context with room to spare.
- **Common pattern to try later:** retrieve more chunks (20 to 50), re-rank them, and keep the best 3 to 5.

### 3 · Does hybrid search help here?

- **Why it's open:** vector search matches meaning but can miss exact terms. Guidelines are full of exact terms: drug names, doses, abbreviations such as ART or IPT. Keyword search (full-text search, or BM25) finds exact words but misses paraphrases. Hybrid search runs both and merges the results.
- **How to answer it:** in Postgres, run a full-text query (`tsvector`) and a pgvector query, then merge the two ranked lists, for example with reciprocal rank fusion. Compare recall@k for vector only, keyword only and hybrid on the same questions, and look especially at questions that name a drug or a dose.
- **This is planned for 5 November:** that lab's task is one hybrid keyword-plus-vector query, so this question gets its first answer that day.