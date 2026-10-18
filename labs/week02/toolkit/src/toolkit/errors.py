from typing import ClassVar


class AppError(Exception):
    """Base class for all application-specific errors."""

    code: ClassVar[str] = "app_error"


class ValidationFailedError(AppError):
    """Raised when validation of input data fails."""

    code: ClassVar[str] = "validation_failed_error"


class UpstreamTimeoutError(AppError):
    """Raised when an upstream service times out."""

    code: ClassVar[str] = "upstream_timeout_error"


class RateLimitedError(AppError):
    """Raised when a rate limit is exceeded."""

    code: ClassVar[str] = "rate_limited_error"


class ToolFailedError(AppError):
    """Raised when a tool fails to execute properly."""

    code: ClassVar[str] = "tool_failed_error"
