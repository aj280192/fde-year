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

| Area | Before | After |
| --- | --- | --- |
| `services.py` | 100% | |
| `serve.py` | 0% | |
| `rag_adapter.py` | — | |
| Application code | 98% | |
| Tests passed | 272 | |

## Wed 25 Nov · Agent loop
