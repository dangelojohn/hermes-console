"""Tests for hermes_get_provider_health."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.providers import register, set_provider_registry


class FakeRegistry:
    def __init__(self) -> None:
        self.health = AsyncMock(return_value={
            "openai": "ok",
            "hermes_harness": "disabled",
            "anthropic": "ok",
        })


def test_provider_health() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_provider_registry(FakeRegistry())
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_get_provider_health", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["llm"]["openai"] == "ok"
            assert body["llm"]["anthropic"] == "ok"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
