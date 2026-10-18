# toolkit

Validates tool-call payloads from an AI agent before they run, with errors precise enough for the model to fix its next attempt.

## Install

```bash
uv build
uv pip install dist/toolkit-0.1.0-py3-none-any.whl
```

## Configure

| Variable | Required | Values | Default |
| --- | --- | --- | --- |
| `TOOLKIT_ENV` | Yes | `dev`, `prod` | none |
| `TOOLKIT_LOG_LEVEL` | No | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |

## Usage

```bash
TOOLKIT_ENV=dev toolkit validate examples/calls.json
```

```text
c1  ok
c2  invalid  name: Field required
c3  invalid  arguments: Input should be a valid dictionary
c4  invalid  priority: Extra inputs are not permitted
1 valid, 3 invalid
```

The report goes to standard output. One JSON log line per run goes to standard error.

| Exit code | Meaning |
| --- | --- |
| 0 | Every tool call is valid |
| 1 | The file was read, but at least one tool call is invalid |
| 2 | The tool could not run: missing setting, missing file, or invalid JSON |

## Design decisions

**Strict models that reject unknown fields.** A model can send `"100"` where a number belongs, or misspell a field. Lenient parsing would coerce or ignore these and run the wrong call. Strict validation rejects them with the field name and the expected type, which the model can act on.

**A tagged union for tool outcomes.** A result is either a success with `content` or an error with `message`, chosen by a `kind` field. The alternative, one model with optional fields, allows a result that is both or neither.

**Logs on standard error, report on standard output.** `toolkit validate calls.json > report.txt` gives a clean report, while the JSON log lines still reach the log platform.

**Exit code 1 for bad data, 2 for a tool that could not run.** A CI pipeline can treat "your payloads are wrong" differently from "the check itself failed".

## Development

```bash
uv run pytest
uv run pyright
uv run ruff check .
```