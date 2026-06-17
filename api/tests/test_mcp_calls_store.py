"""SQLite tests for the mcp_calls audit table."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from api.local_store import LocalStore


def test_log_then_list_call() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="claude-code", key_hash="h1")
            call_id = await store.log_mcp_call(
                client_id=cid,
                tool_name="hermes_list_recommendations",
                args_redacted={"state": "ready"},
                outcome="ok",
                error_text=None,
                duration_ms=12,
            )
            assert call_id >= 1
            rows = await store.list_mcp_calls(since_hours=24)
            assert len(rows) == 1
            assert rows[0]["client_id"] == cid
            assert rows[0]["tool_name"] == "hermes_list_recommendations"
            assert rows[0]["outcome"] == "ok"
            assert rows[0]["duration_ms"] == 12
            await store.shutdown()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_log_failure_records_error() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="codex", key_hash="h2")
            await store.log_mcp_call(
                client_id=cid,
                tool_name="hermes_run_skill",
                args_redacted={"skill": "nope"},
                outcome="error",
                error_text="skill nope not found",
                duration_ms=2,
            )
            rows = await store.list_mcp_calls(since_hours=24)
            assert rows[0]["outcome"] == "error"
            assert rows[0]["error_text"] == "skill nope not found"
            await store.shutdown()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
