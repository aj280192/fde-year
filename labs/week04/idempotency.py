"""Idempotent create: a retried POST /v1/tasks with the same Idempotency-Key returns the
first task instead of making a second one (DESIGN.md section 11)."""

import hashlib
import json
from datetime import datetime, timedelta

from models import CreateTaskRequest
from pydantic import BaseModel

TTL = timedelta(hours=24)  # how long a key is remembered


class IdempotencyRecord(BaseModel):
    """What we remember about one (API key, Idempotency-Key) pair."""

    fingerprint: (
        str  # of the request body, to spot the same key reused for a different request
    )
    task_id: str  # the task the first request created
    created_at: datetime  # when, for the 24-hour expiry


def fingerprint(body: CreateTaskRequest) -> str:
    """SHA-256 of the parsed body with sorted keys, so spacing and key order don't matter."""
    canonical = json.dumps(body.model_dump(), sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
