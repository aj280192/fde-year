"""Run /ask against a real model by hand. Default: Ollama on this machine.

    uv run python labs/week03/serve.py
    curl -N -X POST localhost:8000/ask -H 'content-type: application/json' \
         -d '{"question": "Why do pods restart?"}'
"""

import os

import uvicorn
from app import create_app
from client import LLMClient

client = LLMClient(
    os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1"),
    model=os.environ.get("LLM_MODEL", "llama3.2"),
)

if __name__ == "__main__":
    uvicorn.run(create_app(client), host="127.0.0.1", port=8000)
