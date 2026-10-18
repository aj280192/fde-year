import json
from pathlib import Path

import pytest
from toolkit.cli import EXIT_ERROR, EXIT_INVALID, EXIT_OK, main

VALID_CALL = {"id": "c1", "name": "get_pod_logs", "arguments": {"pod": "api-7f9"}}


@pytest.fixture(autouse=True)
def toolkit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TOOLKIT_ENV", "dev")


def write_json(path: Path, data: object) -> Path:
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_all_valid_returns_0(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = write_json(tmp_path / "calls.json", [VALID_CALL])

    assert main(["validate", str(calls)]) == EXIT_OK
    assert "1 valid, 0 invalid" in capsys.readouterr().out


def test_invalid_entries_return_1_and_name_the_field(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_name: dict[str, object] = {"id": "c2", "arguments": {}}
    calls = write_json(tmp_path / "calls.json", [VALID_CALL, missing_name])

    assert main(["validate", str(calls)]) == EXIT_INVALID
    out = capsys.readouterr().out
    assert "c2  invalid  name: Field required" in out
    assert "1 valid, 1 invalid" in out


def test_missing_file_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["validate", str(tmp_path / "nope.json")]) == EXIT_ERROR
    assert "does not exist" in capsys.readouterr().err


def test_broken_json_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    calls = tmp_path / "calls.json"
    calls.write_text("[{", encoding="utf-8")

    assert main(["validate", str(calls)]) == EXIT_ERROR
    assert "is not valid JSON" in capsys.readouterr().err


def test_top_level_must_be_a_list(tmp_path: Path) -> None:
    calls = write_json(tmp_path / "calls.json", VALID_CALL)

    assert main(["validate", str(calls)]) == EXIT_ERROR


def test_missing_setting_returns_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("TOOLKIT_ENV")
    calls = write_json(tmp_path / "calls.json", [VALID_CALL])

    assert main(["validate", str(calls)]) == EXIT_ERROR
    assert "set TOOLKIT_ENV" in capsys.readouterr().err
