import pytest
from pydantic import ValidationError
from toolkit.models import ToolCall, ToolResult, ToolSpec


def test_toolcall_name_validation() -> None:
    payload = '{"id": "123", "arguments": {"pod": "api-7f9", "lines": 100}}'
    with pytest.raises(ValidationError) as exc_info:
        ToolCall.model_validate_json(payload)
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("name",)
    assert error["type"] == "missing"


def test_toolcall_arguments_validation() -> None:
    payload = '{"id": "123", "name": "test_tool", "arguments": "api-7f9"}'
    with pytest.raises(ValidationError) as exc_info:
        ToolCall.model_validate_json(payload)
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("arguments",)
    assert error["type"] == "dict_type"


def test_toolcall_extra_validation() -> None:
    payload = '{"id": "123", "name": "test_tool", "arguments": {"pod": "api-7f9", "lines": 100}, "extra_field": "extra_value"}'
    with pytest.raises(ValidationError) as exc_info:
        ToolCall.model_validate_json(payload)
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("extra_field",)
    assert error["type"] == "extra_forbidden"


def test_toolresult_kind_done() -> None:
    payload = '{"call_id": "123", "outcome": {"kind": "done", "content": "This should not be allowed"}}'
    with pytest.raises(ValidationError) as exc_info:
        ToolResult.model_validate_json(payload)
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("outcome",)
    assert error["type"] == "union_tag_invalid"


def test_toolresult_kind_message() -> None:
    payload = '{"call_id": "123", "outcome": {"kind": "error", "content": "This should not be allowed"}}'
    with pytest.raises(ValidationError) as exc_info:
        ToolResult.model_validate_json(payload)
    error = exc_info.value.errors()[0]
    assert error["loc"] == (
        "outcome",
        "error",
        "content",
    )
    assert error["type"] == "extra_forbidden"


def test_toolspec_name_validation() -> None:
    payload = '{"name": 43, "description": "A tool without a name", "input_schema": {"param": "value"}}'
    with pytest.raises(ValidationError) as exc_info:
        ToolSpec.model_validate_json(payload)
    error = exc_info.value.errors()[0]
    assert error["loc"] == ("name",)
    assert error["type"] == "string_type"
