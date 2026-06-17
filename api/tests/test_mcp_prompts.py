"""Tests for prompts/list + prompts/get."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.prompts import set_prompts_context

FIXTURES = Path(__file__).parent / "fixtures"


def test_prompts_list_includes_review_queue_and_per_skill() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            store = LocalStore(tmp.name)
            await store.startup()
            set_prompts_context(skills_root=str(FIXTURES))
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "prompts/list", "params": {},
            })
            names = [p["name"] for p in resp["result"]["prompts"]]
            assert "review-queue" in names
            assert "use-skill/skill-fixture-ok" in names
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_prompt_get_review_queue() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            reset_registry_for_tests()
            store = LocalStore(tmp.name)
            await store.startup()
            set_prompts_context(skills_root=str(FIXTURES))
            cid = await store.create_mcp_client(name="x", key_hash="h")
            srv = MCPServer(store, client_id=cid, client_name="x")
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "prompts/get",
                "params": {"name": "review-queue", "arguments": {}},
            })
            messages = resp["result"]["messages"]
            assert messages[0]["role"] == "user"
            assert "review" in messages[0]["content"]["text"].lower()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
