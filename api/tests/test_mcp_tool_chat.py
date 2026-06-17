"""Tests for hermes_list_chat_threads + hermes_get_chat_messages."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.chat import register, set_store


def test_list_threads_returns_threads() -> None:
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
            await store.create_thread(title="alpha", provider="openai", model="gpt-4o")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_list_chat_threads", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert any(t["title"] == "alpha" for t in body["threads"])
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_get_chat_messages_for_nonexistent_returns_empty() -> None:
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
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "hermes_get_chat_messages",
                           "arguments": {"thread_id": 999}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["messages"] == []
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
