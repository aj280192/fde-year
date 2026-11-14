# fde-year

One year of building production AI agent systems in public, from 5 October 2026 to 3 October 2027.

I come from ML research and platform work. This repository is where I close the gap to production engineering: typed and tested services, agents on the Model Context Protocol, evaluation, security, and systems that hold up under load.

## What is here

```text
fde-year/
  notes/        weekly notes, reading notes, and a log of practice reps
  labs/         small weekly exercises, one folder per week
  capstones/    four larger projects that build on each other, plus one RAG project
```

## Capstones

| # | Project | Weeks | Status |
| --- | --- | --- | --- |
| 1 | An operations agent that diagnoses faults in a Kubernetes cluster through MCP servers | 9 to 18 | Not started |
| 2 | An evaluation and safety harness for that agent: benchmark, traces, red-team report | 19 to 26 | Not started |
| 3 | The agent as a multi-tenant platform on a public cloud, with a load test and a cost model | 27 to 36 | Not started |
| 4 | A healthcare agent on synthetic records, built for a real user from discovery to handover | 37 to 44 | Not started |
| 5 | A RAG assistant on public health guidelines: hybrid search, citations, an abstain rule, then a LangGraph retrieve-verify-answer graph | 5 to 24, alongside the others | Parts 1 to 3 done: retrieval measured; answers with citations and a code-enforced abstain rule; `POST /v1/ask` ([capstones/05-health-rag](capstones/05-health-rag)) |

Project 5 uses the Malawi health guidelines dataset published on Zindi under [CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/). The data, chunks and embeddings are not committed. Download the files from Zindi to run it.

## The year in six phases

| Phase | Weeks | Focus |
| --- | --- | --- |
| 1 | 1 to 8 | Production engineering: Python, APIs, SQL, TypeScript, testing, deployment |
| 2 | 9 to 18 | Agents and MCP |
| 3 | 19 to 26 | Evaluation, observability, reliability, security |
| 4 | 27 to 36 | Scale, access control, inference platforms, cloud |
| 5 | 37 to 44 | Working with a real user, design documents, technical writing |
| 6 | 45 to 52 | Review and consolidation |

## Working rules

- Public or synthetic data only. Nothing here comes from an employer's code, data or systems.
- Third-party datasets are credited and kept out of git, as their licences require.
- No secrets in the repository. Keys live in a local `.env` file that git ignores.
- Every capstone ships with a design document, tests, and measured results.
- A weekly note goes into `notes/` every Sunday: what I built, what broke, what is next.

## Toolchain

Python is managed with [uv](https://docs.astral.sh/uv/). Code is linted and formatted with ruff, type-checked with pyright in strict mode, and tested with pytest. A pre-commit hook runs the lint and format checks before every commit.

```bash
uv sync                      # install dependencies
uv run pre-commit install    # enable the commit hook, once per clone
uv run ruff check .          # lint
uv run ruff format .         # format
uv run pyright               # type-check
uv run pytest                # test
```

## Labs so far

| Week | Folder | What it is |
| --- | --- | --- |
| 2 | [labs/week02/toolkit](labs/week02/toolkit) | A packaged Python toolkit: strict Pydantic models with a tagged union, typed settings, JSON logging, coded errors, and a CLI with exit codes. Built as a wheel and tagged `toolkit-v0.1.0`. |
| 3 | [labs/week03](labs/week03) | A resilient LLM gateway for any OpenAI-compatible model: async client with retries, full-jitter backoff, `Retry-After`, a time budget and a concurrency limit, plus a `POST /ask` SSE endpoint with heartbeats, error events and disconnect handling. Tested against a fake model server with six failure modes (35 tests). |
| 4 | [labs/week04](labs/week04) | An HTTP API for long-running agent tasks, designed before it was built ([DESIGN.md](labs/week04/DESIGN.md)): create returns 202, API keys with read and write scopes, idempotent create, opaque cursor paging, one error shape. Refactored into domain, repository, service and API layers with an architecture test (167 tests, `openapi.json` committed). |
| 5 | [labs/week05](labs/week05) | The same API on Postgres: an Alembic-managed schema, a repository that passes the same tests as the in-memory one, a million-row index lab (235× and 42× faster with a composite and a partial index), and demos of a lost update and of `FOR UPDATE SKIP LOCKED`. |
| 6 | [labs/week06](labs/week06) | TypeScript under `strict`: the Handbook typed out by hand, the week 2 tool models rebuilt in Zod and compared with Pydantic, and a typed client for the task API (types generated from its OpenAPI spec, every response checked with Zod, a cancellable server-sent-events stream). Reps in TypeScript. |
| 5 | [capstones/05-health-rag](capstones/05-health-rag) | Retrieval over six health-guideline booklets: keyword, vector and hybrid search in Postgres, a labelled test set with a held-out split, chunking experiments and a cross-encoder reranker, every run recorded in `results.csv`. Design: [Q1_Retrieval_Design.md](capstones/05-health-rag/Q1_Retrieval_Design.md). |

To try week 3 by hand against a local [Ollama](https://ollama.com) model:

```bash
uv run python labs/week03/serve.py
curl -N -X POST localhost:8000/ask -H 'content-type: application/json' \
     -d '{"question": "Why do pods restart?"}'
```

## Progress

| Week | Dates | Topic | Note |
| --- | --- | --- | --- |
| 1 | 5 to 11 Oct 2026 | Baseline and setup | [notes/week01.md](notes/week01.md) |
| 2 | 12 to 18 Oct 2026 | Production Python | [notes/week02.md](notes/week02.md) |
| 3 | 19 to 25 Oct 2026 | Async, streaming and failure handling | [notes/week03.md](notes/week03.md) |
| 4 | 26 Oct to 1 Nov 2026 | API design | [notes/week04.md](notes/week04.md) |
| 5 | 2 to 8 Nov 2026 | Data and SQL; retrieval you can measure | [Q1_Retrieval_Design.md](capstones/05-health-rag/Q1_Retrieval_Design.md) |
| 6 | 9 to 15 Nov 2026 | TypeScript, the language | [notes/week06.md](notes/week06.md) |

## Licence

MIT. See [LICENSE](LICENSE).