# Week 8 · a minimal agent loop

`run(task, tools, model, max_steps)`: asks the model, runs the tools it requests (several at once),
sends each result back by call id, and stops at `max_steps` with `stopped_reason="step_limit"`.
Tool errors are returned to the model as text, never raised.

The loop depends on a small `Model` protocol. `OpenAIModel` adapts the OpenAI Responses API; the tests
use `FakeModel`, with scripted replies and no network.

    set -a; source .env; set +a                 # AGENT_API_KEY, AGENT_MODEL
    uv run python labs/week08/agent_loop.py "What is 17 times 23?"
    uv run pytest labs/week08                    # no key needed
