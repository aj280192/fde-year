# Week 8 · 23 to 29 November 2026 · Test, ship and review

## Tue 24 and Wed 25 Nov · pytest
### Coverage before, 25 Nov (B1)

`uv run pytest labs/week05 --cov=labs/week05 --cov-report=term-missing -q`: 272 passed in 2.2 s, on
both stores (memory and Postgres). Test files, `conftest.py` and the demo scripts are left out of the
measurement (`[tool.coverage.run] omit` in `pyproject.toml`).

| Area | Statements | Covered | Not covered |
| --- | --- | --- | --- |
| `services.py` | 57 | **100%** | — |
| `domain/` (task, errors, idempotency) | 69 | **100%** | — |
| `repository.py` (protocol and in-memory store) | 40 | **100%** | — |
| `db/` (models, engine, Postgres repository) | 121 | 98% | `db/repository.py` lines 51, 139 |
| `api/` | 269 | 96% | `auth.py` 21, 25–29; `errors.py` 47–48, 162, 215–216; `app.py` 38 |
| `serve.py` | 31 | **0%** | the whole file |
| **Total** | **587** | **93%** | 44 lines, 31 of them in `serve.py` |

**What it means:**
- The service layer and the domain were already at 100%, above the plan's 80% target.
- Without `serve.py`, the rest is at 98% (13 missed lines out of 556).
- **`serve.py` is the gap:** it holds the RAG-to-API conversion that hid Saturday's `sorted()` bug.
- B8 and B9 weren't needed: both idempotency paths were already covered.
- **Truncate, not rollback:** the suite runs in 2.2 s and the slowest fixture setup is 0.04 s, so
  rolling back would gain almost nothing. Recorded in DESIGN.md.

### Coverage after (B12)

`uv run pytest labs/week05 --cov=labs/week05 --cov-report=term-missing -q -rs`: 285 passed in 2.3 s,
none skipped, on both stores.

| Area | Before | After | Change |
| --- | --- | --- | --- |
| `services.py` | 100% | 100% | — |
| `domain/` | 100% | 100% | — |
| `db/repository.py` | 97% | 97% | — |
| `api/auth.py` | 72% | 72% | not tested yet (lines 21, 25–29) |
| `rag_adapter.py` | — | **100%** (8 statements) | new: the conversion moved out of `serve.py` |
| `serve.py` | 0% | 0% | expected: what's left only starts the server and loads the models |
| **Total** | 93% (587 statements) | **93%** (595 statements) | — |
| Application code without `serve.py` | 98% | 98% | — |
| Tests run | 272 | **285** | +13 |

**What changed, and what didn't:**
- The number barely moved, and that's the honest result: coverage was already high. Today's value
  was in *what* got tested. The RAG-to-API conversion that hid Saturday's `sorted()` bug now has its
  own tests, and I watched the first one fail on the broken version.
- The 13 new runs come from the table-driven create-error test and the adapter tests, each on both
  stores where the repository is involved.
- `serve.py` stays at 0% on purpose. Testing it would mean starting the server and loading the
  embedding and reranking models, and that belongs in an end-to-end check, not in unit tests.
- **Lesson from a mistaken run:** in a new terminal without `TEST_DATABASE_URL`, 96 tests were
  silently skipped and the total fell to 86%, with nothing red on screen. A skipped test is not a
  passed test. Run with `-rs`, and make Postgres required in CI (Thursday).

## Wed 25 Nov · Agent loop

### What I built
`labs/week08/agent_loop.py`: `run(task, tools, model, max_steps=8)`, with no framework. Each step sends
the conversation and the tool descriptions to the model. If the model asks for tools, the loop runs
them all at once and sends each result back by its `call_id`; if it answers, the loop returns. At
`max_steps` it stops with `stopped_reason="step_limit"` and no answer, so it can never run forever.
That's control 1 of the 15 agent controls.

Three toy tools in `tools.py`: `calculator` (four operations, never `eval`), `lookup` (a small dict of
facts) and `flaky` (fails half the time). A tool that fails, an unknown tool name and wrong arguments
all come back to the model as error text; the loop never crashes on them.

