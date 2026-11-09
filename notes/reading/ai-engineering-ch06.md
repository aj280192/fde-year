# AI Engineering · ch. 6 · RAG and agents

Chip Huyen, *AI Engineering* (O'Reilly, 2025). Read Mon 9 Nov 2026, at the start of week 6.
**Why now:** this chapter frames Phase 2 (agents and MCP, weeks 9 to 18), and its first half covers the
retrieval I built and measured last week. My numbers are from `capstones/05-health-rag/results.csv`,
596 tuning questions, whole paragraphs as chunks.

---

## Five lines: what the chapter says

1. **RAG** gives a model the context it needs at question time: a retriever finds relevant documents,
   and the generator answers from them.
2. **Retrievers are term-based (sparse)**, such as TF-IDF and BM25 (what Elasticsearch uses), **or
   embedding-based (dense)**, which search vectors with approximate nearest-neighbour algorithms because
   exact search is too slow at scale. The two can be combined into a hybrid.
3. **Retrieval is judged on its own,** by context precision and recall, ranking quality, embedding quality,
   cost and latency; then the generated answer is judged separately. Retrieval improves through
   chunking, reranking, query rewriting and contextual retrieval.
4. **An agent** perceives an environment and acts on it with **tools**: knowledge augmentation,
   capability extension, and write actions that change the world.
5. **Agents plan** (plan generation, function calling, plan granularity, reflection), and **fail** in
   planning, in tool use and in efficiency, so each kind of failure needs its own evaluation.

---

# Part 1 · RAG

## What RAG is, and why it exists

- **The problem it solves:** it adds relevant context for the LLM to generate its response from. It
  overcomes the model's out-of-date knowledge by adding up-to-date context, and its missing private
  knowledge by adding our own documents, which can then be cited.
- **The two parts:** the **retriever** gets the relevant information from the knowledge base (internal
  documents, a database). The **generator** uses the prompt built from it to write a response grounded
  in that context.
- **RAG against a long context window:** why not just put all six booklets in the prompt? First is cost:
  a long context costs more compute and takes longer to process, on every question. Second, research
  shows models use information at the start and end of a long input better than in the middle, so they
  can miss the relevant part. Retrieval puts only the relevant paragraphs in front of the model.

## Retrieval algorithms

| Kind | How it works | Strengths | Weaknesses | Example | My result |
| --- | --- | --- | --- | --- | --- |
| Term-based (sparse, lexical) | scores documents by the query's words: how often each appears in the document (term frequency), weighted by how rare it is across all documents (inverse document frequency); BM25 also corrects for document length | fast, cheap, no model or training needed; exact terms (drug and disease names, codes) match exactly | misses meaning: a synonym or paraphrase scores 0; favours long documents unless length is corrected for | TF-IDF, BM25, Elasticsearch; Postgres full text (`ts_rank_cd`) | Recall@5 0.168 (*run 2*), 0.226 with a length penalty (*run 3*) |
| Embedding-based (dense, semantic) | turns the query and each document into vectors with an embedding model, and returns the nearest by cosine distance; at scale, approximate nearest-neighbour (ANN) indexes such as HNSW, IVF, LSH or product quantisation trade a little recall for speed | matches meaning, not just words; the embedding model can be swapped or fine-tuned | costs an embedding model at indexing and query time; weaker on exact rare terms; the model reads a limited input (256 tokens for mine) | vector databases; pgvector | Recall@5 0.473 (*run 4*) |
| Hybrid | runs both, then merges the results: either in sequence (a cheap retriever narrows, an expensive one reranks) or side by side, merged by reciprocal rank fusion | the two find different documents, so together they find more | two systems to run and tune; slower | reciprocal rank fusion (k = 60) | Recall@5 0.531, MRR@5 0.468 (*run 5*) |

**What the chapter says about choosing between them:** term-based retrieval is cheap and fast, works out
of the box and is a strong baseline, but misses meaning. Embedding-based retrieval costs more but
matches on meaning, and can be improved by choosing or fine-tuning the embedding model, which a
term-based retriever can't learn from data in the same way (BM25 has only a couple of settings).

**Where my measurements agree or disagree with the chapter:**

- **Agree: hybrid beats either one alone.** Hybrid gains 5.8 points of Recall@5 and 7.8 of MRR@5 over
  vector alone (*run 4 → run 5*), although its keyword half is weak on its own (0.168, *run 2*). The two
  lists find different paragraphs.
- **Disagree, for this data: term-based was not a strong baseline.** It reached only 0.226 (*run 3*),
  half of vector's 0.473. The cause is the data, not the method: a few huge flattened tables (3% of
  paragraphs) contain almost every word, and take 85% of the keyword top-5 slots. Whole-paragraph
  chunking makes term-based search look worse than it should; splitting those tables should narrow the gap.
