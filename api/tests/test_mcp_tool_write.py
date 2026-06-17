"""Tests for the Phase 2 write tools."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.write import register, set_write_context


class FakeBridge:
    name = "southbrook_hermes"

    def __init__(self) -> None:
        self.health = AsyncMock(return_value="ok")
        self.push = AsyncMock(return_value={"ok": True, "consumer_id": 999})


class FakeRunner:
    async def run_once(self, name: str):
        if name == "nope":
            raise KeyError(name)
        return {"status": "ok", "recommendations_created": [],
                "loop": name}


def test_file_recommendation_creates_row() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            store = LocalStore(tmp.name)
            await store.startup()
            set_write_context(store=store, agent_runner=FakeRunner(),
                              bridges={"southbrook_hermes": FakeBridge()})
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_file_recommendation",
                           "arguments": {"title": "Try X",
                                         "priority": "high",
                                         "summary": "test"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            rec = body["recommendation"]
            assert rec["title"] == "Try X"
            assert rec["state"] == "ready"
            assert rec["priority"] == "high"
            rows = await store.list_recommendations()
            assert any(r["title"] == "Try X" for r in rows)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_file_recommendation_rejects_invalid_priority() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            store = LocalStore(tmp.name)
            await store.startup()
            set_write_context(store=store, agent_runner=None, bridges={})
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_file_recommendation",
                           "arguments": {"title": "X",
                                         "priority": "URGENT"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "invalid priority" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_trigger_agent_loop_unknown_returns_error() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            store = LocalStore(tmp.name)
            await store.startup()
            set_write_context(store=store, agent_runner=FakeRunner(), bridges={})
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_trigger_agent_loop",
                           "arguments": {"name": "nope"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "unknown agent loop" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_apply_refuses_non_approved() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            store = LocalStore(tmp.name)
            await store.startup()
            set_write_context(store=store, agent_runner=None,
                              bridges={"southbrook_hermes": FakeBridge()})
            cid = await store.create_mcp_client(name="x", key_hash="h")
            rec = await store.create_recommendation({"title": "X", "state": "ready"})
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_apply_recommendation",
                           "arguments": {"id": rec["id"]}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "only 'approved'" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_apply_approved_pushes_through_bridge() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            bridge = FakeBridge()
            store = LocalStore(tmp.name)
            await store.startup()
            set_write_context(store=store, agent_runner=None,
                              bridges={"southbrook_hermes": bridge})
            cid = await store.create_mcp_client(name="x", key_hash="h")
            rec = await store.create_recommendation({"title": "X", "state": "ready"})
            await store.update_recommendation_state(
                rec["id"], "approved", reviewer_note="ok"
            )
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_apply_recommendation",
                           "arguments": {"id": rec["id"]}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["recommendation"]["state"] == "applied"
            assert bridge.push.await_count == 1
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
