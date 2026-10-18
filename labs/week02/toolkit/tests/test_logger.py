import json
import logging

import pytest
from toolkit.log import configure_logging


def test_json_logging_output(capsys: pytest.CaptureFixture[str]) -> None:
    # Configure inside the test so the handler writes to pytest's captured stderr.
    configure_logging("INFO")

    logging.getLogger("toolkit").info("hello", extra={"request_id": "r-1"})

    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1  # catches duplicate handlers

    record: dict[str, object] = json.loads(lines[0])
    assert record["message"] == "hello"
    assert record["request_id"] == "r-1"
    assert record["level"] == "INFO"
    assert record["logger"] == "toolkit"
    assert "time" in record
    assert "tool_name" not in record
    assert "duration_ms" not in record


def test_debug_dropped_when_level_is_info(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logger = logging.getLogger("toolkit")

    logger.debug("hidden message")
    logger.info("visible message")

    lines = capsys.readouterr().err.strip().splitlines()
    assert len(lines) == 1
    record: dict[str, object] = json.loads(lines[0])
    assert record["message"] == "visible message"
