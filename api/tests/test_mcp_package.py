"""Package layout sanity checks for the new MCP module + keygen/keys CLI tests."""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile

import pytest


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


def _run_cli(*args: str, env_extra: "dict[str, str] | None" = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
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
