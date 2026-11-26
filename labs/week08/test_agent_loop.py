"""The agent loop, tested with scripted replies: no network, no key, no cost."""

import asyncio
import copy
import json
from typing import Any

from agent_loop import Item, Reply, RunResult, Tool, ToolCall, as_dict, run


def asks(*calls: ToolCall) -> Reply:
    """A scripted reply that requests tools, with output items shaped like the Responses API's."""
    items = [
        {
            "type": "function_call",
            "call_id": c.id,
            "name": c.name,
            "arguments": json.dumps(c.arguments),
        }
        for c in calls
    ]
    return Reply(text=None, tool_calls=list(calls), output_items=items)


def says(text: str) -> Reply:
    """A scripted final answer."""
    return Reply(text=text, output_items=[{"role": "assistant", "content": text}])


class FakeModel:
    """Returns scripted replies in order, and records what it was sent each time."""

    def __init__(self, replies: list[Reply]) -> None:
        self._replies = list(replies)
        self.seen: list[list[Item]] = []

    async def complete(self, items: list[Item], tools: list[dict[str, Any]]) -> Reply:
        self.seen.append(
            copy.deepcopy(items)
        )  # a copy: the loop keeps appending to the list
        if not self._replies:
            raise AssertionError("FakeModel ran out of scripted replies")
        return self._replies.pop(0)


def echo_tool(name: str = "echo") -> Tool:
    def echo(value: str) -> str:
        return f"{name}:{value}"

    return Tool(
        name,
        "Echo the value.",
        {"type": "object", "properties": {"value": {"type": "string"}}},
        echo,
    )


def go(task: str, tools: list[Tool], model: FakeModel, max_steps: int = 8) -> RunResult:
    return asyncio.run(run(task, tools, model, max_steps))


def outputs(items: list[Item]) -> dict[str, str]:
    """call_id → output, for every tool result in the conversation."""
    ds = [as_dict(i) for i in items]
    return {
        d["call_id"]: d["output"] for d in ds if d.get("type") == "function_call_output"
    }


def calls_sent_back(items: list[Item]) -> list[str]:
    """The call_ids of the model's own function_call items, as the loop sent them back."""
    ds = [as_dict(i) for i in items]
    return [d["call_id"] for d in ds if d.get("type") == "function_call"]


def test_answers_on_step_2_after_one_tool_call() -> None:
    model = FakeModel(
        [
            asks(ToolCall("call_1", "echo", {"value": "hi"})),
            says("The echo said hi."),
        ]
    )
    result = go("say hi", [echo_tool()], model)

    assert result.stopped_reason == "answered"
    assert result.answer == "The echo said hi."
    assert result.steps == 2
    assert calls_sent_back(model.seen[1]) == ["call_1"]  # its own call went back first
    assert outputs(model.seen[1]) == {
        "call_1": "echo:hi"
    }  # then the result, by its call_id


def test_step_limit_stops_a_model_that_never_answers() -> None:
    always_calls = [asks(ToolCall(f"c{i}", "echo", {"value": "x"})) for i in range(20)]
    model = FakeModel(always_calls)
    result = go("loop forever", [echo_tool()], model, max_steps=3)

    assert result.stopped_reason == "step_limit"
    assert result.answer is None
    assert result.steps == 3
    assert len(model.seen) == 3  # never more model calls than max_steps


def test_two_tool_calls_in_one_reply_both_answered_by_id() -> None:
    model = FakeModel(
        [
            asks(
                ToolCall("a", "left", {"value": "1"}),
                ToolCall("b", "right", {"value": "2"}),
            ),
            says("done"),
        ]
    )
    result = go("both", [echo_tool("left"), echo_tool("right")], model)

    assert result.answer == "done"
    assert outputs(model.seen[1]) == {"a": "left:1", "b": "right:2"}


def broken_tool() -> Tool:
    def fail(value: str) -> str:
        raise TimeoutError("upstream timed out")

    return Tool("broken", "Always fails.", {"type": "object", "properties": {}}, fail)


def test_a_failing_tool_is_reported_to_the_model_not_raised() -> None:
    model = FakeModel(
        [
            asks(ToolCall("x", "broken", {"value": "v"})),
            says("The tool failed, so I can't answer."),
        ]
    )
    result = go("try it", [broken_tool()], model)

    assert result.stopped_reason == "answered"
    assert outputs(model.seen[1])["x"].startswith("error: TimeoutError")


def test_an_unknown_tool_name_is_reported_to_the_model() -> None:
    model = FakeModel([asks(ToolCall("u", "no_such_tool", {})), says("ok")])
    go("try it", [echo_tool()], model)
    assert "no tool named 'no_such_tool'" in outputs(model.seen[1])["u"]


def test_wrong_arguments_are_reported_to_the_model() -> None:
    model = FakeModel([asks(ToolCall("w", "echo", {"wrong": "field"})), says("ok")])
    go("try it", [echo_tool()], model)
    assert outputs(model.seen[1])["w"].startswith("error: TypeError")
