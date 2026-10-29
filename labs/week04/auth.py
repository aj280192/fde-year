import hashlib
import secrets

from pydantic import BaseModel, ConfigDict

READ = "tasks:read"
WRITE = "tasks:write"


class Principal(BaseModel):
    model_config = ConfigDict(frozen=True)
    key_id: str
    scopes: frozenset[str]


def hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def new_key() -> str:
    return "sk_" + secrets.token_urlsafe(32)


if __name__ == "__main__":
    new_key_generated = new_key()
    new_key_hashed = hash_key(new_key_generated)

    print("key  (keep secret, paste into /docs): ", new_key_generated)
    print("hash (goes in serve.py): ", new_key_hashed)
