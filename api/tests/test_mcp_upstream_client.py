"""Tests for the upstream MCP client + re-export glue (Phase 3)."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from api.local_store import LocalStore
from api.mcp.clients.upstream_mcp import (
    UpstreamConfig,
    UpstreamMCPClient,
    register_upstream_as_tools,
    reset_upstreams_for_tests,
)
from api.mcp.server import MCPServer
from api.mcp.tools import ToolSpec, register_tool, reset_registry_for_tests


class FakeRespondingTransport:
    """Stub httpx-style transport that returns fixed JSON-RPC responses."""
    def __init__(self) -> None:
        self.calls = []

    async def post(self, *args, **kwargs):
        body = kwargs.get("json") or {}
        self.calls.append(body)
        method = body.get("method")
        msg_id = body.get("id")
        if method == "initialize":
            result = {"protocolVersion": "2025-06-18",
                      "serverInfo": {"name": "fake-upstream", "version": "0"},
                      "capabilities": {"tools": {}}}
        elif method == "tools/list":
            result = {"tools": [{
                "name": "search",
                "description": "Search the upstream's documentation.",
                "inputSchema": {"type": "object",
                                 "properties": {"q": {"type": "string"}}}
            }]}
        elif method == "tools/call":
            params = body.get("params") or {}
            result = {"echoed_args": params.get("arguments"),
                      "tool": params.get("name")}
        else:
            return _FakeResp({"jsonrpc": "2.0", "id": msg_id,
                              "error": {"code": -32601, "message": "unknown"}})
        return _FakeResp({"jsonrpc": "2.0", "id": msg_id, "result": result})

    async def aclose(self) -> None:
        pass


class _FakeResp:
    def __init__(self, body: dict) -> None:
        self._body = body
        self.status_code = 200
        self.text = json.dumps(body)
        self.headers = {"content-type": "application/json"}

    def json(self) -> dict:
        return self._body


def test_upstream_tools_appear_under_prefix() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            reset_upstreams_for_tests()
            cfg = UpstreamConfig(
                name="fake-docs",
                url="http://fake.test/mcp",
                prefix="cf_docs",
            )
            uc = UpstreamMCPClient(cfg)
            uc._client = FakeRespondingTransport()  # type: ignore[assignment]
            uc._next_id = 1

            # Run register_upstream_as_tools manually using our fake client
            # (skip the real network startup).
            tools = await uc.list_tools()
            assert len(tools) == 1

            for ut in tools:
                wrapped_name = f"{cfg.prefix}__{ut['name']}"

                def _make(_client, _orig):
                    async def _h(ctx, args):
                        try:
                            raw = await _client.call_tool(_orig, args)
                        except Exception as exc:
                            return {"error": str(exc)}
                        return {"upstream_result": raw}
                    return _h

                register_tool(ToolSpec(
                    name=wrapped_name,
                    description=f"[via upstream MCP '{cfg.name}'] "
                                + (ut.get("description") or ""),
                    input_schema=ut.get("inputSchema") or {"type": "object"},
                    handler=_make(uc, ut["name"]),
                ))

            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {},
            })
            names = [t["name"] for t in resp["result"]["tools"]]
            assert "cf_docs__search" in names

            # Now call the wrapped tool and confirm the upstream got called
            # with the right name + args.
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "cf_docs__search",
                           "arguments": {"q": "tunnels"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["upstream_result"]["echoed_args"] == {"q": "tunnels"}
            assert body["upstream_result"]["tool"] == "search"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_upstream_errors_surface_cleanly() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            reset_upstreams_for_tests()

            class BrokenTransport(FakeRespondingTransport):
                async def post(self, *args, **kwargs):
                    body = kwargs.get("json") or {}
                    return _FakeResp({"jsonrpc": "2.0", "id": body.get("id"),
                                       "error": {"code": -32000,
                                                  "message": "upstream blew up"}})

            cfg = UpstreamConfig(name="broken", url="http://x/mcp", prefix="b")
            uc = UpstreamMCPClient(cfg)
            uc._client = BrokenTransport()  # type: ignore[assignment]

            async def call_via_handler():
                async def _h(ctx, args):
                    try:
                        return {"upstream_result": await uc.call_tool("anything", args)}
                    except Exception as exc:
                        return {"error": str(exc)}
                register_tool(ToolSpec(
                    name="b__anything",
                    description="",
                    input_schema={"type": "object"},
                    handler=_h,
                ))

            await call_via_handler()
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "b__anything", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "upstream blew up" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