- **Agree: term-based retrieval misses paraphrase.** Booklet 3, whose paragraphs rarely name their topic,
  scores 0.017 with keyword search and 0.412 with vector search.
- **Agree: requiring every query word is too strict.** It found nothing at all for 428 of 596 questions
  (*run 1*).
- **The ANN point didn't apply yet:** with 5,155 vectors, an exact scan takes about 2 ms per question
  (*run 4*, database time only), so I have no vector index. It matters at millions of chunks, when an
  HNSW index would trade a little recall for speed, and that loss should be measured too.

## How retrieval is evaluated

| What the chapter measures | Means | Did I measure it? | How, or why not |
| --- | --- | --- | --- |
| Context recall | of the documents that should have been retrieved, the share that were | ✅ | **Recall@5** and **Recall@20**, from the labelled paragraphs in `Train.csv` |
| Context precision | of the documents retrieved, the share that are relevant | ❌ not reported | computable from the same labels (relevant hits in the top 5 ÷ 5), but most questions have one labelled paragraph, so precision@5 is at most 0.2 and says little; recall is the better measure here |
| Ranking quality (MRR, MAP, nDCG) | whether relevant documents come *first* | ✅ MRR@5 | MAP and binary nDCG are computable from the same labels; graded nDCG isn't, because the labels are yes or no |
| Embedding quality | how good the embedding model is, on general benchmarks such as MTEB, and on my task | partly | only through retrieval on my own task (*run 4*); I haven't compared embedding models yet |
| Retrieval latency and cost | time and money per query, and for indexing | partly | `ms_per_question` (database time: about 3 ms keyword, 2 ms vector, 5 ms hybrid); question embedding time and indexing time not yet recorded |
| Generation quality | whether the answer is correct and faithful to the retrieved context | ❌ not yet | needs the generator (week 6) and a judge (week 21) |

**One thing I'd add from doing it:** judge per subset as well as overall. Booklet 6 has 45% of the
questions, and per-booklet Recall@5 shows hybrid helps booklet 1 most (0.312 → 0.461) and booklet 2
barely (0.516 → 0.517, *runs 4 and 5*). The overall mean hides that.

## Making retrieval better

| Technique | What it does | When it helps | Used it? | What happened |
| --- | --- | --- | --- | --- |
| Chunking strategy | splits documents into units: by size (characters or tokens), with overlap, or by structure (headings, sections); smaller chunks are more precise, but lose context | always a decision; most when documents are long or uneven | ⏳ today | B3 found the problem it should fix: 16,000-character tables crowd out the top 5. Results: *runs …* |
| Reranking | re-scores the first retriever's candidates with a more accurate, slower model (a cross-encoder), or by other signals such as recency | when the right answer is retrieved but ranked low (Recall@20 well above Recall@5) | ⏳ today | ceiling for hybrid: Recall@20 0.654 against Recall@5 0.531 (*run 5*) |
| Query rewriting | rewrites the user's query before retrieval: resolving "it" or "that" from the conversation, expanding acronyms, splitting a compound question | conversations, vague or compound questions | read only | my test questions are single, self-contained questions, so it would matter more in a chat interface |
| Contextual retrieval | adds context to each chunk before indexing: an LLM writes a sentence placing the chunk within its document, or metadata such as the title and section is attached | when chunks don't make sense on their own | read only | the cheap version is my "attach headings" change (below) |
| Metadata and filtering | stores fields such as source, date or section with each chunk, and filters or boosts on them | when a query names a scope ("in the TB guidelines") or recency matters | planned (heading as weighted metadata) | not filtering by booklet: a real user's question doesn't come with one |

