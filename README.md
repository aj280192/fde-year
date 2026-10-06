# fde-year

One year of building production AI agent systems in public, from 5 October 2026 to 3 October 2027.

I come from ML research and platform work. This repository is where I close the gap to production engineering: typed and tested services, agents on the Model Context Protocol, evaluation, security, and systems that hold up under load.

## What is here

```text
fde-year/
  notes/        weekly notes, reading notes, and a log of practice reps
  labs/         small weekly exercises, one folder per week
  capstones/    four larger projects that build on each other
```

## Capstones

| # | Project | Weeks | Status |
| --- | --- | --- | --- |
| 1 | An operations agent that diagnoses faults in a Kubernetes cluster through MCP servers | 9 to 18 | Not started |
| 2 | An evaluation and safety harness for that agent: benchmark, traces, red-team report | 19 to 26 | Not started |
| 3 | The agent as a multi-tenant platform on a public cloud, with a load test and a cost model | 27 to 36 | Not started |
| 4 | A healthcare agent on synthetic records, built for a real user from discovery to handover | 37 to 44 | Not started |

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

## Progress

| Week | Dates | Topic | Note |
| --- | --- | --- | --- |
| 1 | 5 to 11 Oct 2026 | Baseline and setup | [notes/week01.md](notes/week01.md) |

## Licence

MIT. See [LICENSE](LICENSE).
