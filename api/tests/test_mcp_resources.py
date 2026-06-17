"""Tests for resources/list + resources/read."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.resources import set_resources_context

FIXTURES = Path(__file__).parent / "fixtures"


def test_resources_list_includes_skills_and_audit() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            store = LocalStore(tmp.name)
            await store.startup()
            set_resources_context(store=store, skills_root=str(FIXTURES))
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "resources/list", "params": {},
            })
            uris = [r["uri"] for r in resp["result"]["resources"]]
            assert any(u.startswith("hermes://skills/") for u in uris)
            assert any(u == "hermes://audit/today" for u in uris)
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_resources_read_skill_md() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            store = LocalStore(tmp.name)
            await store.startup()
            set_resources_context(store=store, skills_root=str(FIXTURES))
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "resources/read",
                "params": {"uri": "hermes://skills/skill-fixture-ok/SKILL.md"},
            })
            contents = resp["result"]["contents"]
            assert "Skill Fixture OK" in contents[0]["text"]
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_resources_read_audit_today() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            store = LocalStore(tmp.name)
            await store.startup()
            set_resources_context(store=store, skills_root=str(FIXTURES))
            cid = await store.create_mcp_client(name="x", key_hash="h")
            await store.log_mcp_call(
                client_id=cid, tool_name="hermes_list_recommendations",
                args_redacted={"state": "ready"}, outcome="ok",
                error_text=None, duration_ms=3,
            )
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 3, "method": "resources/read",
                "params": {"uri": "hermes://audit/today"},
            })
            body = json.loads(resp["result"]["contents"][0]["text"])
            assert body["count"] >= 1
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
