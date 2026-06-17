# Hermes MCP Service — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a read-only MCP service inside `hermes-api` that exposes Hermes's queue, chat threads, skills library, tenant-bridge state, and provider health to Claude Code via stdio, with per-agent API-key auth and a full audit trail.

**Architecture:** The MCP server is a new Python module `api/mcp/` inside the existing hermes-api codebase. Claude Code reaches it by spawning `ssh admin@ssh.odooiq.com docker exec -i hermes-api python -m api.mcp stdio --key <token>`. The MCP server shares the existing SQLite store (`LocalStore`) and ProviderRegistry directly — no HTTP bridge needed in Phase 1. Per-agent API keys are stored hashed (argon2) in a new `mcp_clients` table; every tool call is audited in `mcp_calls`. The 42-skill library is read directly from disk at `/app/custom-hermes-skills/` (mounted in).

**Tech Stack:** Python 3.12, FastAPI 0.115 (existing), Pydantic 2.9 (existing), SQLite WAL (existing), `mcp` SDK 1.x (new), `argon2-cffi` 23.x (new), pytest with `unittest.mock.AsyncMock` (existing convention).

---

## File structure

| Path | Responsibility |
|---|---|
| `api/mcp/__init__.py` | Package marker + exported types |
| `api/mcp/__main__.py` | CLI entry: `python -m api.mcp stdio|keygen|keys` |
| `api/mcp/server.py` | MCP stdio server: initialize, capabilities, dispatch |
| `api/mcp/auth.py` | API key generation, argon2 hashing, lookup |
| `api/mcp/audit.py` | Audit context manager (one row per call) |
| `api/mcp/redaction.py` | Secret-pattern scrubber for tool results |
| `api/mcp/tools/__init__.py` | Tool registry + dispatch |
| `api/mcp/tools/recommendations.py` | `hermes_list_recommendations`, `hermes_get_recommendation` |
| `api/mcp/tools/chat.py` | `hermes_list_chat_threads`, `hermes_get_chat_messages` |
| `api/mcp/tools/bridges.py` | `hermes_get_tenant_status` |
| `api/mcp/tools/providers.py` | `hermes_get_provider_health` |
| `api/mcp/tools/skills.py` | `hermes_list_skills`, `hermes_run_skill` |
| `api/mcp/skill_runner.py` | Load + validate + run a skill from custom-hermes-skills/ |
| `api/mcp/resources.py` | Resource URI parsing + read handlers |
| `api/mcp/prompts.py` | Prompt templates: review-queue, use-skill/{name} |
| `api/local_store.py` | EXTEND: add `mcp_clients` + `mcp_calls` schema + methods |
| `api/requirements.txt` | EXTEND: `mcp`, `argon2-cffi` |
| `api/Dockerfile` | EXTEND: mount custom-hermes-skills at /app/custom-hermes-skills |
| `docker-compose.yml` | EXTEND: bind-mount custom-hermes-skills into hermes-api |
| `api/tests/test_mcp_*.py` | One test module per source module |
| `api/tests/fixtures/skill-fixture/` | A minimal valid skill folder for tests |
| `~/bin/hermes-mcp` (operator's Mac) | Single shell wrapper that runs ssh+docker-exec |
| `custom-hermes-skills/skills/hermes-mcp-service/` | Companion SKILL.md + metadata.json + SOURCE_INSPIRATION.md |

---

## Task 1 — Add MCP SDK + argon2 to requirements

**Files:**
- Modify: `api/requirements.txt`

- [ ] **Step 1: Add the two new packages**

Append to `api/requirements.txt`:

```
mcp==1.9.0
argon2-cffi==23.1.0
```

- [ ] **Step 2: Rebuild the wheel layer locally to confirm both resolve**

Run:

```bash
cd ~/hermes-console
python3 -m venv .venv-mcp-check
.venv-mcp-check/bin/pip install -q -r api/requirements.txt
.venv-mcp-check/bin/python -c "import mcp, argon2; print(mcp.__version__, argon2.__version__)"
rm -rf .venv-mcp-check
```

Expected output: `1.9.0 23.1.0` (or close patch versions).

- [ ] **Step 3: Commit**

```bash
git add api/requirements.txt
git commit -m "feat(mcp): add mcp SDK + argon2-cffi to hermes-api requirements"
```

---

## Task 2 — Create the api/mcp/ package skeleton

**Files:**
- Create: `api/mcp/__init__.py`
- Create: `api/mcp/__main__.py`
- Create: `api/tests/test_mcp_package.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_package.py`:

```python
"""Package layout sanity checks for the new MCP module."""
from __future__ import annotations

import importlib
import subprocess
import sys


def test_package_imports() -> None:
    mod = importlib.import_module("api.mcp")
    assert mod.__name__ == "api.mcp"


def test_module_runnable_prints_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "api.mcp", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "stdio" in result.stdout
    assert "keygen" in result.stdout
    assert "keys" in result.stdout
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_package.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.mcp'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/__init__.py`:

```python
"""Hermes MCP service.

Phase 1 surface: read-only tools + resources + prompts over stdio.
See ``docs/superpowers/specs/2026-06-17-hermes-mcp-service-design.md``.
"""

__all__: list[str] = []
```

Create `api/mcp/__main__.py`:

```python
"""CLI entry: ``python -m api.mcp <subcommand>``.

Subcommands:
  stdio   Run the MCP stdio server (Claude Code spawns this).
  keygen  Create a new per-agent API key.
  keys    List or revoke existing keys.
"""
from __future__ import annotations

import argparse
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api.mcp", description="Hermes MCP service")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stdio", help="Run the MCP stdio server")
    kg = sub.add_parser("keygen", help="Create a new per-agent API key")
    kg.add_argument("--client", required=True, help="Logical name for the client")
    keys = sub.add_parser("keys", help="List or revoke existing keys")
    keys.add_argument("action", choices=["list", "revoke"])
    keys.add_argument("--id", type=int, help="Required for revoke")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "stdio":
        print("stdio: not implemented yet (Task 9)", file=sys.stderr)
        return 1
    if args.cmd == "keygen":
        print(f"keygen: not implemented yet (Task 8) client={args.client}", file=sys.stderr)
        return 1
    if args.cmd == "keys":
        print(f"keys {args.action}: not implemented yet (Task 8)", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_package.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/__init__.py api/mcp/__main__.py api/tests/test_mcp_package.py
git commit -m "feat(mcp): scaffold api.mcp package with CLI subcommand skeleton"
```

---

## Task 3 — Add `mcp_clients` table to LocalStore + tests

**Files:**
- Modify: `api/local_store.py:218-231` (the `startup()` method's `_init()` inner function)
- Modify: `api/local_store.py` (append new methods after the existing recommendation methods)
- Create: `api/tests/test_mcp_clients_store.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_clients_store.py`:

```python
"""SQLite store tests for the new mcp_clients table."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_create_then_get_mcp_client(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="claude-code", key_hash="hash-xyz"))
    assert cid >= 1
    row = asyncio.run(store.get_mcp_client(cid))
    assert row is not None
    assert row["name"] == "claude-code"
    assert row["key_hash"] == "hash-xyz"
    assert row["revoked_at"] is None


def test_list_active_mcp_clients_excludes_revoked(store: LocalStore) -> None:
    a = asyncio.run(store.create_mcp_client(name="a", key_hash="ha"))
    b = asyncio.run(store.create_mcp_client(name="b", key_hash="hb"))
    asyncio.run(store.revoke_mcp_client(a))
    rows = asyncio.run(store.list_mcp_clients(active_only=True))
    assert len(rows) == 1
    assert rows[0]["id"] == b


def test_find_mcp_client_by_key_hash(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="codex", key_hash="hashed-secret"))
    found = asyncio.run(store.find_mcp_client_by_key_hash("hashed-secret"))
    assert found is not None
    assert found["id"] == cid
    none = asyncio.run(store.find_mcp_client_by_key_hash("nope"))
    assert none is None
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_clients_store.py -v
```

Expected: FAIL with `AttributeError: 'LocalStore' object has no attribute 'create_mcp_client'`.

- [ ] **Step 3: Write the minimal implementation**

Locate `api/local_store.py:218` (the `startup()` method's `_init()` inner function). Add this CREATE TABLE inside `_init`:

```python
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mcp_clients (
                  id          INTEGER PRIMARY KEY AUTOINCREMENT,
                  name        TEXT NOT NULL,
                  key_hash    TEXT NOT NULL UNIQUE,
                  created_at  TEXT NOT NULL,
                  revoked_at  TEXT
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_mcp_clients_key_hash "
                "ON mcp_clients(key_hash) WHERE revoked_at IS NULL"
            )
```

Append four methods to `LocalStore` (after the existing recommendation methods, before any chat methods):

```python
    async def create_mcp_client(self, *, name: str, key_hash: str) -> int:
        now = _utcnow_iso()

        def _insert() -> int:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO mcp_clients (name, key_hash, created_at) "
                    "VALUES (?, ?, ?)",
                    (name, key_hash, now),
                )
                return int(cur.lastrowid)

        async with self._write_lock:
            return await asyncio.to_thread(_insert)

    async def get_mcp_client(self, client_id: int) -> Optional[Dict[str, Any]]:
        def _select() -> Optional[Dict[str, Any]]:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id, name, key_hash, created_at, revoked_at "
                    "FROM mcp_clients WHERE id = ?",
                    (client_id,),
                ).fetchone()
                return dict(row) if row else None

        return await asyncio.to_thread(_select)

    async def list_mcp_clients(
        self, *, active_only: bool = False
    ) -> List[Dict[str, Any]]:
        def _select() -> List[Dict[str, Any]]:
            with self._connect() as conn:
                if active_only:
                    rows = conn.execute(
                        "SELECT id, name, key_hash, created_at, revoked_at "
                        "FROM mcp_clients WHERE revoked_at IS NULL "
                        "ORDER BY id"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT id, name, key_hash, created_at, revoked_at "
                        "FROM mcp_clients ORDER BY id"
                    ).fetchall()
                return [dict(r) for r in rows]

        return await asyncio.to_thread(_select)

    async def find_mcp_client_by_key_hash(
        self, key_hash: str
    ) -> Optional[Dict[str, Any]]:
        def _select() -> Optional[Dict[str, Any]]:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT id, name, key_hash, created_at, revoked_at "
                    "FROM mcp_clients "
                    "WHERE key_hash = ? AND revoked_at IS NULL",
                    (key_hash,),
                ).fetchone()
                return dict(row) if row else None

        return await asyncio.to_thread(_select)

    async def revoke_mcp_client(self, client_id: int) -> bool:
        now = _utcnow_iso()

        def _update() -> bool:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE mcp_clients SET revoked_at = ? "
                    "WHERE id = ? AND revoked_at IS NULL",
                    (now, client_id),
                )
                return cur.rowcount > 0

        async with self._write_lock:
            return await asyncio.to_thread(_update)
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_clients_store.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/local_store.py api/tests/test_mcp_clients_store.py
git commit -m "feat(mcp): add mcp_clients SQLite table + 5 LocalStore methods"
```

---

## Task 4 — Add `mcp_calls` audit table + tests

**Files:**
- Modify: `api/local_store.py` (same `_init` + append methods)
- Create: `api/tests/test_mcp_calls_store.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_calls_store.py`:

```python
"""SQLite tests for the mcp_calls audit table."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_log_then_list_call(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="claude-code", key_hash="h1"))
    call_id = asyncio.run(
        store.log_mcp_call(
            client_id=cid,
            tool_name="hermes_list_recommendations",
            args_redacted={"state": "ready"},
            outcome="ok",
            error_text=None,
            duration_ms=12,
        )
    )
    assert call_id >= 1
    rows = asyncio.run(store.list_mcp_calls(since_hours=24))
    assert len(rows) == 1
    assert rows[0]["client_id"] == cid
    assert rows[0]["tool_name"] == "hermes_list_recommendations"
    assert rows[0]["outcome"] == "ok"
    assert rows[0]["duration_ms"] == 12


def test_log_failure_records_error(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="codex", key_hash="h2"))
    asyncio.run(
        store.log_mcp_call(
            client_id=cid,
            tool_name="hermes_run_skill",
            args_redacted={"skill": "nope"},
            outcome="error",
            error_text="skill nope not found",
            duration_ms=2,
        )
    )
    rows = asyncio.run(store.list_mcp_calls(since_hours=24))
    assert rows[0]["outcome"] == "error"
    assert rows[0]["error_text"] == "skill nope not found"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_calls_store.py -v
```

Expected: FAIL with `AttributeError: 'LocalStore' object has no attribute 'log_mcp_call'`.

- [ ] **Step 3: Write the minimal implementation**

In `api/local_store.py` `_init()`, append:

```python
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mcp_calls (
                  id                INTEGER PRIMARY KEY AUTOINCREMENT,
                  client_id         INTEGER NOT NULL REFERENCES mcp_clients(id),
                  tool_name         TEXT NOT NULL,
                  args_redacted_json TEXT,
                  outcome           TEXT NOT NULL,
                  error_text        TEXT,
                  started_at        TEXT NOT NULL,
                  duration_ms       INTEGER NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS ix_mcp_calls_started_at "
                "ON mcp_calls(started_at DESC)"
            )
```

Append two methods to `LocalStore`:

```python
    async def log_mcp_call(
        self,
        *,
        client_id: int,
        tool_name: str,
        args_redacted: Dict[str, Any],
        outcome: str,
        error_text: Optional[str],
        duration_ms: int,
    ) -> int:
        now = _utcnow_iso()
        args_json = json.dumps(args_redacted, default=str, sort_keys=True)

        def _insert() -> int:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO mcp_calls "
                    "(client_id, tool_name, args_redacted_json, outcome, "
                    " error_text, started_at, duration_ms) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        client_id,
                        tool_name,
                        args_json,
                        outcome,
                        error_text,
                        now,
                        duration_ms,
                    ),
                )
                return int(cur.lastrowid)

        async with self._write_lock:
            return await asyncio.to_thread(_insert)

    async def list_mcp_calls(
        self, *, since_hours: int = 24
    ) -> List[Dict[str, Any]]:
        cutoff = (
            datetime.now(tz=timezone.utc) - timedelta(hours=since_hours)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")

        def _select() -> List[Dict[str, Any]]:
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT id, client_id, tool_name, args_redacted_json, "
                    "outcome, error_text, started_at, duration_ms "
                    "FROM mcp_calls WHERE started_at >= ? "
                    "ORDER BY started_at DESC",
                    (cutoff,),
                ).fetchall()
                return [dict(r) for r in rows]

        return await asyncio.to_thread(_select)
```

If `datetime` / `timedelta` / `json` aren't already imported at the top of `local_store.py`, add the necessary imports.

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_calls_store.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/local_store.py api/tests/test_mcp_calls_store.py
git commit -m "feat(mcp): add mcp_calls audit table + 2 LocalStore methods"
```

---

## Task 5 — API key generator + argon2 hasher + tests

**Files:**
- Create: `api/mcp/auth.py`
- Create: `api/tests/test_mcp_auth.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_auth.py`:

```python
"""Tests for the API key generator and argon2 hasher."""
from __future__ import annotations

from api.mcp.auth import (
    generate_key,
    hash_key,
    verify_key,
    KEY_PREFIX,
)


def test_generate_key_shape() -> None:
    k = generate_key("claude-code-main")
    assert k.startswith(KEY_PREFIX)
    assert "claude-code-main" in k
    # prefix + name + 32-char random suffix ⇒ at least 50 chars
    assert len(k) >= 50


def test_generate_key_uniqueness() -> None:
    a = generate_key("x")
    b = generate_key("x")
    assert a != b


def test_hash_then_verify_round_trip() -> None:
    k = generate_key("codex")
    h = hash_key(k)
    assert h != k
    assert verify_key(k, h) is True
    assert verify_key(k + "tamper", h) is False
    assert verify_key("totally-different", h) is False


def test_hash_is_argon2_format() -> None:
    h = hash_key(generate_key("x"))
    assert h.startswith("$argon2id$")
```

- [ ] **Step 2: Run the test to verify it fails**

Run:

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_auth.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.mcp.auth'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/auth.py`:

```python
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
```

- [ ] **Step 4: Run the test to verify it passes**

Run:

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_auth.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/auth.py api/tests/test_mcp_auth.py
git commit -m "feat(mcp): API key generator + argon2id hasher + verifier"
```

---

## Task 6 — Secret redactor for tool args + results

**Files:**
- Create: `api/mcp/redaction.py`
- Create: `api/tests/test_mcp_redaction.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_redaction.py`:

```python
"""Tests for the secret-pattern redactor used on MCP audit + tool results."""
from __future__ import annotations

from api.mcp.redaction import redact


def test_redact_openai_key() -> None:
    out = redact({"key": "sk-proj-9Tpva-KPRV9jsLM0R48a7sbbBPGVq1LL"})
    assert "sk-proj-" not in str(out)
    assert "<redacted:openai>" in str(out)


def test_redact_anthropic_key() -> None:
    out = redact({"k": "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA"})
    assert "<redacted:anthropic>" in str(out)


def test_redact_nested_dict_and_list() -> None:
    inp = {
        "outer": [
            {"inner": "AIzaSyDmABCDEFGHIJKLMNOPQRSTUVWXY-12"},
            "AKIAIOSFODNN7EXAMPLE",
        ]
    }
    out = redact(inp)
    assert "AIza" not in str(out)
    assert "AKIA" not in str(out)


def test_redact_passes_clean_strings_unchanged() -> None:
    inp = {"hello": "world", "n": 42, "nested": {"keep": "this"}}
    out = redact(inp)
    assert out == inp


def test_redact_mcp_key_pattern() -> None:
    out = redact({"k": "mcp_key_claude-code_2026-06-17_abcDEFghi123456"})
    assert "mcp_key_" not in str(out)
    assert "<redacted:mcp-key>" in str(out)
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_redaction.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.mcp.redaction'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/redaction.py`:

```python
"""Secret-pattern redactor for MCP audit args and tool results.

Mirrors the regex bank in ``custom-hermes-skills/scripts/validate_skills.py``
but operates on already-parsed JSON-ish structures (dict / list / str / int / None).
"""
from __future__ import annotations

import re
from typing import Any, List, Tuple

_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"sk-(proj-)?[A-Za-z0-9_-]{20,}"), "openai"),
    (re.compile(r"sk-ant-api03-[A-Za-z0-9_-]{20,}"), "anthropic"),
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "groq"),
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), "google-legacy"),
    (re.compile(r"AQ\.Ab8[A-Za-z0-9_-]{20,}"), "google-new"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws-akid"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "github-pat"),
    (re.compile(r"xoxb-[0-9A-Za-z-]{20,}"), "slack-bot"),
    (re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"), "private-key"),
    (re.compile(r"mcp_key_[a-z0-9-]+_\d{4}-\d{2}-\d{2}_[A-Za-z0-9_-]{20,}"), "mcp-key"),
]


def _redact_str(s: str) -> str:
    out = s
    for pat, label in _PATTERNS:
        out = pat.sub(f"<redacted:{label}>", out)
    return out


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_str(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact(v) for v in value)
    return value
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_redaction.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/redaction.py api/tests/test_mcp_redaction.py
git commit -m "feat(mcp): secret-pattern redactor for audit args + tool results"
```

---

## Task 7 — Audit context manager

**Files:**
- Create: `api/mcp/audit.py`
- Create: `api/tests/test_mcp_audit.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_audit.py`:

```python
"""Tests for the per-call audit context manager."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore
from api.mcp.audit import audit_call


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_audit_call_logs_success(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))

    async def go() -> None:
        async with audit_call(
            store, client_id=cid, tool_name="hermes_get_provider_health",
            args={"foo": "bar"},
        ) as ctx:
            ctx.set_outcome("ok")

    asyncio.run(go())
    rows = asyncio.run(store.list_mcp_calls(since_hours=1))
    assert len(rows) == 1
    assert rows[0]["outcome"] == "ok"
    assert rows[0]["tool_name"] == "hermes_get_provider_health"


def test_audit_call_redacts_args(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))

    async def go() -> None:
        async with audit_call(
            store, client_id=cid, tool_name="hermes_chat",
            args={"k": "sk-proj-9Tpva-KPRV9jsLM0R48a7sbbBPGVq1LL"},
        ) as ctx:
            ctx.set_outcome("ok")

    asyncio.run(go())
    rows = asyncio.run(store.list_mcp_calls(since_hours=1))
    assert "sk-proj-" not in rows[0]["args_redacted_json"]


def test_audit_call_logs_exception_as_error(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))

    async def go() -> None:
        try:
            async with audit_call(
                store, client_id=cid, tool_name="hermes_run_skill",
                args={"skill": "nope"},
            ) as ctx:
                raise ValueError("skill nope not found")
        except ValueError:
            pass

    asyncio.run(go())
    rows = asyncio.run(store.list_mcp_calls(since_hours=1))
    assert rows[0]["outcome"] == "error"
    assert "skill nope not found" in (rows[0]["error_text"] or "")
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_audit.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.mcp.audit'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/audit.py`:

```python
"""Per-call audit: one row per MCP tool invocation.

Async context manager. Default outcome is 'error' unless ``ctx.set_outcome('ok')``
is called explicitly before exit. If an exception escapes the with-block, the
outcome stays 'error' and ``error_text`` carries the exception repr (redacted).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from api.local_store import LocalStore
from api.mcp.redaction import redact


class AuditContext:
    def __init__(self) -> None:
        self.outcome: str = "error"
        self.error_text: Optional[str] = None

    def set_outcome(self, outcome: str) -> None:
        self.outcome = outcome


@asynccontextmanager
async def audit_call(
    store: LocalStore,
    *,
    client_id: int,
    tool_name: str,
    args: Dict[str, Any],
) -> AsyncIterator[AuditContext]:
    ctx = AuditContext()
    started = time.perf_counter()
    args_redacted = redact(args)
    try:
        yield ctx
    except Exception as exc:  # noqa: BLE001 — we want to log anything
        ctx.error_text = _short_repr_redacted(exc)
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await store.log_mcp_call(
            client_id=client_id,
            tool_name=tool_name,
            args_redacted=args_redacted,
            outcome=ctx.outcome,
            error_text=ctx.error_text,
            duration_ms=duration_ms,
        )


def _short_repr_redacted(exc: Exception) -> str:
    s = f"{exc.__class__.__name__}: {exc}"
    # redact strings inside an exception repr the same way as tool args.
    redacted_obj = redact({"_": s})
    return redacted_obj["_"][:500]
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_audit.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/audit.py api/tests/test_mcp_audit.py
git commit -m "feat(mcp): audit context manager — one row per tool call"
```

---

## Task 8 — Wire `keygen`, `keys list`, `keys revoke` CLI subcommands

**Files:**
- Modify: `api/mcp/__main__.py` (replace the "not implemented yet" stubs)
- Modify: `api/tests/test_mcp_package.py` (add CLI behavior tests)

- [ ] **Step 1: Write the failing tests**

Append to `api/tests/test_mcp_package.py`:

```python
import json
import os
import subprocess
import sys
import tempfile

import pytest


def _run_cli(*args: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)
    return subprocess.run(
        [sys.executable, "-m", "api.mcp", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
        env=env,
    )


@pytest.fixture()
def tmp_db_path() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


def test_keygen_prints_key_once_and_persists_hash(tmp_db_path: str) -> None:
    res = _run_cli(
        "keygen", "--client", "claude-code-main",
        env_extra={"HERMES_SQLITE_PATH": tmp_db_path},
    )
    assert res.returncode == 0, res.stderr
    key_line = [ln for ln in res.stdout.splitlines() if ln.startswith("mcp_key_")]
    assert len(key_line) == 1
    assert "claude-code-main" in key_line[0]

    listing = _run_cli("keys", "list", env_extra={"HERMES_SQLITE_PATH": tmp_db_path})
    assert listing.returncode == 0
    parsed = json.loads(listing.stdout)
    assert len(parsed) == 1
    assert parsed[0]["name"] == "claude-code-main"
    # the raw key must NOT be in the listing — only id, name, created_at, revoked_at
    assert "key" not in parsed[0]


def test_keys_revoke_marks_revoked(tmp_db_path: str) -> None:
    _run_cli("keygen", "--client", "x", env_extra={"HERMES_SQLITE_PATH": tmp_db_path})
    listing = _run_cli("keys", "list", env_extra={"HERMES_SQLITE_PATH": tmp_db_path})
    rec_id = json.loads(listing.stdout)[0]["id"]

    res = _run_cli("keys", "revoke", "--id", str(rec_id),
                   env_extra={"HERMES_SQLITE_PATH": tmp_db_path})
    assert res.returncode == 0, res.stderr

    again = _run_cli("keys", "list", env_extra={"HERMES_SQLITE_PATH": tmp_db_path})
    parsed = json.loads(again.stdout)
    assert parsed[0]["revoked_at"] is not None
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_package.py -v
```

Expected: 4 tests collected; the 2 new ones FAIL with `returncode != 0` and `'not implemented yet'` in stderr.

- [ ] **Step 3: Write the minimal implementation**

Replace `api/mcp/__main__.py` with:

```python
"""CLI entry: ``python -m api.mcp <subcommand>``.

stdio   Run the MCP stdio server (Task 9 wires it up).
keygen  Create a new per-agent API key. Prints the key ONCE to stdout.
keys    list  → JSON list of clients (no raw keys).
        revoke --id N → mark client N revoked.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from api.local_store import LocalStore
from api.mcp.auth import generate_key, hash_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api.mcp", description="Hermes MCP service")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stdio", help="Run the MCP stdio server")
    kg = sub.add_parser("keygen", help="Create a new per-agent API key")
    kg.add_argument("--client", required=True, help="Logical name for the client")
    keys = sub.add_parser("keys", help="List or revoke existing keys")
    keys.add_argument("action", choices=["list", "revoke"])
    keys.add_argument("--id", type=int, help="Required for revoke")
    return parser


def _db_path() -> str:
    return os.environ.get("HERMES_SQLITE_PATH", "/data/hermes.sqlite")


async def _keygen(client_name: str) -> int:
    key = generate_key(client_name)
    store = LocalStore(_db_path())
    await store.startup()
    try:
        await store.create_mcp_client(name=client_name, key_hash=hash_key(key))
    finally:
        await store.shutdown()
    # The raw key is shown EXACTLY once and goes to stdout. The operator copies
    # it to ~/.config/hermes/mcp-key-<client>; nothing else stores it.
    print(key)
    print(
        f"\nKey for client '{client_name}' issued. Copy the line above to "
        "~/.config/hermes/mcp-key-<client> on the operator Mac (chmod 600). "
        "This is the only time the key is displayed.",
        file=sys.stderr,
    )
    return 0


async def _keys_list() -> int:
    store = LocalStore(_db_path())
    await store.startup()
    try:
        rows = await store.list_mcp_clients(active_only=False)
    finally:
        await store.shutdown()
    safe = [
        {"id": r["id"], "name": r["name"],
         "created_at": r["created_at"], "revoked_at": r["revoked_at"]}
        for r in rows
    ]
    print(json.dumps(safe, indent=2))
    return 0


async def _keys_revoke(client_id: int) -> int:
    store = LocalStore(_db_path())
    await store.startup()
    try:
        ok = await store.revoke_mcp_client(client_id)
    finally:
        await store.shutdown()
    if not ok:
        print(f"client id={client_id} not found or already revoked", file=sys.stderr)
        return 1
    print(f"revoked client id={client_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "stdio":
        print("stdio: not implemented yet (Task 9)", file=sys.stderr)
        return 1
    if args.cmd == "keygen":
        return asyncio.run(_keygen(args.client))
    if args.cmd == "keys":
        if args.action == "list":
            return asyncio.run(_keys_list())
        if args.action == "revoke":
            if args.id is None:
                print("--id required for revoke", file=sys.stderr)
                return 2
            return asyncio.run(_keys_revoke(args.id))
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_package.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/__main__.py api/tests/test_mcp_package.py
git commit -m "feat(mcp): keygen + keys list/revoke CLI subcommands"
```

---

## Task 9 — MCP stdio server skeleton (initialize + tools/list with empty tools)

**Files:**
- Create: `api/mcp/server.py`
- Modify: `api/mcp/__main__.py` (replace the stdio stub)
- Create: `api/tests/test_mcp_server_handshake.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_server_handshake.py`:

```python
"""Drive the stdio server through an initialize + tools/list exchange."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile

import pytest

from api.local_store import LocalStore
from api.mcp.auth import generate_key, hash_key


@pytest.fixture()
def tmp_db() -> str:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    yield tmp.name
    os.unlink(tmp.name)


@pytest.fixture()
def valid_key(tmp_db: str) -> str:
    key = generate_key("test-client")

    async def setup() -> None:
        s = LocalStore(tmp_db)
        await s.startup()
        await s.create_mcp_client(name="test-client", key_hash=hash_key(key))
        await s.shutdown()

    asyncio.run(setup())
    return key


def _jsonrpc(method: str, params: dict | None = None, _id: int = 1) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": _id, "method": method,
                       "params": params or {}})


def test_initialize_returns_server_info(tmp_db: str, valid_key: str) -> None:
    env = os.environ.copy()
    env["HERMES_SQLITE_PATH"] = tmp_db
    proc = subprocess.Popen(
        [sys.executable, "-m", "api.mcp", "stdio", "--key", valid_key],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=True,
    )
    proc.stdin.write(_jsonrpc("initialize", {
        "protocolVersion": "2025-06-18",
        "clientInfo": {"name": "test", "version": "0.0"},
        "capabilities": {},
    }) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    proc.stdin.close()
    proc.wait(timeout=10)
    parsed = json.loads(line)
    assert parsed["id"] == 1
    assert parsed["result"]["serverInfo"]["name"] == "hermes-mcp"
    assert "tools" in parsed["result"]["capabilities"]


def test_stdio_rejects_invalid_key(tmp_db: str) -> None:
    env = os.environ.copy()
    env["HERMES_SQLITE_PATH"] = tmp_db
    res = subprocess.run(
        [sys.executable, "-m", "api.mcp", "stdio", "--key", "bogus"],
        capture_output=True, text=True, timeout=10, env=env,
    )
    assert res.returncode != 0
    assert "invalid" in res.stderr.lower() or "unauthorized" in res.stderr.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_server_handshake.py -v
```

Expected: FAIL — stdio still prints "not implemented yet" and exits 1.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/server.py`:

```python
"""MCP stdio server.

Phase 1 capabilities: tools, resources, prompts (read-only).
Protocol version: 2025-06-18.
Auth: --key <key> on the command line. Verified against mcp_clients on
startup; if no match (or revoked), server exits non-zero before reading stdin.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Awaitable, Callable, Dict, Optional

from api.local_store import LocalStore
from api.mcp.auth import verify_key

logger = logging.getLogger("api.mcp.server")

SERVER_NAME = "hermes-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-06-18"


class MCPServer:
    def __init__(self, store: LocalStore, client_id: int, client_name: str) -> None:
        self._store = store
        self._client_id = client_id
        self._client_name = client_name
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
        }

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
        }

    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Tools are registered in Tasks 11-18; for now return empty.
        return {"tools": []}

    async def dispatch(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = message.get("method")
        msg_id = message.get("id")
        handler = self._handlers.get(method or "")
        if handler is None:
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"unknown method: {method}"},
            }
        try:
            result = await handler(message.get("params") or {})
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as exc:  # noqa: BLE001
            logger.exception("mcp dispatch error")
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32603, "message": str(exc)[:300]},
            }


async def run_stdio(db_path: str, key: str) -> int:
    store = LocalStore(db_path)
    await store.startup()
    try:
        rows = await store.list_mcp_clients(active_only=True)
        matched = None
        for r in rows:
            if verify_key(key, r["key_hash"]):
                matched = r
                break
        if matched is None:
            print("unauthorized: invalid or revoked key", file=sys.stderr)
            return 1

        server = MCPServer(store, client_id=matched["id"], client_name=matched["name"])
        logger.info("mcp stdio ready client=%s", matched["name"])

        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        writer_transport, writer_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, loop)

        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            resp = await server.dispatch(msg)
            if resp is not None:
                writer.write((json.dumps(resp) + "\n").encode("utf-8"))
                await writer.drain()
        return 0
    finally:
        await store.shutdown()
```

Modify `api/mcp/__main__.py` — replace the build_parser block to add `--key` and the stdio dispatch:

In `build_parser()`, change the `sub.add_parser("stdio", …)` line to:

```python
    st = sub.add_parser("stdio", help="Run the MCP stdio server")
    st.add_argument("--key", required=True, help="Per-agent API key")
```

In `main()`, replace the `if args.cmd == "stdio":` block:

```python
    if args.cmd == "stdio":
        from api.mcp.server import run_stdio
        return asyncio.run(run_stdio(_db_path(), args.key))
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_server_handshake.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/server.py api/mcp/__main__.py api/tests/test_mcp_server_handshake.py
git commit -m "feat(mcp): stdio server skeleton with auth + initialize + tools/list"
```

---

## Task 10 — Tools registry + dispatcher (tools/call routing, no tools yet)

**Files:**
- Create: `api/mcp/tools/__init__.py`
- Modify: `api/mcp/server.py` (register tools/call handler)
- Create: `api/tests/test_mcp_tools_dispatch.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_tools_dispatch.py`:

```python
"""Tools/call dispatches to the right handler + audits + returns content."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import register_tool, ToolSpec


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_tools_call_unknown_returns_error(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "no_such_tool", "arguments": {}},
    }))
    assert resp is not None
    assert "error" in resp
    assert "no_such_tool" in resp["error"]["message"]


