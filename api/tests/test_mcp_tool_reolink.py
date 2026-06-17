"""Tests for the hermes_reolink_* MCP tools."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.reolink import register, set_cameras, build_cameras_from_env


class FakeCamera:
    def __init__(self, name: str = "foyer") -> None:
        self.name = name
        self.get_dev_info = AsyncMock(return_value={
            "name": name, "model": "RLC-810A", "firmware": "v3.1.0",
            "hardware": "v1.0", "serial": "ABC123", "channel_num": 1, "type": "ipc",
        })
        self.get_motion_state = AsyncMock(return_value=True)
        self.get_snapshot_url = AsyncMock(return_value="http://x/snap?token=t")


def _store_and_srv(tmp_path: str):
    async def setup():
        store = LocalStore(tmp_path)
        await store.startup()
        cid = await store.create_mcp_client(name="x", key_hash="h")
        return store, MCPServer(store, client_id=cid, client_name="x")
    return setup


def test_list_cameras_returns_names_only() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_cameras({"foyer": FakeCamera("foyer"),
                          "garage": FakeCamera("garage")})
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_reolink_list_cameras", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["cameras"] == ["foyer", "garage"]
            assert body["count"] == 2
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_get_motion_state_returns_bool() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_cameras({"foyer": FakeCamera()})
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_reolink_get_motion_state",
                           "arguments": {"name": "foyer"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["motion"] is True
            assert body["camera"] == "foyer"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_unknown_camera_returns_error() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_cameras({})
            store, srv = await _store_and_srv(tmp.name)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_reolink_get_device_info",
                           "arguments": {"name": "nope"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "not configured" in body.get("error", "")
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_build_cameras_from_env_parses_json() -> None:
    cams = build_cameras_from_env(
        '[{"name":"foyer","ip":"192.168.68.50","user":"admin","password":"p"}]'
    )
    assert "foyer" in cams
    assert cams["foyer"].name == "foyer"


def test_build_cameras_from_env_drops_invalid_entries() -> None:
    # Missing required fields → entry is silently dropped.
    cams = build_cameras_from_env(
        '[{"name":"ok","ip":"1","user":"u","password":"p"},'
        ' {"name":"missing-creds","ip":"2"}]'
    )
    assert list(cams.keys()) == ["ok"]


def test_build_cameras_from_env_handles_bad_json() -> None:
    assert build_cameras_from_env("not json") == {}
    assert build_cameras_from_env("") == {}
