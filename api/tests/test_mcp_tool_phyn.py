"""Tests for the hermes_phyn_* MCP tools (HA-backed)."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.phyn import register, set_phyn_context


class FakeHA:
    def __init__(self) -> None:
        # Three phyn entities + one non-phyn that should NOT show up.
        all_entities = [
            {"entity_id": "sensor.phyn_current_flow_rate", "state": "0.0",
             "friendly_name": "Phyn flow rate", "unit_of_measurement": "gal/min"},
            {"entity_id": "sensor.phyn_water_pressure", "state": "62",
             "friendly_name": "Phyn pressure", "unit_of_measurement": "psi"},
            {"entity_id": "binary_sensor.phyn_leak", "state": "on",
             "friendly_name": "Phyn leak", "device_class": "moisture"},
            {"entity_id": "light.kitchen", "state": "off",
             "friendly_name": "Kitchen light"},
        ]
        async def _list(*, domain_filter=None, name_filter=None):
            out = list(all_entities)
            if name_filter:
                nf = name_filter.lower()
                out = [e for e in out
                        if nf in e["entity_id"].lower()
                            or nf in e.get("friendly_name", "").lower()]
            return out
        self.list_entities = _list


def _store_and_srv(tmp_path: str):
    async def setup():
        store = LocalStore(tmp_path)
        await store.startup()
        cid = await store.create_mcp_client(name="x", key_hash="h")
        return store, MCPServer(store, client_id=cid, client_name="x")
    return setup


def test_discover_returns_only_phyn_entities() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_phyn_context(bridge=FakeHA())
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_phyn_discover", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            ids = [e["entity_id"] for e in body["entities"]]
            assert "sensor.phyn_current_flow_rate" in ids
            assert "light.kitchen" not in ids
            assert body["hint"] == "phyn"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_snapshot_highlights_leak_signals() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_phyn_context(bridge=FakeHA())
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_phyn_snapshot", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["count"] == 3
            assert len(body["active_leak_signals"]) == 1
            assert (body["active_leak_signals"][0]["entity_id"]
                     == "binary_sensor.phyn_leak")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_no_bridge_returns_helpful_error() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_phyn_context(bridge=None)
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_phyn_snapshot", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "Home Assistant" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