def test_tools_list_returns_registered_tools(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))

    async def echo(ctx, args):
        return {"echoed": args}

    register_tool(ToolSpec(
        name="test_echo",
        description="Echoes back the args.",
        input_schema={"type": "object"},
        handler=echo,
    ))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
    }))
    names = [t["name"] for t in resp["result"]["tools"]]
    assert "test_echo" in names


def test_tools_call_audits_and_returns_content(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))

    async def echo(ctx, args):
        return {"echoed": args}

    register_tool(ToolSpec(
        name="test_echo",
        description="Echoes back the args.",
        input_schema={"type": "object"},
        handler=echo,
    ))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "test_echo", "arguments": {"hi": 1}},
    }))
    content = resp["result"]["content"]
    assert content[0]["type"] == "text"
    assert "echoed" in content[0]["text"]

    rows = asyncio.run(store.list_mcp_calls(since_hours=1))
    assert any(r["tool_name"] == "test_echo" and r["outcome"] == "ok" for r in rows)
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tools_dispatch.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.mcp.tools'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/tools/__init__.py`:

```python
"""Tool registry + dispatcher for the MCP server."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from api.local_store import LocalStore
from api.mcp.audit import audit_call

ToolHandler = Callable[[Any, Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: ToolHandler


_REGISTRY: Dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    _REGISTRY[spec.name] = spec


def reset_registry_for_tests() -> None:
    _REGISTRY.clear()


def list_tools() -> List[Dict[str, Any]]:
    return [
        {"name": s.name, "description": s.description, "inputSchema": s.input_schema}
        for s in _REGISTRY.values()
    ]


async def call_tool(
    store: LocalStore, *, client_id: int, tool_name: str, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    spec = _REGISTRY.get(tool_name)
    if spec is None:
        raise KeyError(f"tool not registered: {tool_name}")
    async with audit_call(
        store, client_id=client_id, tool_name=tool_name, args=arguments,
    ) as ctx:
        result = await spec.handler(ctx, arguments)
        ctx.set_outcome("ok")
    return {
        "content": [
            {"type": "text", "text": json.dumps(result, default=str, indent=2)},
        ],
    }
```

