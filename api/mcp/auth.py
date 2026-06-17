"""Per-agent API key generation, argon2 hashing, verification.

Format of a generated key: ``mcp_key_<client_name>_<date>_<random32>``.
- ``KEY_PREFIX`` keeps the audit-log redactor able to recognise that a
  string IS a Hermes MCP key (so it can be replaced with ``<mcp-key>``
  rather than the secret regex matcher's generic ``<redacted>``).
- The client name is embedded for human-readability of audit rows that
  reference the key BEFORE it has been resolved to a client_id.
- The random tail is the actual secret. 32 base64url chars ⇒ ~192 bits.
"""
from __future__ import annotations

import base64
import re
import secrets
from datetime import date

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash

KEY_PREFIX = "mcp_key_"

_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=64 * 1024,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def _sanitize_client_name(name: str) -> str:
    """Strip everything that's not a-z0-9- to keep keys greppable + filename-safe."""
    return re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-") or "client"


def generate_key(client_name: str) -> str:
    safe = _sanitize_client_name(client_name)
    today = date.today().isoformat()
    random_bytes = secrets.token_bytes(24)
    tail = base64.urlsafe_b64encode(random_bytes).decode("ascii").rstrip("=")
    return f"{KEY_PREFIX}{safe}_{today}_{tail}"


def hash_key(key: str) -> str:
    return _hasher.hash(key)


def verify_key(key: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, key)
    except (VerifyMismatchError, InvalidHash, ValueError):
        return False
