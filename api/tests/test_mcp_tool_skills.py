"""Tests for hermes_list_skills + hermes_run_skill."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.skills import register, set_skills_root

FIXTURES = Path(__file__).parent / "fixtures"


def test_list_skills_returns_only_read_only() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_skills_root(str(FIXTURES))
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_list_skills", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            names = [s["name"] for s in body["skills"]]
            assert "skill-fixture-ok" in names
            assert "skill-fixture-destructive" not in names
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_run_skill_returns_markdown() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_skills_root(str(FIXTURES))
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "hermes_run_skill",
                           "arguments": {"name": "skill-fixture-ok"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "Skill Fixture OK" in body["skill_markdown"]
            assert body["metadata"]["name"] == "skill-fixture-ok"
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_run_skill_rejects_destructive() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            register()
            set_skills_root(str(FIXTURES))
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "hermes_run_skill",
                           "arguments": {"name": "skill-fixture-destructive"}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert "destructive" in body.get("error", "").lower()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
