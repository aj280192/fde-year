"""Idempotent create, as a rule: the same key and the same request within 24 hours means
"return the first task", not "make another one" (DESIGN.md section 11)."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta

TTL = timedelta(hours=24)  # how long a key is remembered; the boundary is inclusive


@dataclass(frozen=True)
class IdempotencyRecord:
    """What we remember about one (owner, idempotency key) pair."""

    fingerprint: (
        str  # of the request, to spot the same key reused for a different request
    )
    task_id: str  # the task the first request created
    created_at: datetime  # when, for the expiry


def fingerprint(input: str) -> str:
    """SHA-256 of the request's fields as sorted JSON. A dict, so new fields slot in later."""
    canonical = json.dumps({"input": input}, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()
