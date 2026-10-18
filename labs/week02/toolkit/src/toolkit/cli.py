"""Command line: `toolkit validate FILE` checks a JSON list of tool calls."""

import argparse
import logging
import sys
import time
import uuid
from pathlib import Path

import pydantic
from pydantic import JsonValue, TypeAdapter

from toolkit.errors import AppError, ValidationFailedError
from toolkit.log import configure_logging
from toolkit.models import ToolCall
from toolkit.settings import Settings

EXIT_OK = 0  # every tool call is valid
EXIT_INVALID = 1  # the file was read, but at least one call is invalid
EXIT_ERROR = 2  # the tool could not run: bad settings, missing file, bad JSON

logger = logging.getLogger("toolkit.cli")

# Parses JSON text and checks the top level is a list, in one typed step.
JSON_LIST: TypeAdapter[list[JsonValue]] = TypeAdapter(list[JsonValue])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toolkit", description="Validate tool-call payloads."
    )
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser(
        "validate", help="Validate a JSON file holding a list of tool calls."
    )
    validate.add_argument("path", type=Path, help="Path to the JSON file.")
    return parser


def load_entries(path: Path) -> list[JsonValue]:
    """Read the file and return its top-level JSON list, or raise ValidationFailed."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ValidationFailedError(f"{path} does not exist") from exc
    try:
        return JSON_LIST.validate_json(text)
    except pydantic.ValidationError as exc:
        if exc.errors()[0]["type"] == "json_invalid":
            raise ValidationFailedError(f"{path} is not valid JSON") from exc
        raise ValidationFailedError(
            f"{path} must contain a JSON list of tool calls"
        ) from exc


def entry_label(index: int, entry: JsonValue) -> str:
    """Use the entry's id when it has a usable one, otherwise its position."""
    if isinstance(entry, dict):
        entry_id = entry.get("id")
        if isinstance(entry_id, str):
            return entry_id
    return f"#{index}"


def describe(error: pydantic.ValidationError) -> str:
    """First validation error as 'field.path: message'."""
    first = error.errors()[0]
    location = ".".join(str(part) for part in first["loc"]) or "(entry)"
    return f"{location}: {first['msg']}"


def validate_file(path: Path) -> int:
    entries = load_entries(path)
    valid = 0
    for index, entry in enumerate(entries, start=1):
        label = entry_label(index, entry)
        try:
            ToolCall.model_validate(entry)
        except pydantic.ValidationError as error:
            print(f"{label}  invalid  {describe(error)}")
        else:
            valid += 1
            print(f"{label}  ok")
    invalid = len(entries) - valid
    print(f"{valid} valid, {invalid} invalid")
    return EXIT_OK if invalid == 0 else EXIT_INVALID


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        # model_validate({}) reads the environment like Settings() does, but pyright
        # does not expect the required fields as constructor arguments.
        settings = Settings.model_validate({})
    except pydantic.ValidationError:
        print("toolkit: set TOOLKIT_ENV to 'dev' or 'prod'", file=sys.stderr)
        return EXIT_ERROR

    configure_logging(settings.log_level)
    request_id = uuid.uuid4().hex[:8]
    started = time.perf_counter()

    try:
        exit_code = validate_file(args.path)
    except AppError as error:
        print(f"toolkit: {error}", file=sys.stderr)
        logger.error(f"run failed: {error.code}", extra={"request_id": request_id})
        return EXIT_ERROR

    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    logger.info(
        f"validated {args.path.name}, exit code {exit_code}",
        extra={"request_id": request_id, "duration_ms": duration_ms},
    )
    return exit_code
