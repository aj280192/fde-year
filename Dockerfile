# syntax=docker/dockerfile:1

# ---- Stage 1: build the virtual environment ----
FROM python:3.13-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.13.10 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Dependencies first, in their own layer: rebuilt only when the lock file changes.
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-default-groups --group agent

# ---- Stage 2: the image that runs ----
FROM python:3.13-slim AS runtime

# A user with no password and no shell login: the app never runs as root.
RUN useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --chown=app:app labs/week05 /app/labs/week05

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

USER app
WORKDIR /app/labs/week05
EXPOSE 8080

CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]
