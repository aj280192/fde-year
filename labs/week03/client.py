"""An async client for any OpenAI-compatible chat endpoint: one complete call, one streamed call."""

from collections.abc import AsyncIterator
from types import TracebackType
from typing import Self

import httpx
from pydantic import BaseModel, ConfigDict

# Providers add fields over time, so responses ignore unknown fields rather than reject them.
LENIENT = ConfigDict(extra="ignore")


class Message(BaseModel):
    model_config = LENIENT
    content: str


class Choice(BaseModel):
    model_config = LENIENT
    message: Message


class Completion(BaseModel):
    model_config = LENIENT
    choices: list[Choice]


class Delta(BaseModel):
    model_config = LENIENT
    content: str | None = None


class ChunkChoice(BaseModel):
    model_config = LENIENT
    delta: Delta


class Chunk(BaseModel):
    model_config = LENIENT
    choices: list[ChunkChoice]


class LLMClient:
    def __init__(self, base_url: str, model: str, api_key: str = "not-needed") -> None:
        self.model = model
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0),
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self._http.aclose()

    def _body(self, prompt: str, *, stream: bool) -> dict[str, object]:
        return {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": stream,
        }

    async def complete(self, prompt: str) -> str:
        response = await self._http.post(
            "/chat/completions", json=self._body(prompt, stream=False)
        )
        response.raise_for_status()
        return (
            Completion.model_validate_json(response.content).choices[0].message.content
        )

    async def stream(self, prompt: str) -> AsyncIterator[str]:
        body = self._body(prompt, stream=True)
        async with self._http.stream(
            "POST", "/chat/completions", json=body
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line.startswith("data: "):
                    continue  # blank lines and comments separate events
                data = line.removeprefix("data: ")
                if data == "[DONE]":
                    return
                chunk = Chunk.model_validate_json(data)
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
