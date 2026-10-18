import pytest
from toolkit.errors import (
    AppError,
    RateLimitedError,
    ToolFailedError,
    UpstreamTimeoutError,
    ValidationFailedError,
)


def test_base_app_error_code() -> None:
    assert AppError("x").code == "app_error"


@pytest.mark.parametrize(
    "cls, expected_code",
    [
        (ValidationFailedError, "validation_failed_error"),
        (UpstreamTimeoutError, "upstream_timeout_error"),
        (RateLimitedError, "rate_limited_error"),
        (ToolFailedError, "tool_failed_error"),
    ],
)
def test_subclass_hierarchy_and_attributes(
    cls: type[AppError], expected_code: str
) -> None:
    instance: AppError = cls("boom")
    assert instance.code == expected_code

    with pytest.raises(AppError):
        raise cls("boom")

    assert str(instance) == "boom"
