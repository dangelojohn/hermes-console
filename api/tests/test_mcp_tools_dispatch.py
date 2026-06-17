"""Tools/call dispatches to the right handler + audits + returns content."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import register_tool, reset_registry_for_tests, ToolSpec


def test_tools_call_unknown_returns_error() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "no_such_tool", "arguments": {}},
            })
            assert resp is not None
            assert "error" in resp
            assert "no_such_tool" in resp["error"]["message"]
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_tools_list_returns_registered_tools() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")

            async def echo(ctx, args):
                return {"echoed": args}

            register_tool(ToolSpec(
                name="test_echo",
                description="Echoes back the args.",
                input_schema={"type": "object"},
                handler=echo,
            ))
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
            })
            names = [t["name"] for t in resp["result"]["tools"]]
            assert "test_echo" in names
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_tools_call_audits_and_returns_content() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")

            async def echo(ctx, args):
                return {"echoed": args}

            register_tool(ToolSpec(
                name="test_echo",
                description="Echoes back the args.",
                input_schema={"type": "object"},
                handler=echo,
            ))
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "test_echo", "arguments": {"hi": 1}},
            })
            content = resp["result"]["content"]
            assert content[0]["type"] == "text"
            assert "echoed" in content[0]["text"]

            rows = await store.list_mcp_calls(since_hours=1)
            assert any(r["tool_name"] == "test_echo" and r["outcome"] == "ok" for r in rows)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
