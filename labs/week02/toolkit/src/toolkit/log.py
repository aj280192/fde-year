import json
import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:

        log_data = {
            "time": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        extra_fields = ["request_id", "tool_name", "duration_ms"]
        for field in extra_fields:
            val = getattr(record, field, None)
            if val is not None:
                log_data[field] = val

        if record.exc_info:
            log_data["exc"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def configure_logging(level: str) -> None:
    logger = logging.getLogger("toolkit")

    if logger.handlers:
        for handler in list(logger.handlers):
            logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JSONFormatter())

    logger.addHandler(handler)
    logger.setLevel(level.upper())
    logger.propagate = False
