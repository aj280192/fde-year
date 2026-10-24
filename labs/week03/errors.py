from typing import ClassVar


class UpstreamError(Exception):
    """Base class for all application-specific errors."""

    code: ClassVar[str] = "upstream_error"


class RateLimitedError(UpstreamError):
    """Raised whem an upstream service rate limits."""

    code: ClassVar[str] = "rate_limited"


class UpstreamTimeoutError(UpstreamError):
    """Raised when an upstream service times out."""

    code: ClassVar[str] = "upstream_timeout"


class UpstreamDroppedError(UpstreamError):
    """Raised when a tool fails to execute properly."""

    code: ClassVar[str] = "upstream_dropped"
