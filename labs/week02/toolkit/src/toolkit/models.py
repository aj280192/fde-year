from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ToolSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    name: str
    description: str
    input_schema: dict[str, JsonValue]


class ToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str
    name: str
    arguments: dict[str, JsonValue]


class ToolSuccess(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["success"]
    content: str


class ToolError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["error"]
    message: str


class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    call_id: str
    outcome: ToolSuccess | ToolError = Field(discriminator="kind")
