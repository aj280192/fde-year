# Week 7 · 16 to 22 November 2026

Planned as the TypeScript front-end week. On 19 November I changed the plan: no TypeScript from here
on, and the week became agent reading, my first AI-assisted coding rep, and a Python demo page for
the health RAG assistant.

---

## What I built

- **`POST /v1/tasks/{id}:retry`** (Fri), through AI-assisted rep 1. A failed task is retried by
  creating a new queued task with the same input; the failed one stays failed, because `failed` is
  terminal in the state machine.
- **A `sources` event on `POST /v1/ask`** (Sat): every retrieved paragraph with its id, score and
  text, best score first, sent after an answer and after an abstention. DESIGN.md now has a full
  `/v1/ask` section, which it was missing.
- **A Streamlit demo page** (Sun): a question box, a working status, the answer with its citations,
  a calm message when it abstains, and every source as an expandable row with the cited ones
  marked. Errors (API down, wrong key, not configured, timeout) show one plain sentence, and a
  Retry button where retrying can help.
- **Ten demo questions**, nine from the tuning set and one of mine to test abstaining, in `capstones/05-health-rag/demo_outputs.md`.
- **`AGENTS.md`** at the root of the repository, with eight lessons from past mistakes.
- **Reading notes:** the Anthropic and OpenAI agent guides (Thu), *Designing AI Interfaces* ch. 5 (Sat).

## What broke, and what I learned

- **My spoken plan contradicted my own tests.** In the rep I said "set the failed task back to
  queued and add one to attempts". The tests and DESIGN.md said a retry is a new task. The agent
  stopped and pointed it out before writing any code. Lesson: the tests are the spec, and I should
  read my own design before describing a change.
- **`sorted()` did nothing.** In `serve.py` I wrote `sorted(a.sources, ...)` without keeping the
  result, so sources weren't sorted. The tests didn't catch it because the fake sources were
  already in order, and nothing tests the adapter in `serve.py`. Fixed; the adapter needs a test.
- **Streamlit's rerun model.** The whole script reruns on every click, so the answer vanished when
  I opened a source until I kept it in `st.session_state`. A button inside a form can't have a
  callback; my display code was indented inside the form.

## What the demo showed

From ten demo questions (details in `demo_outputs.md`):

- The right paragraph was found in 7 of 9, but the system often cites a **related neighbour** as
  well: a definition, a line list, a paragraph that repeats a word from the question.
- **q232 found nothing relevant and answered anyway.** That is the case I most need to fix: it
  should have abstained.
- Answers that span **several paragraphs** come back incomplete (q283), which points at chunking.
- **It abstained correctly on a hard one:** a statin dose question, a health topic the booklets
  don't cover. The page showed the calm message, the reason and what it searched. So the abstain
  rule works; q232 must have scored just above the threshold.

## What I would tell a customer

The assistant answers questions from the six health booklets and shows the paragraphs it used, so
every answer can be checked. It is usually right about where the answer is, but it sometimes cites
an extra related paragraph and, rarely, answers when it should say it doesn't know, so it should
support a health worker's reading of the booklets, not replace it.

## The plan change on 19 November, and why

I read 13 current Singapore job postings. They ask for Python with RAG and agent experience, plus
evaluation, monitoring and deployment. None required TypeScript on its own. So:

- TypeScript, React and Next.js are dropped from week 7 on; week 6's typed client stays as done work.
- Phase 4 shrinks from ten weeks to six (weeks 27 to 32).
- A new multi-agent capstone, 3B, a service desk under 15 agent controls, takes weeks 33 to 36.
- Applications for AI and agent engineer roles start in week 27; FDE applications still start in week 37.

## Agents: what my system already has

From the figure in *An Illustrated Guide to AI Agents* ch. 1 (photo below).

| Part | Status |
| --- | --- |
| User input (`POST /v1/tasks`) | ✅ built |
| Task state machine, including `waiting_for_input` for a person in the loop | ✅ built |
| Least privilege (read and write scopes) and a stop button (`:cancel`) | ✅ built |
| Tracing (`runs`, `tool_calls` tables) | ◐ designed, nothing writes them yet |
| Tools (`ToolSpec`, `ToolCall`, `ToolResult` from week 2) | ◐ schemas exist, no model chooses them yet |
| The model loop, step and budget limits, memory, planning | ⏳ from Wed 25 Nov |


## AI-assisted rep 1

| Task | Minutes | Corrections | Lesson added to AGENTS.md |
| --- | --- | --- | --- |
| `:retry` endpoint with Claude Code | 10 | 0 | If my instructions conflict with the tests or DESIGN.md, stop and say so before writing code |

The agent also found that `openapi.json` was already missing `/v1/ask`, and said so instead of
quietly regenerating it.

## Rules for the demo page (from *Designing AI Interfaces* ch. 5)

1. Ground every answer in the sources, and abstain when they don't support one.
2. When it abstains, say why in plain words and show what was searched.
3. Present the answer so it is readable and actionable, with the sources beside it.

Full note and the 12 checks: `notes/reading/designing-ai-interfaces-ch05.md`.

## Next week

Week 8: the agent loop starts on Wed 25 Nov, read-only tools first, with a turn limit as its exit.