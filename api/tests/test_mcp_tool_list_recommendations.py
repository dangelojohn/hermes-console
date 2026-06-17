"""Tests for hermes_list_recommendations + hermes_get_recommendation."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.recommendations import register, set_store


def test_list_recommendations_filters_by_state() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            store = LocalStore(tmp.name)
            await store.startup()
            set_store(store)
            cid = await store.create_mcp_client(name="x", key_hash="h")
            await store.create_recommendation({"title": "A", "state": "ready"})
            await store.create_recommendation({"title": "B", "state": "applied"})
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_list_recommendations",
                           "arguments": {"state": "ready"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            titles = [r["title"] for r in body["recommendations"]]
            assert titles == ["A"]
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_get_recommendation_by_id() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            store = LocalStore(tmp.name)
            await store.startup()
            set_store(store)
            cid = await store.create_mcp_client(name="x", key_hash="h")
            await store.create_recommendation({"title": "X", "state": "ready"})
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "hermes_get_recommendation",
                           "arguments": {"id": 1}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["recommendation"]["title"] == "X"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
