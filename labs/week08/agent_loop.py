"""A minimal agent loop: model, tools, and a step limit. No framework."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast

Item = Any  # one Responses API input item: a message dict, a function_call_output dict, or a model output item


def as_dict(item: Item) -> dict[str, Any]:
    """One item as a typed dict: our own dicts as they are, SDK output items via model_dump()."""
    if isinstance(item, dict):
        return cast(dict[str, Any], item)
    return cast(dict[str, Any], item.model_dump())


@dataclass(frozen=True)
class ToolCall:
    id: str  # the model's call_id; results must quote it back
    name: str
    arguments: dict[str, Any]  # already parsed from the model's JSON string


@dataclass(frozen=True)
class Reply:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list[ToolCall])
    output_items: list[Item] = field(
        default_factory=list[Item]
    )  # the model's raw output, sent back as-is
    input_tokens: int = 0
    output_tokens: int = 0


class Model(Protocol):
    async def complete(
        self, items: list[Item], tools: list[dict[str, Any]]
    ) -> Reply: ...


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON Schema for the arguments
    fn: Callable[..., Any]

    def schema(self) -> dict[str, Any]:
        """The Responses API's flat tool definition."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "strict": True,
        }


@dataclass
class RunResult:
    answer: str | None
    stopped_reason: Literal["answered", "step_limit"]
    steps: int
    items: list[Item]  # the whole conversation, as sent to the model
    input_tokens: int = 0
    output_tokens: int = 0


async def call_tool(tools: dict[str, Tool], call: ToolCall) -> str:
    """Run one tool call and return its result as text. Never raises: errors become text for the model."""
    tool = tools.get(call.name)
    if tool is None:
        return (
            f"error: no tool named {call.name!r}. Available: {', '.join(sorted(tools))}"
        )
    try:
        result = await asyncio.to_thread(tool.fn, **call.arguments)
    except Exception as exc:  # noqa: BLE001  tool boundary: every failure goes back to the model as text
        return f"error: {type(exc).__name__}: {exc}"
    return json.dumps(result) if not isinstance(result, str) else result


SYSTEM = (
    "You are a careful assistant. Use the tools when they help. "
    "When you have the answer, reply in one or two sentences without calling a tool."
)


async def run(
    task: str, tools: list[Tool], model: Model, max_steps: int = 8
) -> RunResult:
    by_name = {t.name: t for t in tools}
    schemas = [t.schema() for t in tools]
    items: list[Item] = [
        {"role": "developer", "content": SYSTEM},
        {"role": "user", "content": task},
    ]
    input_tokens = output_tokens = 0

    for step in range(1, max_steps + 1):
        reply = await model.complete(items, schemas)
        input_tokens += reply.input_tokens
        output_tokens += reply.output_tokens
        items += (
            reply.output_items
        )  # the model's own turn: function calls and reasoning, unchanged

        if not reply.tool_calls:  # an answer: done
            return RunResult(
                reply.text, "answered", step, items, input_tokens, output_tokens
            )

        results = await asyncio.gather(
            *(call_tool(by_name, c) for c in reply.tool_calls)
        )
        for call, result in zip(reply.tool_calls, results, strict=True):
            items.append(
                {"type": "function_call_output", "call_id": call.id, "output": result}
            )

    return RunResult(None, "step_limit", max_steps, items, input_tokens, output_tokens)


class OpenAIModel:
    """Adapts the OpenAI Responses API to the Model protocol."""

    def __init__(self, model: str, api_key: str, base_url: str | None = None) -> None:
        from openai import AsyncOpenAI  # imported here so the tests never need it

        self._client = AsyncOpenAI(api_key=api_key, base_url=base_url or None)
        self._model = model

    async def complete(self, items: list[Item], tools: list[dict[str, Any]]) -> Reply:
        r = await self._client.responses.create(
            model=self._model,
            input=items,  # pyright: ignore[reportArgumentType]  plain dicts and output items
            tools=tools,  # pyright: ignore[reportArgumentType]
        )
        calls = [
            ToolCall(id=o.call_id, name=o.name, arguments=_parse_arguments(o.arguments))
            for o in r.output
            if o.type == "function_call"
        ]
        usage = r.usage
        return Reply(
            text=r.output_text or None,
            tool_calls=calls,
            output_items=list(r.output),
            input_tokens=usage.input_tokens if usage else 0,
            output_tokens=usage.output_tokens if usage else 0,
        )


def _parse_arguments(raw: str | None) -> dict[str, Any]:
    """The model sends arguments as a JSON string, and sometimes gets it wrong."""
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {
            "__invalid_json__": raw
        }  # the tool call then fails with a TypeError, returned as text
    if not isinstance(parsed, dict):
        return {"__not_an_object__": parsed}
    return cast(dict[str, Any], parsed)


async def _main(task: str) -> None:
    import os

    from tools import TOOLS

    model = OpenAIModel(
        os.environ["AGENT_MODEL"],
        os.environ["AGENT_API_KEY"],
        os.environ.get("AGENT_BASE_URL"),
    )
    result = await run(task, TOOLS, model, max_steps=8)
    for item in result.items[1:]:  # skip the instructions
        d = as_dict(item)
        kind = d.get("type")
        if kind == "function_call":
            print(f"call   {d['name']}({d['arguments']})  id={d['call_id']}")
        elif kind == "function_call_output":
            print(f"result {d['output']}  id={d['call_id']}")
        elif "role" in d and d["role"] != "assistant":
            print(f"text   {d['content']}")
    print(f"\nanswer: {result.answer}")
    print(
        f"{result.stopped_reason} after {result.steps} steps; "
        f"tokens in {result.input_tokens}, out {result.output_tokens}"
    )


if __name__ == "__main__":
    import sys

    asyncio.run(
        _main(
            " ".join(sys.argv[1:])
            or "What is 17 times 23, and what is the capital of France?"
        )
    )