**Contextual retrieval against my "attach headings" change:** both add context to a chunk. The
difference is that contextual retrieval uses another LLM to write that context from the whole document,
while attaching headings just adds the raw heading text. Headings are free, deterministic and always
right, but only say what the heading says. Generated context can say more (which disease, which
section, what the chunk is for), at the cost of one LLM call per chunk at indexing time, and the risk
that the generated text is wrong.

## RAG beyond plain text

- **Tables and structured data:** for data in tables, the chapter's approach is text to SQL: the model
  writes a query against the table, and the result goes into the context, instead of retrieving table
  text. My booklets' tables are flattened into one long paragraph each, which is the worst of both:
  too long to embed and too full of words for keyword search. Two better options: split each table into
  one chunk per row, with its header repeated, so each row reads as a sentence; or load the important
  tables (case definitions, reporting deadlines) into real Postgres tables and query them.
- **Multimodal RAG:** retrieving images (or text extracted or generated from them) alongside text, using
  embedding models that place text and images in one space. My 71 empty paragraphs were images; they're
  invisible to retrieval now. A caption written for each, by a vision model, would make them findable.

---

# The retrieval techniques: used or only read about

| Technique | Used? | Where | What I learned from using it, or why I haven't yet |
| --- | --- | --- | --- |
| Term-based search (Postgres full text) | ✅ used | `retrieve.py`: `keyword_all`, `keyword`, `keyword_norm` | requiring every word finds nothing for most questions; long documents dominate unless length is penalised (+5.8 points, *run 2 → 3*) |
| Embedding search (pgvector, cosine) | ✅ used | `embed.py`, `retrieve.py`: `vector` | the strongest single method here (0.473); vectors must be normalised and sent as a `vector`, not a list |
| Hybrid, reciprocal rank fusion | ✅ used | `retrieve.py`: `hybrid`, `rrf` | +5.8 Recall@5 and +7.8 MRR@5 over vector alone; merge by rank because the two scores aren't comparable |
| Chunking | ⏳ today | `chunks` table | |
| Reranking (cross-encoder) | ⏳ today | | |
| Retrieval evaluation with labels | ✅ used | `build_testset.py`, `metrics.py`, `evaluate.py` | check every label against the data (one was malformed); a held-out set used once; under 2 points is noise |
| ANN vector index (HNSW, IVF) | read only | | 5,155 vectors scan exactly in about 2 ms; needed at millions |
| BM25 | read only | | Postgres's `ts_rank_cd` isn't BM25; an extension or a search engine would provide it |
| Query rewriting | read only | | my test questions are already single and self-contained |
| Contextual retrieval (LLM-written context) | read only | | try after the cheap heading version, with one LLM call per chunk at indexing |
| Text to SQL for tables | read only | | a candidate for the case-definition tables |
| Multimodal RAG | read only | | would recover the 71 image paragraphs |
| Embedding model choice or fine-tuning | read only | | only all-MiniLM-L6-v2 so far |

---

# Part 2 · Agents

## What an agent is

- **The chapter's definition, in my words:** an agent is anything that can perceive its environment and
  act on it. An AI agent uses a model to decide which actions to take, observes what happened, and
  decides again, until the task is done.
- **Its two defining parts:** the *environment* it acts in (a cluster, a codebase, the web), and the
  *actions* (tools) it can take. The environment decides which tools make sense, and the tools decide
  what the agent can do.
- **How an agent differs from a RAG pipeline:** in my opinion, RAG is also an agent, and retrieval is the
  tool it uses to act on its environment (the knowledge base). The chapter makes the same point. The
  difference is degree: a RAG pipeline runs one fixed step (retrieve, then answer), while an agent
  chooses its own steps, how many, and in what order.
- **Why agents are harder:** errors compound over many steps. If each step is right 95% of the time,
  10 steps are all right only 60% of the time (0.95¹⁰ ≈ 0.60), and 20 steps only 36%. Each step also
  costs time and money, and write actions can do real damage.

## Tools

| Category | What it gives the agent | Examples from the chapter | An example for an operations agent (Phase 2) |
| --- | --- | --- | --- |
| Knowledge augmentation (read) | information the model doesn't have: private data, current data | retrieval, SQL queries, web search, internal APIs (inventory, a CRM) | list pods and their status, read recent logs, describe a deployment, query metrics |
| Capability extension | abilities the model is bad at on its own | a calculator, a code interpreter, a calendar or time zone converter, a translator | compute an error rate from raw counts, parse and filter a log file with code, compare two config files |
| Write actions (change the world) | the power to change the environment, not just read it | sending an email, running a SQL update, placing an order, a bank transfer | restart a pod, scale a deployment, roll back a release, open a ticket |