In `api/mcp/server.py`, register the `tools/call` handler. Modify the `MCPServer.__init__` to include:

```python
        from api.mcp.tools import list_tools as _list_tools, call_tool as _call_tool
        self._list_tools = _list_tools
        self._call_tool = _call_tool
        self._handlers["tools/call"] = self._handle_tools_call
```

Replace `_handle_tools_list`:

```python
    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {"tools": self._list_tools()}
```

Add:

```python
    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            raise ValueError("tools/call requires 'name'")
        return await self._call_tool(
            self._store, client_id=self._client_id,
            tool_name=name, arguments=arguments,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tools_dispatch.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/tools/__init__.py api/mcp/server.py api/tests/test_mcp_tools_dispatch.py
git commit -m "feat(mcp): tools registry + dispatcher with audit wrapping"
```

---

## Task 11 — `hermes_list_recommendations` tool

**Files:**
- Create: `api/mcp/tools/recommendations.py`
- Create: `api/tests/test_mcp_tool_list_recommendations.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_tool_list_recommendations.py`:

```python
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.recommendations import register


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    reset_registry_for_tests()
    register()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_list_recommendations_filters_by_state(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    asyncio.run(store.create_recommendation({"title": "A", "state": "ready"}))
    asyncio.run(store.create_recommendation({"title": "B", "state": "applied"}))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "hermes_list_recommendations",
                   "arguments": {"state": "ready"}},
    }))
    import json
    body = json.loads(resp["result"]["content"][0]["text"])
    titles = [r["title"] for r in body["recommendations"]]
    assert titles == ["A"]
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_list_recommendations.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.mcp.tools.recommendations'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/tools/recommendations.py`:

```python
"""Recommendation read tools."""
from __future__ import annotations

from typing import Any, Dict

from api.mcp.tools import ToolSpec, register_tool


async def _list_recommendations(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    from api.mcp.server import MCPServer  # noqa: F401 — keep import lazy
    state = args.get("state")
    limit = int(args.get("limit") or 50)
    # ctx doesn't carry the store; the tool fetches it from a thread-local set
    # in the dispatcher. For the implementation here we look it up via a
    # function injection set by register() — see below.
    store = _current_store()
    rows = await store.list_recommendations(state=state, limit=limit)
    return {
        "recommendations": [
            {
                "id": r["id"], "state": r["state"], "title": r["title"],
                "priority": r["priority"], "source": r.get("source"),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
        "count": len(rows),
    }


async def _get_recommendation(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    rec_id = int(args["id"])
    store = _current_store()
    row = await store.get_recommendation(rec_id)
    if row is None:
        return {"error": f"recommendation id={rec_id} not found"}
    return {"recommendation": row}


_STORE: Any = None


def _current_store():
    if _STORE is None:
        raise RuntimeError("MCP store not set; call set_store() first")
    return _STORE


def set_store(store: Any) -> None:
    global _STORE
    _STORE = store


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_list_recommendations",
        description="List recommendations, optionally filtered by state "
                    "(ready|approved|rejected|applied|draft).",
        input_schema={
            "type": "object",
            "properties": {
                "state": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        handler=_list_recommendations,
    ))
    register_tool(ToolSpec(
        name="hermes_get_recommendation",
        description="Fetch a single recommendation by id.",
        input_schema={
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}},
        },
        handler=_get_recommendation,
    ))
```

In `api/mcp/server.py` `run_stdio()`, AFTER constructing `server` and BEFORE the read loop, add:

```python
        from api.mcp.tools.recommendations import register, set_store
        register()
        set_store(store)
```

- [ ] **Step 4: Run the test to verify it passes**

The test also needs `set_store(store)` called in its fixture. Update `api/tests/test_mcp_tool_list_recommendations.py`'s fixture:

```python
@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    reset_registry_for_tests()
    register()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    from api.mcp.tools.recommendations import set_store
    set_store(s)
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)
```

Run:

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_list_recommendations.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/tools/recommendations.py api/mcp/server.py api/tests/test_mcp_tool_list_recommendations.py
git commit -m "feat(mcp): tool hermes_list_recommendations + hermes_get_recommendation"
```

---

## Task 12 — `hermes_list_chat_threads` + `hermes_get_chat_messages` tools

**Files:**
- Create: `api/mcp/tools/chat.py`
- Create: `api/tests/test_mcp_tool_chat.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_tool_chat.py`:

```python
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.chat import register, set_store


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    reset_registry_for_tests()
    register()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    set_store(s)
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_list_threads_returns_threads(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    asyncio.run(store.create_thread({"title": "alpha"}))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "hermes_list_chat_threads", "arguments": {}},
    }))
    body = json.loads(resp["result"]["content"][0]["text"])
    assert any(t["title"] == "alpha" for t in body["threads"])


def test_get_chat_messages_for_nonexistent_returns_empty(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "hermes_get_chat_messages",
                   "arguments": {"thread_id": 999}},
    }))
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["messages"] == []
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_chat.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'api.mcp.tools.chat'`.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/tools/chat.py`:

```python
"""Chat-thread read tools."""
from __future__ import annotations

from typing import Any, Dict

from api.mcp.tools import ToolSpec, register_tool

_STORE: Any = None


def _current_store():
    if _STORE is None:
        raise RuntimeError("MCP store not set; call set_store() first")
    return _STORE


def set_store(store: Any) -> None:
    global _STORE
    _STORE = store


async def _list_threads(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(args.get("limit") or 50)
    rows = await _current_store().list_threads(limit=limit)
    return {"threads": rows, "count": len(rows)}


async def _get_messages(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    thread_id = int(args["thread_id"])
    store = _current_store()
    thread = await store.get_thread(thread_id)
    if thread is None:
        return {"messages": [], "thread": None}
    msgs = await store.list_messages(thread_id=thread_id)
    return {"thread": thread, "messages": msgs}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_list_chat_threads",
        description="List chat threads in the Hermes Console store.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 50}},
        },
        handler=_list_threads,
    ))
    register_tool(ToolSpec(
        name="hermes_get_chat_messages",
        description="Fetch all messages in a chat thread by id.",
        input_schema={
            "type": "object",
            "required": ["thread_id"],
            "properties": {"thread_id": {"type": "integer"}},
        },
        handler=_get_messages,
    ))
```

In `api/mcp/server.py` `run_stdio()`, add right after the recommendations registration:

```python
        from api.mcp.tools.chat import register as register_chat, set_store as set_chat_store
        register_chat()
        set_chat_store(store)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_chat.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/tools/chat.py api/mcp/server.py api/tests/test_mcp_tool_chat.py
git commit -m "feat(mcp): tool hermes_list_chat_threads + hermes_get_chat_messages"
```

---

## Task 13 — `hermes_get_tenant_status` tool

**Files:**
- Create: `api/mcp/tools/bridges.py`
- Create: `api/tests/test_mcp_tool_tenant_status.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_tool_tenant_status.py`:

```python
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.bridges import register, set_bridges


class FakeBridge:
    name = "southbrook_hermes"
    def __init__(self, status="ok"):
        self.health = AsyncMock(return_value=status)


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    reset_registry_for_tests()
    register()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_tenant_status_returns_health_per_bridge(store: LocalStore) -> None:
    set_bridges({"southbrook_hermes": FakeBridge("ok"),
                 "home_assistant": FakeBridge("unreachable")})
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "hermes_get_tenant_status", "arguments": {}},
    }))
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["bridges"]["southbrook_hermes"] == "ok"
    assert body["bridges"]["home_assistant"] == "unreachable"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_tenant_status.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/tools/bridges.py`:

