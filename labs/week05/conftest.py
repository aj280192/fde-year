"""Shared test fixtures. `repo` runs every test that uses it twice: in memory and on Postgres."""

import os
from collections.abc import Iterator

import pytest
from db.engine import make_engine
from db.models import Base
from db.repository import PostgresTaskRepository
from repository import InMemoryTaskRepository, TaskRepository
from sqlalchemy import Engine, text

TRUNCATE_ALL = "TRUNCATE tool_calls, runs, idempotency_keys, tasks, tenants RESTART IDENTITY CASCADE"


@pytest.fixture(scope="session")
def pg_engine() -> Iterator[Engine]:
    """One engine for the whole test run, on the TEST database."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url is None:
        pytest.skip(
            "TEST_DATABASE_URL not set"
        )  # the suite still runs without Postgres
    engine = make_engine(url)
    # tasks_test only, never `tasks`: the app's schema is changed by Alembic alone.
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture(params=["memory", "postgres"])
def repo(request: pytest.FixtureRequest) -> TaskRepository:
    if request.param == "memory":
        return InMemoryTaskRepository()
    engine: Engine = request.getfixturevalue("pg_engine")
    with engine.begin() as conn:
        conn.execute(text(TRUNCATE_ALL))  # each test starts with empty tables
    return PostgresTaskRepository(engine)
