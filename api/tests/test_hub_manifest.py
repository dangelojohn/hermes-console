"""Tests for the HubStore persistence + the hermes_hub_* MCP tools."""
from __future__ import annotations

import asyncio
import json
import tempfile
from pathlib import Path

from api.hub_manifest import HubStore, MANIFEST_VERSION
from api.local_store import LocalStore
from api.mcp.server import MCPServer
from api.mcp.tools import reset_registry_for_tests
from api.mcp.tools.hub import register, set_hub_store


def _tmp(suffix=".json"):
    f = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    f.close()
    Path(f.name).unlink(missing_ok=True)
    return f.name


def test_seed_creates_manifest_with_expected_categories() -> None:
    async def _run() -> None:
        path = _tmp()
        try:
            store = HubStore(path=path)
            await store.startup()
            m = await store.read()
            assert m["version"] == MANIFEST_VERSION
            assert m["webmaster"] == "Hermes Console"
            ids = sorted(c["id"] for c in m["categories"])
            for required in ("hermes", "odoo", "home_automation",
                              "network", "code", "qnap", "docs"):
                assert required in ids, f"category {required!r} missing from seed"
            # forgejo link present in code category
            code_cat = next(c for c in m["categories"] if c["id"] == "code")
            forgejo_names = [l["name"] for l in code_cat["links"]
                              if "forgejo" in l["name"].lower()]
            assert forgejo_names, "Forgejo link missing from seed"
        finally:
            Path(path).unlink(missing_ok=True)

    asyncio.run(_run())


def test_add_link_and_persists_to_disk() -> None:
    async def _run() -> None:
        path = _tmp()
        try:
            store = HubStore(path=path)
            await store.startup()
            link = await store.add_link(
                category_id="hermes", name="X", url="https://x.test/",
                description="d", tags=["foo"],
            )
            assert link["name"] == "X"
            assert link["id"] and len(link["id"]) == 12

            # Re-read from disk to confirm persistence.
            on_disk = json.loads(Path(path).read_text())
            hermes_cat = next(c for c in on_disk["categories"]
                                if c["id"] == "hermes")
            new_names = [l["name"] for l in hermes_cat["links"]]
            assert "X" in new_names
            assert on_disk["last_change"]["who"] == "hermes"
        finally:
            Path(path).unlink(missing_ok=True)

    asyncio.run(_run())


def test_update_and_remove_link() -> None:
    async def _run() -> None:
        path = _tmp()
        try:
            store = HubStore(path=path)
            await store.startup()
            link = await store.add_link(
                category_id="docs", name="A", url="https://a/",
            )
            updated = await store.update_link(
                link_id=link["id"], fields={"description": "renamed"},
            )
            assert updated["description"] == "renamed"

            ok = await store.remove_link(link_id=link["id"])
            assert ok is True

            m = await store.read()
            ids = [l["id"] for c in m["categories"] for l in c["links"]]
            assert link["id"] not in ids
        finally:
            Path(path).unlink(missing_ok=True)

    asyncio.run(_run())


def test_replace_validates() -> None:
    async def _run() -> None:
        path = _tmp()
        try:
            store = HubStore(path=path)
            await store.startup()
            bad = {"not": "valid"}
            try:
                await store.replace(bad)
                assert False, "expected ValueError"
            except ValueError:
                pass

            good = {"categories": [{"id": "x", "name": "X", "links": []}]}
            res = await store.replace(good)
            assert any(c["id"] == "x" for c in res["categories"])
        finally:
            Path(path).unlink(missing_ok=True)

    asyncio.run(_run())


def _setup_mcp(tmp_sqlite, hub_path):
    async def go():
        sstore = LocalStore(tmp_sqlite)
        await sstore.startup()
        hub = HubStore(path=hub_path)
        await hub.startup()
        reset_registry_for_tests()
        register()
        set_hub_store(hub)
        cid = await sstore.create_mcp_client(name="x", key_hash="h")
        return sstore, hub, MCPServer(sstore, client_id=cid, client_name="x")
    return go


def test_mcp_list_links_returns_seed_inventory() -> None:
    async def _run() -> None:
        sqlite = _tmp(".sqlite")
        hub_path = _tmp()
        try:
            _, _, srv = await _setup_mcp(sqlite, hub_path)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_hub_list_links", "arguments": {}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["count"] >= 10  # seed has 30+ links
            cat_ids = [c["id"] for c in body["categories"]]
            for r in ("hermes", "odoo", "home_automation", "network",
                       "code", "qnap", "docs"):
                assert r in cat_ids
        finally:
            for p in (sqlite, hub_path):
                Path(p).unlink(missing_ok=True)

    asyncio.run(_run())


def test_mcp_add_and_remove_link_roundtrip() -> None:
    async def _run() -> None:
        sqlite = _tmp(".sqlite")
        hub_path = _tmp()
        try:
            _, _, srv = await _setup_mcp(sqlite, hub_path)()
            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_hub_add_link", "arguments": {
                    "category_id": "qnap",
                    "name": "Test Endpoint",
                    "url": "https://t.test/",
                    "description": "smoke",
                    "tags": ["test"],
                }},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["ok"] is True
            new_id = body["link"]["id"]

            resp = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "hermes_hub_remove_link",
                            "arguments": {"id": new_id}},
            })
            body = json.loads(resp["result"]["content"][0]["text"])
            assert body["ok"] is True
        finally:
            for p in (sqlite, hub_path):
                Path(p).unlink(missing_ok=True)

    asyncio.run(_run())


def test_mcp_update_link_partial_fields() -> None:
    async def _run() -> None:
        sqlite = _tmp(".sqlite")
        hub_path = _tmp()
        try:
            _, _, srv = await _setup_mcp(sqlite, hub_path)()
            # Add a link first
            add = await srv.dispatch({
                "jsonrpc": "2.0", "id": 1, "method": "tools/call",
                "params": {"name": "hermes_hub_add_link", "arguments": {
                    "category_id": "docs", "name": "doc",
                    "url": "https://d.test/",
                }},
            })
            link_id = json.loads(add["result"]["content"][0]["text"])["link"]["id"]
            upd = await srv.dispatch({
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "hermes_hub_update_link", "arguments": {
                    "id": link_id, "description": "now-updated",
                }},
            })
            body = json.loads(upd["result"]["content"][0]["text"])
            assert body["ok"] is True
            assert body["link"]["description"] == "now-updated"
            # name should be untouched (partial update)
            assert body["link"]["name"] == "doc"
        finally:
            for p in (sqlite, hub_path):
                Path(p).unlink(missing_ok=True)

    asyncio.run(_run())