```python
"""Tenant-bridge status read tool."""
from __future__ import annotations

from typing import Any, Dict

from api.mcp.tools import ToolSpec, register_tool

_BRIDGES: Dict[str, Any] = {}


def set_bridges(bridges: Dict[str, Any]) -> None:
    global _BRIDGES
    _BRIDGES = bridges


async def _get_tenant_status(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, str] = {}
    for name, bridge in _BRIDGES.items():
        try:
            out[name] = await bridge.health()
        except Exception as exc:  # noqa: BLE001
            out[name] = f"error: {exc.__class__.__name__}"
    return {"bridges": out}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_get_tenant_status",
        description="Health status of every tenant bridge registered in Hermes.",
        input_schema={"type": "object"},
        handler=_get_tenant_status,
    ))
```

In `api/mcp/server.py` `run_stdio()`, after the chat registration, add:

```python
        from api.mcp.tools.bridges import register as register_bridges, set_bridges
        register_bridges()
        # build_bridges() lives in api.main; importing it here is acceptable
        from api.main import _build_bridges
        from api.models import Settings
        settings = Settings()
        bridges = _build_bridges(settings)
        for b in bridges.values():
            await b.startup()
        set_bridges(bridges)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_tenant_status.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/tools/bridges.py api/mcp/server.py api/tests/test_mcp_tool_tenant_status.py
git commit -m "feat(mcp): tool hermes_get_tenant_status"
```

---

## Task 14 — `hermes_get_provider_health` tool

**Files:**
- Create: `api/mcp/tools/providers.py`
- Create: `api/tests/test_mcp_tool_provider_health.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_tool_provider_health.py`:

```python
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.providers import register, set_provider_registry


class FakeRegistry:
    health = AsyncMock(return_value={
        "openai": "ok",
        "hermes_harness": "disabled",
        "anthropic": "ok",
    })


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    reset_registry_for_tests()
    register()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    set_provider_registry(FakeRegistry())
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_provider_health(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "hermes_get_provider_health", "arguments": {}},
    }))
    body = json.loads(resp["result"]["content"][0]["text"])
    assert body["llm"]["openai"] == "ok"
    assert body["llm"]["anthropic"] == "ok"
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_provider_health.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/tools/providers.py`:

```python
"""LLM provider health read tool."""
from __future__ import annotations

from typing import Any, Dict

from api.mcp.tools import ToolSpec, register_tool

_REGISTRY: Any = None


def set_provider_registry(reg: Any) -> None:
    global _REGISTRY
    _REGISTRY = reg


async def _provider_health(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    if _REGISTRY is None:
        return {"llm": {}, "error": "registry not configured"}
    return {"llm": await _REGISTRY.health()}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_get_provider_health",
        description="Health of every LLM provider configured in Hermes.",
        input_schema={"type": "object"},
        handler=_provider_health,
    ))
```

In `api/mcp/server.py` `run_stdio()`, after bridges, add:

```python
        from api.mcp.tools.providers import register as register_providers, set_provider_registry
        from api.llm import ProviderRegistry
        register_providers()
        registry = ProviderRegistry.from_settings(settings)
        await registry.startup()
        set_provider_registry(registry)
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_provider_health.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/tools/providers.py api/mcp/server.py api/tests/test_mcp_tool_provider_health.py
git commit -m "feat(mcp): tool hermes_get_provider_health"
```

---

## Task 15 — Skill loader (reads custom-hermes-skills metadata + filters)

**Files:**
- Create: `api/mcp/skill_runner.py`
- Create: `api/tests/fixtures/skill-fixture-ok/metadata.json`
- Create: `api/tests/fixtures/skill-fixture-ok/SKILL.md`
- Create: `api/tests/fixtures/skill-fixture-destructive/metadata.json`
- Create: `api/tests/fixtures/skill-fixture-destructive/SKILL.md`
- Create: `api/tests/test_mcp_skill_runner.py`

- [ ] **Step 1: Create the test fixtures**

`api/tests/fixtures/skill-fixture-ok/metadata.json`:

```json
{
  "name": "skill-fixture-ok",
  "version": "0.0.1",
  "category": "meta",
  "summary": "A read-only fixture skill for tests.",
  "needs": ["N-99"],
  "jtbds": ["J-99"],
  "default_mode": "read-only",
  "destructive_actions": false,
  "requires_confirmation": false,
  "outputs": ["custom-hermes-skills/runs/skill-fixture-ok/<ts>.md"]
}
```

`api/tests/fixtures/skill-fixture-ok/SKILL.md`:

```markdown
# Skill Fixture OK

Used by the MCP test suite.
```

`api/tests/fixtures/skill-fixture-destructive/metadata.json`:

```json
{
  "name": "skill-fixture-destructive",
  "version": "0.0.1",
  "category": "meta",
  "summary": "A destructive fixture skill — Phase 1 must filter this out.",
  "needs": ["N-99"],
  "jtbds": ["J-99"],
  "default_mode": "read-only",
  "destructive_actions": true,
  "requires_confirmation": true,
  "outputs": []
}
```

`api/tests/fixtures/skill-fixture-destructive/SKILL.md`:

```markdown
# Skill Fixture Destructive

Used by the MCP test suite to confirm filtering.
```

- [ ] **Step 2: Write the failing test**

Create `api/tests/test_mcp_skill_runner.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from api.mcp.skill_runner import (
    list_read_only_skills,
    load_skill_metadata,
    load_skill_markdown,
    SkillNotFound,
    SkillNotReadOnly,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_list_read_only_skills_filters_destructive() -> None:
    names = list_read_only_skills(skills_root=str(FIXTURES))
    assert "skill-fixture-ok" in names
    assert "skill-fixture-destructive" not in names


def test_load_skill_metadata_returns_dict() -> None:
    md = load_skill_metadata("skill-fixture-ok", skills_root=str(FIXTURES))
    assert md["name"] == "skill-fixture-ok"
    assert md["destructive_actions"] is False


def test_load_skill_metadata_raises_on_missing() -> None:
    with pytest.raises(SkillNotFound):
        load_skill_metadata("nope", skills_root=str(FIXTURES))


def test_load_skill_markdown_returns_text() -> None:
    md = load_skill_markdown("skill-fixture-ok", skills_root=str(FIXTURES))
    assert "Skill Fixture OK" in md


def test_load_destructive_skill_raises_when_read_only_required() -> None:
    with pytest.raises(SkillNotReadOnly):
        load_skill_metadata(
            "skill-fixture-destructive",
            skills_root=str(FIXTURES),
            require_read_only=True,
        )
```

- [ ] **Step 3: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_skill_runner.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 4: Write the minimal implementation**

Create `api/mcp/skill_runner.py`:

```python
"""Load + filter custom-hermes-skills entries for MCP exposure.

Phase 1 surfaces ONLY read-only skills (``destructive_actions == false``).
The runner is intentionally a metadata reader — Phase 1 does NOT execute
skill procedures from inside the MCP server (Phase 2 will). Phase 1 lets
the calling agent FETCH a skill's metadata + SKILL.md and act on them in
its own session — which is the correct safety boundary for v1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_SKILLS_ROOT = "/app/custom-hermes-skills/skills"


class SkillNotFound(Exception):
    pass


class SkillNotReadOnly(Exception):
    pass


def _root(skills_root: str | None) -> Path:
    return Path(skills_root or os.environ.get(
        "HERMES_SKILLS_ROOT", DEFAULT_SKILLS_ROOT))


def list_read_only_skills(*, skills_root: str | None = None) -> List[str]:
    root = _root(skills_root)
    out: List[str] = []
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        m = d / "metadata.json"
        if not m.exists():
            continue
        try:
            meta = json.loads(m.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if meta.get("destructive_actions") is False:
            out.append(d.name)
    return out


def load_skill_metadata(
    name: str, *, skills_root: str | None = None,
    require_read_only: bool = False,
) -> Dict[str, Any]:
    root = _root(skills_root)
    m = root / name / "metadata.json"
    if not m.exists():
        raise SkillNotFound(f"skill not found: {name}")
    meta = json.loads(m.read_text(encoding="utf-8"))
    if require_read_only and meta.get("destructive_actions") is not False:
        raise SkillNotReadOnly(
            f"skill {name} is destructive; Phase 1 forbids exposure"
        )
    return meta


def load_skill_markdown(
    name: str, *, skills_root: str | None = None
) -> str:
    root = _root(skills_root)
    p = root / name / "SKILL.md"
    if not p.exists():
        raise SkillNotFound(f"skill SKILL.md not found: {name}")
    return p.read_text(encoding="utf-8")
```

- [ ] **Step 5: Run the test to verify it passes + commit**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_skill_runner.py -v
```

Expected: 5 passed.

```bash
git add api/mcp/skill_runner.py api/tests/fixtures/ api/tests/test_mcp_skill_runner.py
git commit -m "feat(mcp): skill metadata loader + read-only filter for custom-hermes-skills"
```

---

## Task 16 — `hermes_list_skills` + `hermes_run_skill` tools

**Files:**
- Create: `api/mcp/tools/skills.py`
- Create: `api/tests/test_mcp_tool_skills.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_tool_skills.py`:

```python
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.skills import register, set_skills_root

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    reset_registry_for_tests()
    register()
    set_skills_root(str(FIXTURES))
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_list_skills_returns_only_read_only(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "hermes_list_skills", "arguments": {}},
    }))
    body = json.loads(resp["result"]["content"][0]["text"])
    names = [s["name"] for s in body["skills"]]
    assert "skill-fixture-ok" in names
    assert "skill-fixture-destructive" not in names


def test_run_skill_returns_markdown(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": "hermes_run_skill",
                   "arguments": {"name": "skill-fixture-ok"}},
    }))
    body = json.loads(resp["result"]["content"][0]["text"])
    assert "Skill Fixture OK" in body["skill_markdown"]
    assert body["metadata"]["name"] == "skill-fixture-ok"


def test_run_skill_rejects_destructive(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 3, "method": "tools/call",
        "params": {"name": "hermes_run_skill",
                   "arguments": {"name": "skill-fixture-destructive"}},
    }))
    body = json.loads(resp["result"]["content"][0]["text"])
    assert "destructive" in body.get("error", "").lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_skills.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/tools/skills.py`:

```python
"""Skill catalog + read-only skill loader as MCP tools."""
from __future__ import annotations

from typing import Any, Dict, Optional

from api.mcp.skill_runner import (
    list_read_only_skills,
    load_skill_markdown,
    load_skill_metadata,
    SkillNotFound,
    SkillNotReadOnly,
)
from api.mcp.tools import ToolSpec, register_tool

_SKILLS_ROOT: Optional[str] = None


def set_skills_root(root: str) -> None:
    global _SKILLS_ROOT
    _SKILLS_ROOT = root