- **Why write actions need extra care:** trust in the system's capability and in its security measures
  is crucial, so write access shouldn't be handed to an unreliable agent. A wrong read wastes a step; a
  wrong write changes the real system, and may not be reversible. Write tools are also what an attacker
  aims for: text injected into a log or a web page could instruct the agent to call one.
- **Guardrails:** the chapter mostly warns rather than prescribing a list. The ones I'd use:
  - **least privilege:** the agent gets only the tools and scopes the task needs, like `tasks:read`
    against `tasks:write` in my task API
  - **human approval** before any write action, shown as the exact call it will make
  - **dry runs** where the system supports them (`kubectl --dry-run`), and reversible actions first
  - **limits:** a maximum number of steps and of write calls per task
  - **an audit trail** of every call, in `tool_calls`
- **How many tools to give an agent, and why:** fewer is better. More tools fill the context with their
  descriptions and make the model more likely to call the wrong one. The chapter suggests ablation:
  remove a tool, and if task success doesn't drop, it wasn't needed. Tools the agent keeps misusing
  need a better description, or removing.
- **How a model chooses a tool and its arguments (function calling):** we give the model the schema of
  every available tool: its name, a description and its parameters. The model decides whether a tool
  is needed and outputs a structured call: the tool's name and its arguments as JSON. **The model doesn't
  run anything itself:** my code checks the call against the schema, runs the tool, and returns the result
  to the model as the next message.
- **Connection to my code:** week 2's `ToolSpec` is the schema the model sees, `ToolCall` is what it
  outputs, and `ToolResult` is what goes back. For the chapter's evaluation ideas, `tool_calls` must
  record, per call: the tool and arguments, whether the call was valid, the type of failure (invalid
  tool, invalid arguments, wrong argument values, the tool itself erroring), how long it took, and the
  size of the result. Counted per task, that gives the number of calls, the failure rate by type, and
  the cost of each run.

## Planning

| Idea | What the chapter says | My take, or an example |
| --- | --- | --- |
| Generating a plan | the model is prompted with the task and the available tools, and writes the steps to take | for "why are the payment pods crash-looping": list pods → read the failing pod's logs → describe its deployment → compare with the last release |
| Separating planning from execution | generate the whole plan first, check it, and only then run it, instead of letting the model act as it goes | lets a wrong plan be caught before anything runs, which matters most when the plan includes write actions |
| Validating a plan before running it | check the plan with simple rules (every tool exists, no step uses a tool outside its permissions, the number of steps is reasonable) or with another model as a judge | cheap rules first: they catch an invalid tool or a write action without approval, at no model cost |
| Plan granularity | a plan can be high-level ("check the logs") or exact function calls; high-level plans are easier to generate and survive tool changes, but need a further step to turn them into calls | write the plan in plain steps, and translate each step into a tool call when it runs; renaming a tool then doesn't break saved plans |
| Control flow | plans aren't only a sequence: steps can run in parallel, branch on a condition (if), or repeat (for or while) | read the logs of all failing pods **in parallel**; **if** the logs show out-of-memory, check the memory limits; **loop** until no pod is restarting, with a limit |
| Reflection and error correction | after a step or at the end, the model checks whether it worked and fixes its plan; for example, the ReAct pattern alternates reasoning, an action and the observed result, and Reflexion adds an evaluator and a written self-critique | reflection catches some mistakes, but costs extra calls, and the model can wrongly decide it succeeded; a check in code is better wherever one exists (did the pod stop restarting?) |
| Human in the loop | a person approves risky steps, or answers when the agent is unsure | my task API's `waiting_for_input` state is exactly this: the task pauses until a person replies |

## How agents fail

