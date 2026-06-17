"""Tests for hermes_get_tenant_status."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.bridges import register, set_bridges


class FakeBridge:
    def __init__(self, status: str = "ok") -> None:
        self.health = AsyncMock(return_value=status)


def test_tenant_status_returns_health_per_bridge() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_bridges({"southbrook_hermes": FakeBridge("ok"),
                         "home_assistant": FakeBridge("unreachable")})
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_get_tenant_status", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["bridges"]["southbrook_hermes"] == "ok"
            assert body["bridges"]["home_assistant"] == "unreachable"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
