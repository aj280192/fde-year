"""The layer rules, as tests, so they can't quietly break later.

    api/  ->  services.py  ->  repository.py  ->  domain/

Each layer may import only the layers to its right, and domain/ imports no libraries at all
beyond the standard library.
"""

import ast
from pathlib import Path

import pytest

HERE = Path(__file__).parent

# What each layer must never import (checked against the start of every imported module name).
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "domain": (
        "fastapi",
        "starlette",
        "pydantic",
        "sqlalchemy",
        "psycopg",
        "api",
        "services",
        "repository",
    ),
    "repository.py": ("fastapi", "starlette", "pydantic", "api", "services"),
    "services.py": ("fastapi", "starlette", "pydantic", "api"),
}


def imported_modules(path: Path) -> set[str]:
    """Every module a file imports, read from its syntax tree (the file is never run)."""
    tree = ast.parse(path.read_text(), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module is not None
            and node.level == 0
        ):
            found.add(node.module)
    return found


def files_of(layer: str) -> list[Path]:
    target = HERE / layer
    return sorted(target.glob("*.py")) if target.is_dir() else [target]


def breaks_rule(module: str, banned: tuple[str, ...]) -> bool:
    return any(module == name or module.startswith(name + ".") for name in banned)


@pytest.mark.parametrize(
    ("layer", "path"),
    [(layer, path) for layer in FORBIDDEN for path in files_of(layer)],
    ids=lambda value: value.name if isinstance(value, Path) else str(value),
)
def test_layer_imports_only_what_it_may(layer: str, path: Path) -> None:
    bad = sorted(m for m in imported_modules(path) if breaks_rule(m, FORBIDDEN[layer]))
    assert not bad, (
        f"{path.relative_to(HERE)} imports {bad}, which {layer} must not depend on"
    )


def test_every_layer_file_was_checked() -> None:
    # Guards against the test passing because it found no files (a renamed folder, say).
    assert len(files_of("domain")) >= 3
    assert all(p.exists() for layer in FORBIDDEN for p in files_of(layer))


def test_the_checker_catches_a_bad_import(tmp_path: Path) -> None:
    # A test for the test: a file that imports fastapi must be reported.
    bad = tmp_path / "bad.py"
    bad.write_text("import fastapi\nfrom pydantic import BaseModel\n")
    found = imported_modules(bad)
    assert breaks_rule("fastapi", FORBIDDEN["domain"])
    assert {"fastapi", "pydantic"} <= found
