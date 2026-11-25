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
