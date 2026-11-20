# AGENTS.md

## What this repo is
`fde-year`: my public, one-year plan to become an AI and agent engineer and Forward Deployed
Engineer (Oct 2026 to Oct 2027). Notes, weekly labs and capstone projects. Python only.

## Layout
- `notes/` weekly notes, `reps.csv`, `reading/`, `papers/`. Written by me.
- `labs/weekNN/` one lab per week, each with its own README.
- `capstones/` 01-ops-agent, 02-evals, 03-platform, 03b-service-desk, 04-engagement,
  05-health-rag (FastAPI + Postgres/pgvector + a local model; `POST /v1/ask`).
- `failure-drills.md` results of the production drills.

## Commands (run from the project folder you are changing)
- Install: `uv sync`
- Test: `uv run pytest`
- Type-check: `uv run pyright`
- Services: `docker compose up -d` (Postgres with pgvector)
- Migrations: `uv run alembic upgrade head`. Ask before creating or running one.

## Conventions
- Python 3.12, type hints everywhere, Pydantic models for every request, response and tool schema.
- Write or update a test first; a change is done when pytest and pyright both pass.
- Small diffs: change only what the task needs. No new dependency without asking.
- Errors are explicit: no bare `except`, no swallowed exceptions, timeouts on every network call.
- Keep `DESIGN.md` and the API schema in step with any change to an endpoint.
- Configuration comes from environment variables (for example `HEALTH_RAG_MODEL`), never hardcoded.

## Never
- Edit a test to make it pass, or delete or skip a failing test.
- Read, print or commit `.env`, API keys or any secret.
- Commit anything under `capstones/05-health-rag/data/`, or quote booklet text in committed files.
  The data licence forbids sharing it; commit only ids and scores.
- Touch `notes/`: those are my own words.
- Add bank (employer) code, data, hostnames or internal details anywhere. Public or synthetic data only.
- Run `git push`, rewrite history, drop tables or delete files without asking.
- Add TypeScript, Node packages or a JavaScript front end. Demo pages use Streamlit or Gradio.

## When unsure
Stop and ask. Say the plan before writing code, and list every file you will change.

## Lessons from past mistakes
<!-- one line per mistake; add one after each rep -->
- Never overwrite an existing file wholesale (a week 5 README was lost this way). Edit it, or ask.
- This is macOS: BSD `sed` needs `sed -i ''`. Prefer a small Python script for multi-file edits.
- Check every evaluation label against the data before trusting a metric (one label was malformed).
- The held-out test set is used once, at the end. Tune only on the tuning set.
- A change under 2 points of Recall@5 is noise; do not call it a win.
- pgvector: normalise embeddings and pass them as a `vector`, not a Python list.
- Endpoints are versioned: `/v1/ask`, not `/ask`.