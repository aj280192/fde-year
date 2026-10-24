"""A fake OpenAI-compatible model server for tests: canned answers, no real model, no cost."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

ANSWER = "Pods restart when the liveness probe fails three times in a row."
WORD_DELAY_SECONDS = 0.05

app = FastAPI()

# What the server saw during the last streamed answer. Tests read this.
last_stream = {"words_sent": 0, "closed_early": False}


class FakeState(BaseModel):
    mode: str = "ok"
    requests: int = 0


FAKE = FakeState()


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[Message]
    stream: bool = False


def sse(payload: dict[str, object] | str) -> str:
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return f"data: {data}\n\n"


async def stream_words() -> AsyncIterator[str]:
    words = ANSWER.split(" ")
    last_stream["words_sent"] = 0
    last_stream["closed_early"] = False
    try:
        for index, word in enumerate(words):
            await asyncio.sleep(WORD_DELAY_SECONDS)

            if FAKE.mode == "drop" and index > 2:
                raise RuntimeError("simulated drop")

            piece = word if index == 0 else f" {word}"
            yield sse({"choices": [{"index": 0, "delta": {"content": piece}}]})
            last_stream["words_sent"] += 1

            if FAKE.mode == "hang" and index == 0:
                await asyncio.sleep(60)

        yield sse(
            {
                "choices": [],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": last_stream["words_sent"],
                    "total_tokens": 10 + last_stream["words_sent"],
                },
            }
        )
        yield sse("[DONE]")
    except asyncio.CancelledError:
        last_stream["closed_early"] = True
        raise


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: ChatRequest,
) -> dict[str, object] | Response:
    FAKE.requests += 1

    if FAKE.mode == "server_error":
        return JSONResponse({"error": "server_error"}, status_code=503)

    if FAKE.mode == "rate_limited":
        return JSONResponse(
            {"error": "slow_down"}, status_code=429, headers={"Retry-After": "1"}
        )

    if FAKE.mode == "rate_limited_twice" and FAKE.requests <= 2:
        return JSONResponse(
            {"error": "slow_down"}, status_code=429, headers={"Retry-After": "1"}
        )

    if request.stream:
        return StreamingResponse(stream_words(), media_type="text/event-stream")
    if FAKE.mode == "hang":
        await asyncio.sleep(60)

    return {
        "choices": [{"index": 0, "message": {"role": "assistant", "content": ANSWER}}]
    }
