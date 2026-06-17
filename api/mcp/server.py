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
            "tools/call": self._handle_tools_call,
            "resources/list": self._handle_resources_list,
            "resources/read": self._handle_resources_read,
            "prompts/list": self._handle_prompts_list,
            "prompts/get": self._handle_prompts_get,
        }
        from api.mcp.tools import list_tools as _list_tools, call_tool as _call_tool
        self._list_tools = _list_tools
        self._call_tool = _call_tool

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
        return {"tools": self._list_tools()}

    async def _handle_tools_call(self, params: Dict[str, Any]) -> Dict[str, Any]:
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not name:
            raise ValueError("tools/call requires 'name'")
        return await self._call_tool(
            self._store, client_id=self._client_id,
            tool_name=name, arguments=arguments,
        )

    async def _handle_resources_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from api.mcp.resources import list_resources
        return {"resources": await list_resources()}

    async def _handle_resources_read(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from api.mcp.resources import read_resource
        uri = params.get("uri")
        if not uri:
            raise ValueError("resources/read requires 'uri'")
        return await read_resource(uri)

    async def _handle_prompts_list(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from api.mcp.prompts import list_prompts
        return {"prompts": await list_prompts()}

    async def _handle_prompts_get(self, params: Dict[str, Any]) -> Dict[str, Any]:
        from api.mcp.prompts import get_prompt
        name = params.get("name")
        if not name:
            raise ValueError("prompts/get requires 'name'")
        return await get_prompt(name, params.get("arguments") or {})

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

        # ---- Phase 1 tool + resource + prompt registration ----
        # Each tool module declares its own register()/set_*() helpers; we
        # plug the store + skill root + provider registry + bridges in here
        # so the registered handlers have everything they need at call time.
        import os as _os
        from api.mcp.tools.recommendations import (
            register as _reg_recs, set_store as _set_recs_store,
        )
        from api.mcp.tools.chat import (
            register as _reg_chat, set_store as _set_chat_store,
        )
        from api.mcp.tools.bridges import (
            register as _reg_bridges, set_bridges as _set_bridges,
        )
        from api.mcp.tools.providers import (
            register as _reg_providers, set_provider_registry as _set_providers,
        )
        from api.mcp.tools.skills import (
            register as _reg_skills, set_skills_root as _set_skills_root,
        )
        from api.mcp.resources import set_resources_context as _set_res_ctx
        from api.mcp.prompts import set_prompts_context as _set_prompts_ctx

        _reg_recs(); _set_recs_store(store)
        _reg_chat(); _set_chat_store(store)

        # Bridges + provider registry are constructed exactly the same way
        # the main FastAPI lifespan does it. Tolerant of import/init errors —
        # the corresponding tools will report "registry not configured"
        # rather than failing the whole MCP session.
        try:
            from api.main import _build_bridges
            from api.models import Settings
            settings = Settings()  # type: ignore[call-arg]
            bridges = _build_bridges(settings)
            for b in bridges.values():
                await b.startup()
            _reg_bridges(); _set_bridges(bridges)
        except Exception as exc:  # noqa: BLE001
            logger.warning("mcp: bridges init skipped (%s)", exc)
            _reg_bridges(); _set_bridges({})

        try:
            from api.llm import ProviderRegistry
            registry = ProviderRegistry.from_settings(settings)  # type: ignore[name-defined]
            await registry.startup()
            _reg_providers(); _set_providers(registry)
        except Exception as exc:  # noqa: BLE001
            logger.warning("mcp: provider registry init skipped (%s)", exc)
            _reg_providers(); _set_providers(None)

        skills_root = _os.environ.get(
            "HERMES_SKILLS_ROOT", "/app/custom-hermes-skills/skills",
        )
        _reg_skills(); _set_skills_root(skills_root)
        _set_res_ctx(store=store, skills_root=skills_root)
        _set_prompts_ctx(skills_root=skills_root)

        # ---- Phase 3 Option C: Hermes-as-MCP-client of upstream servers ----
        # Each upstream MCP server's tools are re-exported under a namespace
        # prefix. Built-in upstream catalog: cloudflare-docs (public, no auth).
        # More can be added via the HERMES_UPSTREAM_MCP_SERVERS env var
        # (comma-separated "name=url:prefix" tuples; future enhancement).
        try:
            from api.mcp.clients.upstream_mcp import (
                UpstreamConfig as _UpstreamConfig,
                register_upstream_as_tools as _register_upstream,
            )
            from api.mcp.tools import register_tool as _rt, ToolSpec as _TS
            registrar = {"register_tool": _rt, "ToolSpec": _TS}

            cf_token = _os.environ.get("CLOUDFLARE_API_TOKEN", "")
            upstreams_to_try = [
                _UpstreamConfig(
                    name="cloudflare-docs",
                    url="https://docs.mcp.cloudflare.com/mcp",
                    prefix="cf_docs",
                    headers=(
                        {"Authorization": f"Bearer {cf_token}"} if cf_token else None
                    ),
                ),
            ]
            for cfg in upstreams_to_try:
                try:
                    n = await _register_upstream(cfg, tool_registrar=registrar)
                    logger.info("upstream %s: %d tools registered", cfg.name, n)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("upstream %s skipped: %s", cfg.name, exc)
        except Exception as exc:  # noqa: BLE001
            logger.warning("mcp: upstream init failed (%s)", exc)

        # ---- Cloudflare tools (Phase 2 Option B) ----
        # Only registered when CLOUDFLARE_API_TOKEN is set. Tools degrade
        # gracefully when the client isn't configured.
        try:
            from api.mcp.tools.cloudflare import (
                register as _reg_cf, set_cloudflare_client as _set_cf,
            )
            from api.mcp.clients.cloudflare import CloudflareClient
            _reg_cf()
            cf_token = _os.environ.get("CLOUDFLARE_API_TOKEN", "")
            if cf_token:
                cf_client = CloudflareClient(
                    api_token=cf_token,
                    account_id=_os.environ.get("CLOUDFLARE_ACCOUNT_ID") or None,
                )
                await cf_client.startup()
                _set_cf(cf_client)
                logger.info("mcp: cloudflare client ready")
            else:
                _set_cf(None)
                logger.info("mcp: CLOUDFLARE_API_TOKEN not set — "
                            "hermes_cloudflare_* tools will return 'not configured'")
        except Exception as exc:  # noqa: BLE001
            logger.warning("mcp: cloudflare init skipped (%s)", exc)

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