| Failure | Example | How to detect it | A metric to track it | When I'll build it |
| --- | --- | --- | --- | --- |
| Invalid tool | calls `get_pod_logs` when the tool is named `read_logs` | the name isn't in the tool list | share of calls naming a tool that doesn't exist | weeks 19 to 26 |
| Valid tool, invalid arguments | `read_logs` without the required `namespace`, or a number where a string is expected | the arguments fail schema validation (Pydantic) | share of calls with invalid arguments | weeks 19 to 26 |
| Valid tool, wrong argument values | reads the logs of the healthy pod, or the wrong namespace | not from the schema: compare with the expected trajectory for a known scenario | share of calls whose values differ from the expected ones | weeks 19 to 26, on scenarios with known answers |
| Goal failure | stops with a confident answer that's wrong, or solves the task but breaks a rule (restarts a pod without approval) | check the final state and answer against the scenario's known root cause and rules | task success rate; constraint violations per task | weeks 19 to 26 |
| Reflection error | says the fix worked when the pod is still restarting | check the outcome in code, not by asking the model | share of runs where the agent's claim and the real outcome disagree | weeks 19 to 26 |
| Tool failure | the logs API times out, or returns a cut-off page | the tool's own error, or a result that fails its checks | tool error rate, by tool | the week 3 failure table: retries, time budgets and clear errors apply to every tool |
| Inefficiency | 25 steps where 6 would do, or reading the same logs three times | count steps, time and cost per task, against a reference run | steps, time and cost per successful task | weeks 19 to 26 |

**The one failure I think is most dangerous for an operations agent, and why:** a **goal failure that
looks like success**: the agent confidently reports a wrong root cause, or a fix that didn't work, and a
person acts on it. A crash or an invalid call is visible; a wrong but plausible answer isn't. The
defences are checking outcomes in code where possible, showing the evidence (which logs, which metric)
behind every conclusion, and measuring task success on scenarios whose answers are known.

## Memory

| Kind | Where it lives | Lasts | Example |
| --- | --- | --- | --- |
| Internal knowledge | the model's weights | until the model is retrained | general knowledge of Kubernetes and its error messages |
| Short-term | the context window | the current task or conversation | the logs read so far, the steps already taken |
| Long-term | external storage, retrieved when needed | as long as it's kept | past incidents and how they were fixed, the team's runbooks |

- **What to keep and what to drop when the context fills up:** the simplest strategy drops the oldest
  messages first, but that can lose the original task. Better: always keep the task and the plan, and
  summarise older steps instead of deleting them. Large tool outputs shouldn't enter the context
  whole: keep a short summary in the context and the full output in storage, retrievable by id.
- **How long-term memory is just RAG over the agent's own history:** the past is stored as documents
  (incidents, tool results, decisions) and the relevant parts are retrieved for the current task, with
  the same retrieval and the same evaluation as the health RAG.

---

## How this changes my plan

- **For the health RAG (weeks 6 to 24):** contextual augmentation, because it adds back the context that
  smaller chunks lose. Order: attach headings first (free), then LLM-written context if headings aren't
  enough, measured the same way.
- **For the operations agent (Phase 2):** start with **read-only tools** (knowledge augmentation: list
  pods, read logs, describe a deployment) and add write actions (restart, scale) only later, each behind
  an explicit approval, like the `tasks:write` scope. Make tool outputs **bounded**: a log tool returns
  the last N lines or a filtered summary, never the whole log. Record every tool call, with its
  arguments, result size and time, in `tool_calls` from the first day.
- **For the evaluation harness (weeks 19 to 26):** the first three metrics, one per failure kind:
  **tool-call validity** (the share of calls naming a real tool with arguments that pass the schema),
  **task success** on a fixed set of scenarios with known answers, and **steps and cost per task**. Plus
  **retrieval Recall@5** kept as a regression test, so a change to the agent can't silently break
  retrieval.

## Questions I still have

1. How would you design a tool whose output is system logs, or any tool whose output is huge and could
   fill the context?
2. Does turning RAG into agentic RAG make it more capable of answering complex questions?

## In an interview, in one sentence each

- **RAG or fine-tuning?** RAG when the model needs knowledge it doesn't have, especially if it changes
  or must be cited; fine-tuning when it needs to change how it behaves (a format, a style, a skill). They
  can be combined.
- **Why hybrid retrieval?** Keyword and vector search find different documents, so merging them by rank
  finds more: on my health RAG, hybrid beat vector alone by 5.8 points of Recall@5 and 7.8 of MRR@5,
  although its keyword half was weak on its own.
- **Why do agents fail more than single model calls?** Errors compound: at 95% per step, a 10-step task
  succeeds only 60% of the time, and each step adds cost, delay and, with write tools, real risk.