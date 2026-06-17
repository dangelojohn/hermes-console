"""Tests for the hermes_ha_* MCP tools."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.home_assistant import register, set_ha_context


class FakeHA:
    """Stand-in for HomeAssistantBridge."""
    def __init__(self) -> None:
        self._context_entities = [
            "climate.ecobee",
            "sensor.ecobee_temperature",
        ]
        self.fetch_context = AsyncMock(return_value={
            "climate.ecobee": {"state": "heat",
                                "attributes": {"current_temperature": 21,
                                                "temperature": 21.5}},
            "sensor.ecobee_temperature": {"state": "21.1", "attributes": {}},
        })
        self.list_entities = AsyncMock(return_value=[
            {"entity_id": "climate.ecobee", "state": "heat",
             "friendly_name": "Ecobee"},
            {"entity_id": "light.kitchen", "state": "on",
             "friendly_name": "Kitchen"},
            {"entity_id": "sensor.omada_signal", "state": "-58",
             "friendly_name": "Omada AP signal"},
        ])
        self.call_service = AsyncMock(return_value={
            "ok": True, "service": "climate.set_temperature",
            "result": [],
        })


def _store_and_srv(tmp_path: str):
    async def setup():
        store = LocalStore(tmp_path)
        await store.startup()
        cid = await store.create_mcp_client(name="x", key_hash="h")
        return store, MCPServer(store, client_id=cid, client_name="x")
    return setup


def test_list_entities_returns_all() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_ha_context(bridge=FakeHA(), allowed_services=[])
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_ha_list_entities", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["count"] == 3
            assert any(e["entity_id"] == "climate.ecobee" for e in body["entities"])
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_get_context_returns_allowlist() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_ha_context(bridge=FakeHA(), allowed_services=[])
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_ha_get_context", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "climate.ecobee" in body["context"]
            assert body["context"]["climate.ecobee"]["state"] == "heat"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_get_state_refuses_non_allowlisted_entity() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_ha_context(bridge=FakeHA(), allowed_services=[])
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_ha_get_state",
                           "arguments": {"entity_id": "light.kitchen"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "allowlist" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_call_service_denied_when_allowlist_empty() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_ha_context(bridge=FakeHA(), allowed_services=[])
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_ha_call_service",
                           "arguments": {"domain": "climate",
                                          "service": "set_temperature",
                                          "data": {"entity_id": "climate.ecobee",
                                                    "temperature": 21}}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "disabled" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_call_service_allowed_through_allowlist() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            ha = FakeHA()
            set_ha_context(bridge=ha,
                            allowed_services=["climate.set_temperature"])
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_ha_call_service",
                           "arguments": {"domain": "climate",
                                          "service": "set_temperature",
                                          "data": {"entity_id": "climate.ecobee",
                                                    "temperature": 21}}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body.get("ok") is True or "ok" in body
            assert ha.call_service.await_count == 1
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