### The design choice that mattered
The loop doesn't call the OpenAI SDK. It depends on a small `Model` protocol of my own (`complete(items,
tools) -> Reply`). `OpenAIModel` adapts the real API to it, and `FakeModel` returns scripted replies for
tests. Same idea as the repository in *Architecture Patterns* ch. 2 and 3: the tests need no network
and no key, and changing provider means writing one adapter, not touching the loop.

### What changed while building it
- **Chat Completions → Responses API.** My first plan used Chat Completions. OpenAI's function-calling
  guide now leads with the Responses API, and its newest models need it for tool calling.
- **The tool schema is flat:** `{"type": "function", "name", "description", "parameters", "strict"}`,
  not the nested `"function": {...}` shape. My first version was wrong here, and the API told me.
- **The model's own output goes back unchanged, before the results.** The API needs its
  `function_call` items, and any reasoning items, back before it accepts the `function_call_output`
  items. So `Reply` carries the raw `output_items`, and the loop replays them without looking inside.
- **`strict: true`** makes the model's arguments follow the schema exactly, which needs every
  property in `required` and `additionalProperties: false`.

### Tests (no network, no key)
`env -u AGENT_API_KEY uv run pytest labs/week08`: 6 passed.
- answers on step 2 after one tool call, and sends its own call back first
- the step limit stops a model that never answers, after exactly `max_steps` model calls
- two tool calls in one reply, both results matched by `call_id`
- a failing tool, an unknown tool and wrong arguments each come back as error text

### The real model (C9)
Model: gpt-6-luna (small, on a personal key with a spending limit)

| Task | Steps | What happened | Tokens in / out |
| --- | --- | --- | --- |
| "What is 17 times 23, and what is the capital of France?" | 2 | **Parallel calls:** `calculator` and `lookup` requested in **one** reply, run together, both results sent back by `call_id`; then the answer "17 × 23 = 391, and the capital of France is Paris." | 426 / 77 |
| "Use the flaky tool to echo hello, retrying if it fails." (run 1) | 2 | `flaky` succeeded first time; answered "hello" | 380 / 23 |
| The same task (run 2) | 3 | `flaky` failed with `TimeoutError`; the error came back **as text**, the model **retried** on its own with a new call, the retry succeeded, then it answered | 628 / 41 |

**What I learned from the runs:**
- **The model chose parallel calls by itself** when the two questions didn't depend on each other.
  One step instead of two saves a full model round trip.
- **Returning errors as text works:** the loop didn't crash, and the model read the error and retried,
  because the tool's description said retrying may help. The description is part of the interface.
- **Every step resends the whole conversation,** so cost grows with steps: one extra step (the retry)
  took input from 380 to 628 tokens, about 65 percent more for the same task. That's why the token
  budget (control 3) is next week's work, and why the step limit also caps cost.
- **The final answer to the flaky task was just "hello":** correct, but it didn't say it had needed a
  retry. For an operations agent I'd want the answer to mention what failed along the way; that's a
  prompt or a trace question for Phase 2.
  
### What the step limit protects against
A model that keeps calling tools without converging, for example retrying a broken tool forever,
would cost money and time with no answer. The limit caps the number of model calls, so the worst case
is known in advance, and the result says plainly that it stopped because of the limit rather than
pretending to have answered.

## Thu 26 Nov · Container and pipeline
(done Fri 27 Nov)

### The app, made ready for a container
- **Postgres when `DATABASE_URL` is set**, memory otherwise. Before this, `serve.py` always used the
  in-memory store, so every restart lost every task. A task now survives a restart, locally and in
  the container.
- **`GET /healthz`**: no key, not in the schema, and it doesn't check the database. A liveness check
  that failed whenever Postgres was slow would make the platform restart a healthy container;
  checking dependencies is a readiness check, for later.
- **Dependency groups:** `sentence-transformers` (and with it PyTorch), Streamlit, the OpenAI SDK and
  openpyxl moved out of the core dependencies into `rag`, `demo`, `agent` and `data` groups. My
  machine still installs everything by default; the image installs only the core. It works because
  `serve.py` imports the RAG packages only when `HEALTH_RAG_DATABASE_URL` is set.

### The image
- Multi-stage: uv builds the environment in the first stage, and only `.venv` and `labs/week05` reach
  the second. uv is pinned to a version, never `latest`.
- Size: FILL MB. `import torch` fails inside it, which proves PyTorch stayed out.
- Runs as a user called `app`, not root: someone who breaks into the app isn't root in the container.
- Listens on `0.0.0.0:8080`. `127.0.0.1` inside a container is reachable only from inside it; 8080
  is Cloud Run's default.
- No secrets in the image: the key hash and the database URL are given when the container starts.
- `.dockerignore` keeps `.env`, `.venv`, `.git`, notes and the booklet data out of the build.

### The pipeline
Four jobs on every pull request and every push to `main`: `lint`, `typecheck`, `test` (on a real
Postgres service, with `-rs` to show nothing was skipped) and `build`, which waits for the other three.
Actions are pinned to commit hashes, and the workflow can only read the repository.

| Run | What | Result | Time |
| --- | --- | --- | --- |
| 1 | first pull request | failed | 2m 18s |
| 2 | first fix | failed | 1m 19s |
| 3 | second fix | passed | 1m 55s |
| 5 | merge to `main` | passed | 2m 25s |

**Failed in CI, passed locally:** pyright couldn't find the week 2 `toolkit` package, and ruff sorted
its imports differently. On my laptop it resolved because it was installed in my local environment;
CI starts from a clean checkout. The fix was to tell both tools where it lives
(`labs/week02/toolkit/src` in pyright's `extraPaths` and ruff's `src`). That's the point of CI: it
catches what only works on my machine.

### The rule for `main`
`main` takes changes only through a pull request with all four checks green, and the rule applies to
me too. Every change now goes branch → pull request → green checks → squash merge.

### Next
- Wed 2 Dec: the other controls on this loop: a tool-call budget, a token budget, loop detection and
  an approval gate for risky tools.
- A Chat Completions adapter, so the same loop runs on a local Qwen through Ollama or vLLM.
