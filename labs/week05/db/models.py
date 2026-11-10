"""The Postgres tables, as SQLAlchemy models.

Row classes are named `...Row` so they're never confused with the domain classes they store:
`TaskRow` is a database row, `domain.task.Task` is the business object. Only db/repository.py
converts between them.
"""

from datetime import datetime
from typing import Any

from domain.task import TaskState
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    and_,
    func,
    or_,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Predictable names for every constraint and index, so later migrations can find them.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

# The states a run can be in: one attempt at a task, by one worker.
RUN_STATES = ("running", "succeeded", "failed", "cancelled")


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TenantRow(Base):
    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(Text, primary_key=True)  # the API key's key_id
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class TaskRow(Base):
    __tablename__ = "tasks"

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    input: Mapped[str] = mapped_column(Text, nullable=False)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # No server_default: the service sets both times from its injected clock. A database
    # default would quietly hide a bug where the code forgot to set them.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        # Serves list_for_owner exactly: filter by tenant, then newest first with id as the
        # tie-breaker (Use the Index, Luke: equality column first, then the sort columns).
        Index(None, "tenant_id", "created_at", "id"),
        # Only active tasks (about 10% of rows): counts of a tenant's active work become
        # an index-only scan, at 744 kB against 55 MB for a full index (week 5 README, Results).
        Index(
            "ix_tasks_active",
            "tenant_id",
            "state",
            postgresql_where=text(
                "state IN ('queued', 'running', 'waiting_for_input')"
            ),
        ),
        # Built from TaskState, so the database and the domain can never disagree.
        CheckConstraint(state.in_([s.value for s in TaskState]), name="state_valid"),
        CheckConstraint(func.length(input).between(1, 10_000), name="input_length"),
        CheckConstraint(
            or_(
                and_(error_code.is_(None), error_message.is_(None)),
                and_(error_code.is_not(None), error_message.is_not(None)),
            ),
            name="error_both_or_neither",
        ),
    )


class IdempotencyKeyRow(Base):
    __tablename__ = "idempotency_keys"

    # The primary key (tenant_id, key) is the unique constraint from DESIGN.md section 14:
    # two inserts with the same pair can never both succeed.
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), primary_key=True)
    key: Mapped[str] = mapped_column(Text, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    __table_args__ = (
        CheckConstraint(func.length(key).between(1, 255), name="key_length"),
    )


class RunRow(Base):
    """One attempt at a task. Nothing writes these yet: the worker comes in Phase 2."""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    task_id: Mapped[str] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(Text, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("task_id", "attempt"),  # a task can't have two "attempt 1"s
        CheckConstraint(attempt >= 1, name="attempt_positive"),
        CheckConstraint(state.in_(RUN_STATES), name="state_valid"),
    )


class ToolCallRow(Base):
    """One tool call inside a run, in order. Read by the trajectory metrics in week 20."""

    __tablename__ = "tool_calls"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    tool_name: Mapped[str] = mapped_column(Text, nullable=False)
    arguments: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("run_id", "seq"),  # one position per call within a run
        CheckConstraint(seq >= 1, name="seq_positive"),
    )
