"""Tests for hermes_cloudflare_* tools.

Mocks the Cloudflare REST API so no real account or token is touched.
"""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.cloudflare import register, set_cloudflare_client


class FakeCFClient:
    """Stand-in for CloudflareClient that returns canned data."""
    def __init__(self) -> None:
        self.list_zones = AsyncMock(return_value=[
            {"id": "zone1", "name": "odooiq.com", "status": "active",
             "plan": "Free", "name_servers": ["ns1", "ns2"]},
        ])
        self.list_dns_records = AsyncMock(return_value=[
            {"id": "rec1", "type": "A", "name": "hermes.odooiq.com",
             "content": "1.2.3.4", "proxied": True, "ttl": 1, "comment": None},
        ])
        self.get_tunnel = AsyncMock(return_value={
            "id": "tunnel1", "name": "qnap-odooiq", "status": "healthy",
            "connections": [], "ingress": [
                {"hostname": "hermes.odooiq.com",
                 "service": "http://localhost:9080", "path": None},
            ], "ingress_count": 1,
        })
        self.list_access_apps = AsyncMock(return_value=[
            {"id": "app1", "name": "QNAP Admin", "type": "self_hosted",
             "domain": "qnap.odooiq.com", "policies_count": 1},
        ])


def test_list_zones_returns_zones() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_cloudflare_client(FakeCFClient())
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_cloudflare_list_zones",
                           "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["count"] == 1
            assert body["zones"][0]["name"] == "odooiq.com"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_list_dns_records_requires_zone_id() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_cloudflare_client(FakeCFClient())
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "hermes_cloudflare_list_dns_records",
                           "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "missing" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_get_tunnel_returns_ingress() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_cloudflare_client(FakeCFClient())
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "hermes_cloudflare_get_tunnel",
                           "arguments": {"tunnel_id": "tunnel1"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["tunnel"]["name"] == "qnap-odooiq"
            assert body["tunnel"]["ingress_count"] == 1
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_tools_without_client_return_error() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_cloudflare_client(None)
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "hermes_cloudflare_list_zones",
                           "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "not configured" in body.get("error", "").lower()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
