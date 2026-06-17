"""SQLite store tests for the new mcp_clients table."""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from api.local_store import LocalStore


def test_create_then_get_mcp_client() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="claude-code", key_hash="hash-xyz")
            assert cid >= 1
            row = await store.get_mcp_client(cid)
            assert row is not None
            assert row["name"] == "claude-code"
            assert row["key_hash"] == "hash-xyz"
            assert row["revoked_at"] is None
            await store.shutdown()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_list_active_mcp_clients_excludes_revoked() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            store = LocalStore(tmp.name)
            await store.startup()
            a = await store.create_mcp_client(name="a", key_hash="ha")
            b = await store.create_mcp_client(name="b", key_hash="hb")
            await store.revoke_mcp_client(a)
            rows = await store.list_mcp_clients(active_only=True)
            assert len(rows) == 1
            assert rows[0]["id"] == b
            await store.shutdown()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())


def test_find_mcp_client_by_key_hash() -> None:
    async def _run() -> None:
        tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        tmp.close()
        try:
            store = LocalStore(tmp.name)
            await store.startup()
            cid = await store.create_mcp_client(name="codex", key_hash="hashed-secret")
            found = await store.find_mcp_client_by_key_hash("hashed-secret")
            assert found is not None
            assert found["id"] == cid
            none = await store.find_mcp_client_by_key_hash("nope")
            assert none is None
            await store.shutdown()
        finally:
            Path(tmp.name).unlink(missing_ok=True)

    asyncio.run(_run())
