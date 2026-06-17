"""Tests for the per-call audit context manager."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from api.local_store import LocalStore
from api.mcp.audit import audit_call


def test_audit_call_logs_success() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            async with audit_call(
                store, client_id=cid, tool_name="hermes_get_provider_health",
                args={"foo": "bar"},
            ) as ctx:
                ctx.set_outcome("ok")
            rows = await store.list_mcp_calls(since_hours=1)
            assert len(rows) == 1
            assert rows[0]["outcome"] == "ok"
            assert rows[0]["tool_name"] == "hermes_get_provider_health"
            await store.shutdown()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_audit_call_redacts_args() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            async with audit_call(
                store, client_id=cid, tool_name="hermes_chat",
                args={"k": "sk-proj-9Tpva-KPRV9jsLM0R48a7sbbBPGVq1LL"},
            ) as ctx:
                ctx.set_outcome("ok")
            rows = await store.list_mcp_calls(since_hours=1)
            assert "sk-proj-" not in rows[0]["args_redacted_json"]
            await store.shutdown()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_audit_call_logs_exception_as_error() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            try:
                async with audit_call(
                    store, client_id=cid, tool_name="hermes_run_skill",
                    args={"skill": "nope"},
                ) as ctx:
                    raise ValueError("skill nope not found")
            except ValueError:
                pass
            rows = await store.list_mcp_calls(since_hours=1)
            assert rows[0]["outcome"] == "error"
            assert "skill nope not found" in (rows[0]["error_text"] or "")
            await store.shutdown()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
