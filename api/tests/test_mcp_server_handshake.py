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


def _jsonrpc(method: str, params: "dict | None" = None, _id: int = 1) -> str:
    return json.dumps({"jsonrpc": "2.0", "id": _id, "method": method,
                       "params": params or {}})


def _env_for_run(tmp_db: str) -> "dict[str, str]":
    env = os.environ.copy()
    env["HERMES_SQLITE_PATH"] = tmp_db
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return env


def test_initialize_returns_server_info(tmp_db: str, valid_key: str) -> None:
    proc = subprocess.Popen(
        [sys.executable, "-m", "api.mcp", "stdio", "--key", valid_key],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env=_env_for_run(tmp_db), text=True,
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
    res = subprocess.run(
        [sys.executable, "-m", "api.mcp", "stdio", "--key", "bogus"],
        capture_output=True, text=True, timeout=10, env=_env_for_run(tmp_db),
    )
    assert res.returncode != 0
    assert "invalid" in res.stderr.lower() or "unauthorized" in res.stderr.lower()
