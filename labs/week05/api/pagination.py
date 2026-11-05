"""Opaque page tokens for GET /v1/tasks (AIP-158).

A token is URL-safe base64 of {"t": <created_at ISO>, "id": <task id>}: the last task on the
previous page. Clients must treat it as opaque. It is not signed (see DESIGN.md section 14).
"""

import base64
import binascii
import json
from datetime import datetime

from repository import Cursor

from api.errors import invalid_page_token


def encode_cursor(cursor: Cursor) -> str:
    created_at, task_id = cursor
    payload = json.dumps({"t": created_at.isoformat(), "id": task_id}).encode()
    return base64.urlsafe_b64encode(payload).decode()


def decode_cursor(token: str) -> Cursor:
    """The (created_at, id) a token points at. Any problem with the token gives 400."""
    try:
        data = json.loads(base64.urlsafe_b64decode(token.encode()))
        created_at = datetime.fromisoformat(data["t"])
        task_id = str(data["id"])
    except (ValueError, binascii.Error, KeyError, TypeError) as exc:
        raise invalid_page_token() from exc
    # Our timestamps are always UTC. A token with no timezone wasn't made by us, and comparing
    # it with a UTC datetime would raise TypeError inside the route (a 500), so reject it here.
    if created_at.tzinfo is None:
        raise invalid_page_token()
    return created_at, task_id
