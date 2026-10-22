"""A fake OpenAI-compatible model server for tests: canned answers, no real model, no cost."""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ANSWER = "Pods restart when the liveness probe fails three times in a row."
WORD_DELAY_SECONDS = 0.05

app = FastAPI()

# What the server saw during the last streamed answer. Tests read this.
last_stream = {"words_sent": 0, "closed_early": False}


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
            piece = word if index == 0 else f" {word}"
            yield sse({"choices": [{"index": 0, "delta": {"content": piece}}]})
            last_stream["words_sent"] += 1
        yield sse("[DONE]")
    except asyncio.CancelledError:
        last_stream["closed_early"] = True
        raise


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    request: ChatRequest,
) -> dict[str, object] | StreamingResponse:
    if request.stream:
        return StreamingResponse(stream_words(), media_type="text/event-stream")
    return {
        "choices": [{"index": 0, "message": {"role": "assistant", "content": ANSWER}}]
    }
