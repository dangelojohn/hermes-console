"""Hermes as an MCP client — Phase 3.

Lets Hermes connect to upstream MCP servers (Cloudflare's hosted MCPs,
product-graph-mcp on the QNAP, anything else speaking MCP) and re-export
their tools under a namespace prefix to Hermes's own MCP clients.

The point: a single Hermes-side authenticated session gives Claude Code +
Codex access to upstream tools without each agent managing the upstream's
auth separately. Every call still lands in Hermes's audit log, so "what
did the agents do this week" stays answerable in one place.

Transport: streamable-http (Cloudflare-style). Other transports can be
added by extending ``UpstreamConfig.transport``.

Auth: per-upstream, passed as a header dict. Cloudflare's hosted MCPs
accept ``Authorization: Bearer <cloudflare-api-token>`` — same token the
direct hermes_cloudflare_* tools use, so a single ``.env`` value covers
both surfaces.

This module is INTENTIONALLY minimal. It owns:
  - One ``UpstreamMCPClient`` per upstream (long-lived inside the hermes-api process)
  - A ``register_upstream_as_tools()`` helper that proxies each upstream tool
    under ``<prefix>__<original_name>`` (double-underscore separator keeps
    tool names valid identifiers for downstream clients that care).
  - A reset/shutdown hook for tests.

It does NOT own resource or prompt re-export — Phase 3 v1 is tool-only.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("api.mcp.clients.upstream_mcp")


@dataclass
class UpstreamConfig:
    name: str
    url: str
    prefix: str
    headers: Optional[Dict[str, str]] = None
    transport: str = "streamable-http"


class UpstreamMCPClient:
    """One long-lived connector to an upstream MCP server.

    Phase 3 v1 implementation: a thin httpx-based JSON-RPC bridge.

    We deliberately do NOT take a dependency on the official ``mcp`` SDK's
    client module here — the surface we need is small (initialize, tools/list,
    tools/call) and the SDK's client API has churned across releases. A
    minimal in-house implementation keeps us off that treadmill and lets us
    test against a fake upstream without spinning up subprocess + transport
    machinery in CI.
    """

    def __init__(self, cfg: UpstreamConfig) -> None:
        self._cfg = cfg
        self._client: Optional[httpx.AsyncClient] = None
        self._next_id = 1
        self._lock = asyncio.Lock()

    @property
    def name(self) -> str:
        return self._cfg.name

    @property
    def prefix(self) -> str:
        return self._cfg.prefix

    async def startup(self) -> None:
        if self._client is None:
            headers = {"Content-Type": "application/json",
                       "Accept": "application/json, text/event-stream"}
            if self._cfg.headers:
                headers.update(self._cfg.headers)
            self._client = httpx.AsyncClient(
                base_url=self._cfg.url,
                timeout=httpx.Timeout(30.0, connect=10.0),
                headers=headers,
            )
            # Best-effort initialize — log a warning on failure so tools/list
            # still gets called (some upstreams accept tools/list without an
            # explicit initialize handshake when no session state is needed).
            try:
                await self._rpc("initialize", {
                    "protocolVersion": "2025-06-18",
                    "clientInfo": {"name": "hermes-mcp",
                                   "version": "0.1.0-upstream-client"},
                    "capabilities": {},
                })
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "upstream %s initialize failed (%s) — continuing optimistically",
                    self._cfg.name, exc,
                )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _rpc(
        self, method: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        async with self._lock:
            assert self._client is not None, "upstream client not started"
            msg_id = self._next_id
            self._next_id += 1
            body = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "method": method,
                "params": params,
            }
            resp = await self._client.post("", json=body)
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"upstream {self._cfg.name} {method} "
                    f"http {resp.status_code}: {resp.text[:200]}"
                )
            data = _parse_streamable_http_body(resp)
            if data is None:
                raise RuntimeError(
                    f"upstream {self._cfg.name} non-json: {resp.text[:200]}"
                )
            if "error" in data:
                raise RuntimeError(
                    f"upstream {self._cfg.name} jsonrpc error: {data['error']}"
                )
            return data.get("result") or {}

    async def list_tools(self) -> List[Dict[str, Any]]:
        result = await self._rpc("tools/list", {})
        return result.get("tools") or []


def _parse_streamable_http_body(resp: httpx.Response) -> Optional[Dict[str, Any]]:
    """Return the JSON-RPC body from a streamable-http MCP response.

    The MCP streamable-http transport returns responses as Server-Sent Events
    with content-type ``text/event-stream``; each event is an ``event: message
    \\ndata: <json>`` block. Single request/response calls (as used by
    initialize / tools/list / tools/call without progress events) come back
    with exactly ONE such block. Some upstreams (smaller, simpler servers)
    return raw JSON instead.

    We accept both. For SSE we parse the FIRST ``data:`` line and stop.
    """
    import json as _json
    ctype = (resp.headers.get("content-type") or "").lower()
    if "text/event-stream" in ctype:
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                payload = line[len("data:"):].strip()
                try:
                    return _json.loads(payload)
                except _json.JSONDecodeError:
                    return None
        return None
    try:
        return resp.json()
    except ValueError:
        return None

    async def call_tool(
        self, name: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        return await self._rpc(
            "tools/call",
            {"name": name, "arguments": arguments},
        )


# ---------------------------------------------------------------------------
# Registration glue — turn an upstream's tool list into local MCP tools.
# ---------------------------------------------------------------------------


_UPSTREAMS: Dict[str, UpstreamMCPClient] = {}


def _registered_upstreams() -> Dict[str, UpstreamMCPClient]:
    return _UPSTREAMS


def reset_upstreams_for_tests() -> None:
    _UPSTREAMS.clear()


async def register_upstream_as_tools(
    cfg: UpstreamConfig, *, tool_registrar: Any
) -> int:
    """Connect to ``cfg.url``, list its tools, and register each one as a
    Hermes-side MCP tool named ``<prefix>__<original_name>``.

    Returns the count of tools registered. Callers pass ``tool_registrar``
    as the ``api.mcp.tools.register_tool`` callable plus the ``ToolSpec``
    constructor — exact import is deferred so this module doesn't pull
    api.mcp.tools at top level (keeps the registry global cleanly owned by
    api.mcp.tools/__init__.py).

    Errors are logged and the upstream is skipped — Hermes stays up if
    Cloudflare's hosted MCP is down.
    """
    client = UpstreamMCPClient(cfg)
    try:
        await client.startup()
        upstream_tools = await client.list_tools()
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "upstream %s registration skipped: %s", cfg.name, exc
        )
        await client.shutdown()
        return 0
    _UPSTREAMS[cfg.name] = client

    register_tool = tool_registrar["register_tool"]
    ToolSpec = tool_registrar["ToolSpec"]

    count = 0
    for ut in upstream_tools:
        original_name = ut.get("name") or ""
        if not original_name:
            continue
        wrapped_name = f"{cfg.prefix}__{original_name}"

        # Each iteration must bind its own client + tool name in the closure.
        def _make_handler(_client: UpstreamMCPClient, _orig: str):
            async def _handler(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
                try:
                    raw = await _client.call_tool(_orig, args)
                except Exception as exc:  # noqa: BLE001
                    return {"error": f"upstream {_client.name}: {exc}"}
                return {"upstream_result": raw}
            return _handler

        register_tool(ToolSpec(
            name=wrapped_name,
            description=(
                f"[via upstream MCP '{cfg.name}'] "
                + (ut.get("description") or "(no description)")
            ),
            input_schema=ut.get("inputSchema") or {"type": "object"},
            handler=_make_handler(client, original_name),
        ))
        count += 1

    logger.info(
        "upstream %s registered %d tools under prefix '%s'",
        cfg.name, count, cfg.prefix,
    )
    return count


async def shutdown_all_upstreams() -> None:
    for client in list(_UPSTREAMS.values()):
        with contextlib.suppress(Exception):
            await client.shutdown()
    _UPSTREAMS.clear()
