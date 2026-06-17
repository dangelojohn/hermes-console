"""MCP stdio server.

Phase 1 capabilities: tools, resources, prompts (read-only).
Protocol version: 2025-06-18.
Auth: --key <key> on the command line. Verified against mcp_clients on
startup; if no match (or revoked), server exits non-zero before reading stdin.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any, Awaitable, Callable, Dict, Optional

from api.local_store import LocalStore
from api.mcp.auth import verify_key

logger = logging.getLogger("api.mcp.server")

SERVER_NAME = "hermes-mcp"
SERVER_VERSION = "0.1.0"
PROTOCOL_VERSION = "2025-06-18"


class MCPServer:
    def __init__(self, store: LocalStore, client_id: int, client_name: str) -> None:
        self._store = store
        self._client_id = client_id
        self._client_name = client_name
        self._handlers: Dict[str, Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]] = {
            "initialize": self._handle_initialize,
            "tools/list": self._handle_tools_list,
        }

    async def _handle_initialize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "protocolVersion": PROTOCOL_VERSION,
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "capabilities": {
                "tools": {"listChanged": False},
                "resources": {"subscribe": False, "listChanged": False},
                "prompts": {"listChanged": False},
            },
        }

    async def _handle_tools_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Tools are registered in later tasks; for now return empty.
        return {"tools": []}

    async def dispatch(self, message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        method = message.get("method")
        msg_id = message.get("id")
        handler = self._handlers.get(method or "")
        if handler is None:
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32601, "message": f"unknown method: {method}"},
            }
        try:
            result = await handler(message.get("params") or {})
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as exc:  # noqa: BLE001
            logger.exception("mcp dispatch error")
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "error": {"code": -32603, "message": str(exc)[:300]},
            }


async def run_stdio(db_path: str, key: str) -> int:
    store = LocalStore(db_path)
    await store.startup()
    try:
        rows = await store.list_mcp_clients(active_only=True)
        matched = None
        for r in rows:
            if verify_key(key, r["key_hash"]):
                matched = r
                break
        if matched is None:
            print("unauthorized: invalid or revoked key", file=sys.stderr)
            return 1

        server = MCPServer(store, client_id=matched["id"], client_name=matched["name"])
        logger.info("mcp stdio ready client=%s", matched["name"])

        loop = asyncio.get_event_loop()
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        writer_transport, writer_protocol = await loop.connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, loop)

        while True:
            line = await reader.readline()
            if not line:
                break
            try:
                msg = json.loads(line.decode("utf-8"))
            except json.JSONDecodeError:
                continue
            resp = await server.dispatch(msg)
            if resp is not None:
                writer.write((json.dumps(resp) + "\n").encode("utf-8"))
                await writer.drain()
        return 0
    finally:
        await store.shutdown()