async def _list_skills(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    names = list_read_only_skills(skills_root=_SKILLS_ROOT)
    out = []
    for n in names:
        try:
            meta = load_skill_metadata(n, skills_root=_SKILLS_ROOT)
        except SkillNotFound:
            continue
        out.append({
            "name": meta["name"],
            "category": meta.get("category"),
            "summary": meta.get("summary"),
            "needs": meta.get("needs", []),
            "jtbds": meta.get("jtbds", []),
        })
    return {"skills": out, "count": len(out)}


async def _run_skill(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    name = args.get("name")
    if not name:
        return {"error": "missing 'name'"}
    try:
        meta = load_skill_metadata(
            name, skills_root=_SKILLS_ROOT, require_read_only=True,
        )
        markdown = load_skill_markdown(name, skills_root=_SKILLS_ROOT)
    except SkillNotReadOnly as exc:
        return {"error": f"destructive skill rejected: {exc}"}
    except SkillNotFound as exc:
        return {"error": str(exc)}
    return {"metadata": meta, "skill_markdown": markdown}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_list_skills",
        description="List read-only skills from custom-hermes-skills.",
        input_schema={"type": "object"},
        handler=_list_skills,
    ))
    register_tool(ToolSpec(
        name="hermes_run_skill",
        description="Fetch a read-only skill's metadata + SKILL.md text. "
                    "Phase 1 returns the procedure — calling agent executes "
                    "it in its own session.",
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        },
        handler=_run_skill,
    ))
```

In `api/mcp/server.py` `run_stdio()`, after providers, add:

```python
        from api.mcp.tools.skills import register as register_skills, set_skills_root
        import os
        register_skills()
        set_skills_root(os.environ.get(
            "HERMES_SKILLS_ROOT", "/app/custom-hermes-skills/skills"))
```

- [ ] **Step 4: Run the tests to verify they pass**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_tool_skills.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/tools/skills.py api/mcp/server.py api/tests/test_mcp_tool_skills.py
git commit -m "feat(mcp): tools hermes_list_skills + hermes_run_skill (read-only filter)"
```

---

## Task 17 — Resources: list + read for recommendations, chat-threads, skills, audit

**Files:**
- Create: `api/mcp/resources.py`
- Modify: `api/mcp/server.py` (add resources/list + resources/read handlers)
- Create: `api/tests/test_mcp_resources.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_resources.py`:

```python
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.resources import set_resources_context

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    reset_registry_for_tests()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    set_resources_context(store=s, skills_root=str(FIXTURES))
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_resources_list_includes_skills(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {},
    }))
    uris = [r["uri"] for r in resp["result"]["resources"]]
    assert any(u.startswith("hermes://skills/") for u in uris)
    assert any(u == "hermes://audit/today" for u in uris)


def test_resources_read_skill_md(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "resources/read",
        "params": {"uri": "hermes://skills/skill-fixture-ok/SKILL.md"},
    }))
    contents = resp["result"]["contents"]
    assert "Skill Fixture OK" in contents[0]["text"]


def test_resources_read_audit_today(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    asyncio.run(store.log_mcp_call(
        client_id=cid, tool_name="hermes_list_recommendations",
        args_redacted={"state": "ready"}, outcome="ok",
        error_text=None, duration_ms=3,
    ))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 3, "method": "resources/read",
        "params": {"uri": "hermes://audit/today"},
    }))
    body = json.loads(resp["result"]["contents"][0]["text"])
    assert body["count"] >= 1
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_resources.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/resources.py`:

```python
"""MCP resources: enumerate + read."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from api.local_store import LocalStore
from api.mcp.skill_runner import (
    list_read_only_skills, load_skill_markdown, load_skill_metadata,
    SkillNotFound,
)

_STORE: Optional[LocalStore] = None
_SKILLS_ROOT: Optional[str] = None


def set_resources_context(*, store: LocalStore, skills_root: str) -> None:
    global _STORE, _SKILLS_ROOT
    _STORE = store
    _SKILLS_ROOT = skills_root


def _require_store() -> LocalStore:
    if _STORE is None:
        raise RuntimeError("resources store not set")
    return _STORE


async def list_resources() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    out.append({
        "uri": "hermes://recommendations",
        "name": "All recommendations (JSON)",
        "mimeType": "application/json",
    })
    out.append({
        "uri": "hermes://chat-threads",
        "name": "All chat threads (JSON)",
        "mimeType": "application/json",
    })
    out.append({
        "uri": "hermes://audit/today",
        "name": "MCP tool-call audit for the last 24h",
        "mimeType": "application/json",
    })
    for name in list_read_only_skills(skills_root=_SKILLS_ROOT):
        out.append({
            "uri": f"hermes://skills/{name}/SKILL.md",
            "name": f"Skill: {name} (SKILL.md)",
            "mimeType": "text/markdown",
        })
        out.append({
            "uri": f"hermes://skills/{name}/metadata.json",
            "name": f"Skill: {name} (metadata.json)",
            "mimeType": "application/json",
        })
    return out


async def read_resource(uri: str) -> Dict[str, Any]:
    if uri == "hermes://recommendations":
        rows = await _require_store().list_recommendations()
        return _json(uri, {"recommendations": rows, "count": len(rows)})
    if uri == "hermes://chat-threads":
        rows = await _require_store().list_threads()
        return _json(uri, {"threads": rows, "count": len(rows)})
    if uri == "hermes://audit/today":
        rows = await _require_store().list_mcp_calls(since_hours=24)
        return _json(uri, {"calls": rows, "count": len(rows)})
    if uri.startswith("hermes://skills/"):
        rest = uri[len("hermes://skills/"):]
        if "/" not in rest:
            raise ValueError(f"unknown resource: {uri}")
        name, filename = rest.split("/", 1)
        try:
            if filename == "SKILL.md":
                return _markdown(uri, load_skill_markdown(
                    name, skills_root=_SKILLS_ROOT))
            if filename == "metadata.json":
                return _json(uri, load_skill_metadata(
                    name, skills_root=_SKILLS_ROOT))
        except SkillNotFound as exc:
            raise ValueError(str(exc))
    raise ValueError(f"unknown resource: {uri}")


def _json(uri: str, body: Any) -> Dict[str, Any]:
    return {
        "contents": [{
            "uri": uri,
            "mimeType": "application/json",
            "text": json.dumps(body, default=str, indent=2),
        }],
    }


def _markdown(uri: str, text: str) -> Dict[str, Any]:
    return {
        "contents": [{
            "uri": uri,
            "mimeType": "text/markdown",
            "text": text,
        }],
    }
```

In `api/mcp/server.py` `MCPServer.__init__`, append to `self._handlers`:

```python
        self._handlers["resources/list"] = self._handle_resources_list
        self._handlers["resources/read"] = self._handle_resources_read
```

Add the two methods:

```python
    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from api.mcp.resources import list_resources
        return {"resources": await list_resources()}

    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from api.mcp.resources import read_resource
        uri = params.get("uri")
        if not uri:
            raise ValueError("resources/read requires 'uri'")
        return await read_resource(uri)
```

In `run_stdio()`, after the skills tool registration, add:

```python
        from api.mcp.resources import set_resources_context
        set_resources_context(
            store=store,
            skills_root=os.environ.get(
                "HERMES_SKILLS_ROOT", "/app/custom-hermes-skills/skills"),
        )
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_resources.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/resources.py api/mcp/server.py api/tests/test_mcp_resources.py
git commit -m "feat(mcp): resources/list + resources/read for recos, chat, skills, audit"
```

---

## Task 18 — Prompts: `review-queue` + `use-skill/<name>`

**Files:**
- Create: `api/mcp/prompts.py`
- Modify: `api/mcp/server.py` (add prompts/list + prompts/get handlers)
- Create: `api/tests/test_mcp_prompts.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_prompts.py`:

