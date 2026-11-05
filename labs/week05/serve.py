"""Run the task API on localhost:8000 with one dev key.

uv run python labs/week04/auth.py     # once: prints a new key and its hash
TASKS_API_KEY_HASH=<hash> uv run python labs/week04/serve.py
"""

import os

import uvicorn
from api.app import create_app
from api.auth import READ, WRITE, Principal

app = create_app(
    {
        os.environ["TASKS_API_KEY_HASH"]: Principal(
            key_id="me", scopes=frozenset({READ, WRITE})
        )
    }
)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
