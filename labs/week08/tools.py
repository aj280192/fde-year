"""Three toy tools for the agent loop. Plain functions; the loop adds the descriptions."""

import random

from agent_loop import Tool

FACTS = {
    "capital of france": "Paris",
    "boiling point of water": "100 °C at sea level",
    "speed of light": "299,792 km/s",
}


def calculator(a: float, b: float, op: str) -> float:
    """Never eval() text from a model: only these four operations exist."""
    if op == "add":
        return a + b
    if op == "subtract":
        return a - b
    if op == "multiply":
        return a * b
    if op == "divide":
        return (
            a / b
        )  # ZeroDivisionError reaches the loop, which returns it as error text
    raise ValueError(f"unknown op {op!r}; use add, subtract, multiply or divide")


def lookup(key: str) -> str:
    return FACTS.get(key.lower().strip(), f"no fact stored for {key!r}")


def flaky(value: str) -> str:
    if random.random() < 0.5:
        raise TimeoutError("flaky tool timed out")
    return f"flaky tool echoed {value!r}"


TOOLS = [
    Tool(
        "calculator",
        "Do one arithmetic operation on two numbers.",
        {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "number"},
                "op": {
                    "type": "string",
                    "enum": ["add", "subtract", "multiply", "divide"],
                },
            },
            "required": ["a", "b", "op"],
            "additionalProperties": False,
        },
        calculator,
    ),
    Tool(
        "lookup",
        "Look up a stored fact by a short key, such as 'capital of france'.",
        {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
            "additionalProperties": False,
        },
        lookup,
    ),
    Tool(
        "flaky",
        "Echo a value. Fails about half the time; retrying may help.",
        {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
            "additionalProperties": False,
        },
        flaky,
    ),
]