```python
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

import pytest

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.prompts import set_prompts_context

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def store() -> LocalStore:
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    reset_registry_for_tests()
    s = LocalStore(tmp.name)
    asyncio.run(s.startup())
    set_prompts_context(skills_root=str(FIXTURES))
    yield s
    asyncio.run(s.shutdown())
    Path(tmp.name).unlink(missing_ok=True)


def test_prompts_list_includes_review_queue_and_per_skill(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {},
    }))
    names = [p["name"] for p in resp["result"]["prompts"]]
    assert "review-queue" in names
    assert "use-skill/skill-fixture-ok" in names


def test_prompt_get_review_queue(store: LocalStore) -> None:
    cid = asyncio.run(store.create_mcp_client(name="x", key_hash="h"))
    srv = MCPServer(store, client_id=cid, client_name="x")
    resp = asyncio.run(srv.dispatch({
        "jsonrpc": "2.0", "id": 2, "method": "prompts/get",
        "params": {"name": "review-queue", "arguments": {}},
    }))
    messages = resp["result"]["messages"]
    assert messages[0]["role"] == "user"
    assert "review" in messages[0]["content"]["text"].lower()
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_prompts.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Write the minimal implementation**

Create `api/mcp/prompts.py`:

```python
"""MCP prompts: review-queue + use-skill/<name>."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.mcp.skill_runner import (
    list_read_only_skills, load_skill_markdown, SkillNotFound,
)

_SKILLS_ROOT: Optional[str] = None


def set_prompts_context(*, skills_root: str) -> None:
    global _SKILLS_ROOT
    _SKILLS_ROOT = skills_root


async def list_prompts() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = [{
        "name": "review-queue",
        "description":
            "Show me what's open in the Hermes recommendation queue and "
            "propose the next action.",
    }]
    for name in list_read_only_skills(skills_root=_SKILLS_ROOT):
        out.append({
            "name": f"use-skill/{name}",
            "description": f"Guided template for invoking the '{name}' skill.",
        })
    return out


async def get_prompt(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "review-queue":
        return {
            "description": "Review the open Hermes queue and propose action.",
            "messages": [{
                "role": "user",
                "content": {"type": "text", "text": (
                    "Review the open recommendations in the Hermes Console. "
                    "Use the tool 'hermes_list_recommendations' with "
                    "state='ready' to fetch them, then propose the single "
                    "most important next action and why."
                )},
            }],
        }
    if name.startswith("use-skill/"):
        skill_name = name[len("use-skill/"):]
        try:
            md = load_skill_markdown(skill_name, skills_root=_SKILLS_ROOT)
        except SkillNotFound:
            raise ValueError(f"no such skill: {skill_name}")
        return {
            "description": f"Guided invocation of skill '{skill_name}'.",
            "messages": [{
                "role": "user",
                "content": {"type": "text", "text": (
                    f"You will invoke the Hermes skill '{skill_name}' via the "
                    "MCP tool 'hermes_run_skill'. Read the SKILL.md text "
                    "BELOW for inputs, outputs, safety constraints, and the "
                    "step-by-step operating procedure. Then carry out the "
                    "procedure in this session and report the findings.\n\n"
                    f"---\n\n{md}"
                )},
            }],
        }
    raise ValueError(f"no such prompt: {name}")
```

In `api/mcp/server.py` `MCPServer.__init__`, append to `self._handlers`:

```python
        self._handlers["prompts/list"] = self._handle_prompts_list
        self._handlers["prompts/get"] = self._handle_prompts_get
```

Add the two methods:

```python
    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from api.mcp.prompts import list_prompts
        return {"prompts": await list_prompts()}

    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from api.mcp.prompts import get_prompt
        name = params.get("name")
        if not name:
            raise ValueError("prompts/get requires 'name'")
        return await get_prompt(name, params.get("arguments") or {})
```

In `run_stdio()`, after `set_resources_context`, add:

```python
        from api.mcp.prompts import set_prompts_context
        set_prompts_context(skills_root=os.environ.get(
            "HERMES_SKILLS_ROOT", "/app/custom-hermes-skills/skills"))
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_prompts.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add api/mcp/prompts.py api/mcp/server.py api/tests/test_mcp_prompts.py
git commit -m "feat(mcp): prompts/list + prompts/get for review-queue + use-skill/<name>"
```

---

## Task 19 — Mount custom-hermes-skills into hermes-api container

**Files:**
- Modify: `docker-compose.yml` (extend `hermes-api.volumes`)
- Modify: `api/Dockerfile` (no changes — just verify)

- [ ] **Step 1: Add the bind-mount**

In `~/hermes-console/docker-compose.yml`, find the `hermes-api.volumes:` block (already contains `- hermes-data:/data` and the new `/data/backup-status` from Task 19 of the backup plan). Append:

```yaml
      - ./custom-hermes-skills:/app/custom-hermes-skills:ro
```

- [ ] **Step 2: Validate the compose file**

Run (locally):

```bash
cd ~/hermes-console
docker compose config --quiet
echo "OK"
```

Expected: `OK` (and no validation errors).

- [ ] **Step 3: Rebuild + recreate hermes-api on QNAP**

```bash
ssh admin@ssh.odooiq.com 'cd /share/CACHEDEV3_DATA/Container/hermes-console && \
  DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker compose \
  up -d --force-recreate hermes-api 2>&1 | tail -5'
```

Expected: `Container hermes-api  Started`.

- [ ] **Step 4: Verify the mount is live + skills are readable**

```bash
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api \
  ls /app/custom-hermes-skills/skills | head -5'
```

Expected: A list of skill folder names (e.g. `auth-token-safety-auditor`, `cloudflare-dns-zero-trust-ops`, …).

- [ ] **Step 5: Commit**

```bash
git add docker-compose.yml
git commit -m "feat(mcp): bind-mount custom-hermes-skills into hermes-api for MCP"
```

---

## Task 20 — Operator-Mac wrapper script + Claude Code mcp.json template

**Files:**
- Create: `~/bin/hermes-mcp` (operator's Mac side, NOT in the repo)
- Create: `docs/mcp/claude-code-mcp.json.example` (in repo)
- Create: `docs/mcp/SETUP.md` (in repo)

- [ ] **Step 1: Write the operator-side wrapper script**

Create `~/bin/hermes-mcp` on the operator's Mac and `chmod 755`:

```bash
#!/usr/bin/env bash
# Hermes MCP stdio launcher — Claude Code spawns this.
# Reads the per-client API key from ~/.config/hermes/mcp-key-<client>
# (file mode 600) and SSH+docker-exec into the running hermes-api on QNAP.

set -euo pipefail

CLIENT="${HERMES_MCP_CLIENT:-claude-code-main}"
KEY_FILE="${HOME}/.config/hermes/mcp-key-${CLIENT}"

if [[ ! -r "$KEY_FILE" ]]; then
  echo "hermes-mcp: cannot read key file $KEY_FILE" >&2
  echo "Generate one with:" >&2
  echo "  ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api python -m api.mcp keygen --client $CLIENT'" >&2
  exit 1
fi

KEY="$(cat "$KEY_FILE")"

exec ssh -q -o ControlMaster=auto -o ControlPersist=10m \
  admin@ssh.odooiq.com \
  "DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec -i hermes-api python -m api.mcp stdio --key '$KEY'"
```

- [ ] **Step 2: Write the Claude Code mcp.json example**

Create `docs/mcp/claude-code-mcp.json.example`:

```json
{
  "mcpServers": {
    "hermes": {
      "command": "/Users/naadmin/bin/hermes-mcp",
      "env": {
        "HERMES_MCP_CLIENT": "claude-code-main"
      }
    }
  }
}
```

- [ ] **Step 3: Write the operator setup doc**

Create `docs/mcp/SETUP.md`:

```markdown
# Hermes MCP — Operator Setup (Phase 1)

## One-time, on the QNAP

Generate a key for each client (Claude Code session, Codex session, …):

```
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api python -m api.mcp keygen --client claude-code-main'
```

The key is shown ONCE. Copy it.

## One-time, on the operator Mac

```
mkdir -p ~/.config/hermes
echo '<paste-the-key-here>' > ~/.config/hermes/mcp-key-claude-code-main
chmod 600 ~/.config/hermes/mcp-key-claude-code-main
```

Copy the wrapper script to `~/bin/hermes-mcp` (see `docs/mcp/SETUP.md`
section "Wrapper script") and `chmod 755`.

Copy `docs/mcp/claude-code-mcp.json.example` into your Claude Code
config directory as `mcp.json` (update the command path if your `~/bin`
isn't on PATH for Claude Code).

## Verify

In a Claude Code session, ask: "Use the MCP tool hermes_get_provider_health to show me Hermes's LLM provider state."

Expected: Claude Code calls the tool and shows back a JSON with
`openai`, `hermes_harness`, `anthropic` health statuses.

## Audit

Every MCP call is recorded. To see the audit:

```
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api curl -s http://localhost:8000/api/mcp/calls?since_hours=24 | jq'
```

(Note: the `/api/mcp/calls` REST endpoint is added in Task 22; until
then audit can be inspected directly from the SQLite store on QNAP.)

## Revoke a key

```
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api python -m api.mcp keys revoke --id <N>'
```

`<N>` is the id you see in `python -m api.mcp keys list`.
```

- [ ] **Step 4: Commit**

```bash
git add docs/mcp/
git commit -m "docs(mcp): operator setup + Claude Code mcp.json example"
```

---

## Task 21 — Companion SKILL.md at custom-hermes-skills/skills/hermes-mcp-service/

**Files:**
- Create: `custom-hermes-skills/skills/hermes-mcp-service/SKILL.md`
- Create: `custom-hermes-skills/skills/hermes-mcp-service/metadata.json`
- Create: `custom-hermes-skills/skills/hermes-mcp-service/SOURCE_INSPIRATION.md`

- [ ] **Step 1: Create the metadata**

`custom-hermes-skills/skills/hermes-mcp-service/metadata.json`:

```json
{
  "name": "hermes-mcp-service",
  "version": "0.1.0",
  "category": "meta",
  "summary": "Operator-facing reference for the Hermes MCP service: setup, troubleshooting, audit, key rotation.",
  "needs": ["N-16", "N-18"],
  "jtbds": ["J-09", "J-10", "J-12"],
  "default_mode": "read-only",
  "destructive_actions": false,
  "requires_confirmation": false,
  "learning_enabled": true,
  "outputs": [
    "custom-hermes-skills/runs/hermes-mcp-service/<ts>.md"
  ]
}
```

- [ ] **Step 2: Create SOURCE_INSPIRATION.md**

`custom-hermes-skills/skills/hermes-mcp-service/SOURCE_INSPIRATION.md`:

```markdown
# Source Inspiration — hermes-mcp-service

| Source Repo | Source Skill/Pattern | What Was Preserved | What Was Changed | Why It Was Changed | License Notes |
|---|---|---|---|---|---|
| (none) | (none) | n/a | Built from the spec at docs/superpowers/specs/2026-06-17-hermes-mcp-service-design.md and the Phase 1 implementation plan at docs/superpowers/plans/2026-06-17-hermes-mcp-phase1.md. The 7 tools + 6 resource patterns + 2 prompt classes are the Phase 1 inventory. | n/a | Original work. |
```

- [ ] **Step 3: Create SKILL.md**

`custom-hermes-skills/skills/hermes-mcp-service/SKILL.md`:

```markdown
# Hermes MCP Service

**Skill name:** `hermes-mcp-service`
**Category:** `meta`

## Purpose

Operator-facing reference for the Hermes MCP service: how to set up a new client (Claude Code, Codex), how to audit, how to rotate keys, how to troubleshoot. Phase 1 is read-only stdio; Phase 2 adds write operations + HTTP+SSE.

## When to use

- Onboarding a new MCP client (a new Claude Code workspace, Codex session, etc.)
- Reviewing the audit log
- Rotating an API key
- Debugging an MCP connection from a coding agent

## When NOT to use

- Designing a new Phase 2 tool — that belongs in the spec, not in operator notes
- Adding raw provider keys to MCP clients — providers are mediated by `hermes_chat`

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `mode` | enum | yes | `setup` / `audit` / `rotate-key` / `troubleshoot` |
| `client_name` | str | yes for setup / rotate-key | E.g. `claude-code-main`, `codex-southbrook` |

## Outputs produced

- `runs/hermes-mcp-service/<mode>-<ts>.md` — operator report

## Step-by-step operating procedure

### `setup`

1. `keygen` on QNAP: `docker exec hermes-api python -m api.mcp keygen --client <client_name>`
2. Save key to `~/.config/hermes/mcp-key-<client_name>` on operator Mac, `chmod 600`
3. Wrapper script at `~/bin/hermes-mcp` (see `docs/mcp/SETUP.md`)
4. Update Claude Code `mcp.json` with the wrapper as `command`
5. Verify in a Claude Code session: ask it to call `hermes_get_provider_health`

### `audit`

1. Query: `docker exec hermes-api python -c 'import asyncio; from api.local_store import LocalStore; s=LocalStore("/data/hermes.sqlite"); asyncio.run(s.startup()); print(asyncio.run(s.list_mcp_calls(since_hours=24)))'`
2. Or use the REST endpoint once Task 22 lands: `curl http://localhost:8000/api/mcp/calls?since_hours=24`

### `rotate-key`

1. Generate the NEW key (`keygen`)
2. Update `~/.config/hermes/mcp-key-<client_name>` on Mac with the new value
3. Verify the new key works in a Claude Code session
4. ONLY THEN: revoke the old key: `python -m api.mcp keys revoke --id <old-id>` (same order as the HA token rotation pattern)

### `troubleshoot`

| Symptom | Probable cause | Resolution |
|---|---|---|
| MCP `initialize` returns error | wrong key | re-check `~/.config/hermes/mcp-key-<client>` matches the value `keygen` printed |
| MCP `tools/list` returns `[]` | server didn't register the tools | check `docker logs hermes-api` for "mcp stdio ready" + registration errors |
| `tools/call` for a destructive skill returns error | by-design — Phase 1 filters destructive_actions=true | use Phase 2 once available, OR run the skill manually outside MCP |
| Connection drops mid-session | ssh ControlPersist expired | the wrapper sets `ControlPersist=10m`; raise if your sessions are longer |

## Related Need IDs

`N-16`, `N-18`

## Related JTBD IDs

`J-09`, `J-10`, `J-12`

## Safety constraints

- Per-agent keys; revocation takes effect on the NEXT call (no shared client identity)
- Phase 1 is read-only — no agent can write to the queue, fire bridges, or trigger loops
- Audit captures every call with arg redaction

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `setup`, `audit`, `troubleshoot` | none |
| `rotate-key` | operator follows the "verify NEW before revoking OLD" order |

## Validation checklist

- [ ] Wrapper script at `~/bin/hermes-mcp` is `chmod 755` and reads the right key file
- [ ] `mcp.json` `command` points at the wrapper
- [ ] At least one successful `tools/call` recorded in `mcp_calls`
- [ ] No raw API key value appears in any audit row (redaction working)

## Examples

```
$ python -m api.mcp keygen --client codex-hermes-ui
mcp_key_codex-hermes-ui_2026-06-17_abc123…

$ python -m api.mcp keys list
[{"id": 1, "name": "claude-code-main", …}, {"id": 2, "name": "codex-hermes-ui", …}]
```

## Troubleshooting

(See the matrix above under operating procedure.)

## Source inspiration

See `SOURCE_INSPIRATION.md`.
```

- [ ] **Step 4: Validate the library**

```bash
cd ~/hermes-console/custom-hermes-skills
python3 scripts/validate_skills.py | tail -3
python3 scripts/build_index.py | tail -1
```

Expected: `Validated 43 skills:  blockers: 0  warns: 0` and `Wrote SKILLS_INDEX.md with 43 skills`.

- [ ] **Step 5: Commit**

```bash
cd ~/hermes-console
git add custom-hermes-skills/skills/hermes-mcp-service/ custom-hermes-skills/SKILLS_INDEX.md
git commit -m "feat(skills): hermes-mcp-service companion SKILL.md"
```

---

## Task 22 — REST endpoint `GET /api/mcp/calls` (audit lens for the UI)

**Files:**
- Modify: `api/main.py` (add the route at the bottom, near other GET endpoints)
- Create: `api/tests/test_mcp_calls_endpoint.py`

- [ ] **Step 1: Write the failing test**

Create `api/tests/test_mcp_calls_endpoint.py`:

```python
"""Smoke for GET /api/mcp/calls."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from api.tests.test_smoke import _make_app


def test_mcp_calls_endpoint_returns_recent() -> None:
    app, store = _make_app()
    with TestClient(app) as client:
        # log a row directly via the LocalStore behind the app
        async def seed() -> None:
            cid = await store.create_mcp_client(name="claude-code", key_hash="h")
            await store.log_mcp_call(
                client_id=cid, tool_name="hermes_list_recommendations",
                args_redacted={"state": "ready"}, outcome="ok",
                error_text=None, duration_ms=10,
            )
        asyncio.run(seed())
        resp = client.get("/api/mcp/calls?since_hours=24")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] >= 1
        assert data["calls"][0]["tool_name"] == "hermes_list_recommendations"
```

You may need to expose a `_make_app` helper in `api/tests/test_smoke.py` if one isn't already there. If it isn't, refactor the existing test_smoke setup into a callable that returns `(app, store)`.

- [ ] **Step 2: Run the test to verify it fails**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_calls_endpoint.py -v
```

Expected: FAIL with 404 (the route doesn't exist yet).

- [ ] **Step 3: Write the minimal implementation**

In `api/main.py`, find the area where existing GET routes are registered (search for `@app.get("/api/agents"` or similar). Add:

```python
    @app.get("/api/mcp/calls")
    async def list_mcp_calls(
        request: Request,
        since_hours: int = 24,
    ) -> Dict[str, Any]:
        store = _store(request)
        rows = await store.list_mcp_calls(since_hours=since_hours)
        return {"count": len(rows), "calls": rows}
```

(`_store(request)` is the existing helper used elsewhere in `api/main.py`. `Request` and `Dict[str, Any]` are already imported at the top of the file.)

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd ~/hermes-console
PYTHONPATH=. python3 -m pytest api/tests/test_mcp_calls_endpoint.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add api/main.py api/tests/test_mcp_calls_endpoint.py
git commit -m "feat(mcp): GET /api/mcp/calls audit endpoint"
```

---

## Task 23 — End-to-end smoke: real stdio session against the QNAP

**Files:**
- Create: `api/tests/test_mcp_e2e_stdio.py` (skipped by default; runs only with env flag set)

- [ ] **Step 1: Write the smoke test**

Create `api/tests/test_mcp_e2e_stdio.py`:

```python
"""End-to-end MCP stdio smoke against a live QNAP.

Skipped unless ``HERMES_MCP_E2E=1`` is set, and requires:
  - ssh access to admin@ssh.odooiq.com
  - a generated mcp key for client 'e2e-test' on the QNAP
  - the key in ~/.config/hermes/mcp-key-e2e-test

Runs three sequential calls:
  1. initialize
  2. tools/list (expect ≥6 tools registered)
  3. tools/call hermes_get_provider_health (expect 200 + non-empty llm dict)
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

E2E = os.environ.get("HERMES_MCP_E2E") == "1"
pytestmark = pytest.mark.skipif(not E2E, reason="HERMES_MCP_E2E=1 to enable")


def _wrapper_path() -> str:
    return os.path.expanduser("~/bin/hermes-mcp")


def _send(proc: subprocess.Popen, method: str, params: dict, _id: int) -> dict:
    proc.stdin.write(json.dumps({
        "jsonrpc": "2.0", "id": _id,
        "method": method, "params": params,
    }) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    return json.loads(line)


def test_e2e_stdio_three_calls() -> None:
    if not Path(_wrapper_path()).exists():
        pytest.skip("wrapper not installed")
    env = os.environ.copy()
    env["HERMES_MCP_CLIENT"] = "e2e-test"
    proc = subprocess.Popen(
        [_wrapper_path()],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=env, text=True,
    )
    try:
        init = _send(proc, "initialize", {
            "protocolVersion": "2025-06-18",
            "clientInfo": {"name": "e2e-test", "version": "0.0"},
            "capabilities": {},
        }, 1)
        assert init["result"]["serverInfo"]["name"] == "hermes-mcp"

        tools = _send(proc, "tools/list", {}, 2)
        names = [t["name"] for t in tools["result"]["tools"]]
        assert "hermes_get_provider_health" in names
        assert "hermes_list_recommendations" in names
        assert "hermes_list_skills" in names
        assert len(names) >= 6

        health = _send(proc, "tools/call", {
            "name": "hermes_get_provider_health", "arguments": {},
        }, 3)
        body = json.loads(health["result"]["content"][0]["text"])
        assert "llm" in body
    finally:
        proc.stdin.close()
        proc.wait(timeout=10)
```

- [ ] **Step 2: Generate the e2e key on QNAP**

```bash
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api \
  python -m api.mcp keygen --client e2e-test' 2>&1 | tee /tmp/e2e-key.txt
```

Save the printed key to `~/.config/hermes/mcp-key-e2e-test` (`chmod 600`).

- [ ] **Step 3: Run the smoke**

```bash
cd ~/hermes-console
HERMES_MCP_E2E=1 PYTHONPATH=. python3 -m pytest api/tests/test_mcp_e2e_stdio.py -v
```

Expected: 1 passed.

- [ ] **Step 4: Revoke the e2e key**

```bash
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api \
  python -m api.mcp keys list' | jq '.[]|select(.name=="e2e-test")|.id'
# pipe the id into:
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api \
  python -m api.mcp keys revoke --id <N>'
```

Delete the local key file:

```bash
shred -u ~/.config/hermes/mcp-key-e2e-test
```

- [ ] **Step 5: Commit**

```bash
git add api/tests/test_mcp_e2e_stdio.py
git commit -m "test(mcp): end-to-end stdio smoke (skipped unless HERMES_MCP_E2E=1)"
```

---

## Task 24 — Ship-gate verification

**Files:**
- No new files. This task is a manual verification + log.

- [ ] **Step 1: Generate a real key for Claude Code**

Per Task 20 SETUP.md instructions. Client name: `claude-code-main`.

- [ ] **Step 2: Use Claude Code with the MCP wired in. Run 5 different real sessions, each using ≥3 read-only skills via MCP**

Examples of sessions that satisfy the ship gate:

| Session # | Skills invoked via MCP |
|---|---|
| 1 | `hermes_list_recommendations`, `hermes_get_provider_health`, `hermes_list_skills` |
| 2 | `hermes_list_chat_threads`, `hermes_get_chat_messages`, `hermes_run_skill` (e.g. `qnap-resource-auditor`) |
| 3 | `hermes_run_skill` × 3 different skills |
| 4 | `hermes_list_skills`, `hermes_run_skill` (`cloudflare-dns-zero-trust-ops`), `hermes_get_tenant_status` |
| 5 | `hermes_list_recommendations` (state=ready), `hermes_list_recommendations` (state=approved), `hermes_get_provider_health` |

- [ ] **Step 3: Verify in audit table that all 5 sessions appear**

```bash
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api \
  curl -s http://localhost:8000/api/mcp/calls?since_hours=24 | jq ".count, .calls | length"'
```

Expected: ≥15 (5 sessions × ≥3 calls each).

- [ ] **Step 4: Verify zero failed calls during ship-gate window**

```bash
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api \
  curl -s http://localhost:8000/api/mcp/calls?since_hours=24 | jq "[.calls[]|select(.outcome!=\"ok\")]|length"'
```

Expected: `0`.

- [ ] **Step 5: Update the spec status + commit**

In `docs/superpowers/specs/2026-06-17-hermes-mcp-service-design.md`, top metadata table, change `Status` from `Draft — design approved by operator, awaiting implementation plan` to `Phase 1 SHIPPED 2026-MM-DD`.

```bash
cd ~/hermes-console
git add docs/superpowers/specs/2026-06-17-hermes-mcp-service-design.md
git commit -m "docs(mcp): Phase 1 ship gate cleared — 5 sessions × ≥3 skills, 0 failures"
```

---

## Self-review (already done by the author)

**Spec coverage:** Every F1-F8 functional requirement and every N1-N6 non-functional requirement maps to one of Tasks 1-24. F9 (Hermes-as-MCP-client of upstreams) is explicitly Phase 3 per the spec and is NOT covered here.

**Placeholder scan:** No `TBD`, `TODO`, `implement later`. Every code block contains complete code. Every command shows expected output.

**Type consistency:** `ToolSpec`, `ToolHandler`, `audit_call`, `register_tool`, `set_store`, `set_resources_context`, `set_prompts_context` — all names referenced in later tasks match their first definition.

**Scope:** Phase 1 read-only stdio. Phase 2 (write tools, HTTP+SSE) and Phase 3 (Hermes-as-MCP-client) each get their own plan.

---

Plan complete and saved to `docs/superpowers/plans/2026-06-17-hermes-mcp-phase1.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
