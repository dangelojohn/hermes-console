"""CLI entry: ``python -m api.mcp <subcommand>``.

stdio   Run the MCP stdio server (Task 9 wires it up).
keygen  Create a new per-agent API key. Prints the key ONCE to stdout.
keys    list  → JSON list of clients (no raw keys).
        revoke --id N → mark client N revoked.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from api.local_store import LocalStore
from api.mcp.auth import generate_key, hash_key


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="api.mcp", description="Hermes MCP service")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("stdio", help="Run the MCP stdio server")
    kg = sub.add_parser("keygen", help="Create a new per-agent API key")
    kg.add_argument("--client", required=True, help="Logical name for the client")
    keys = sub.add_parser("keys", help="List or revoke existing keys")
    keys.add_argument("action", choices=["list", "revoke"])
    keys.add_argument("--id", type=int, help="Required for revoke")
    return parser


def _db_path() -> str:
    return os.environ.get("HERMES_SQLITE_PATH", "/data/hermes.sqlite")


async def _keygen(client_name: str) -> int:
    key = generate_key(client_name)
    store = LocalStore(_db_path())
    await store.startup()
    try:
        await store.create_mcp_client(name=client_name, key_hash=hash_key(key))
    finally:
        await store.shutdown()
    # The raw key is shown EXACTLY once and goes to stdout. The operator copies
    # it to ~/.config/hermes/mcp-key-<client>; nothing else stores it.
    print(key)
    print(
        f"\nKey for client '{client_name}' issued. Copy the line above to "
        "~/.config/hermes/mcp-key-<client> on the operator Mac (chmod 600). "
        "This is the only time the key is displayed.",
        file=sys.stderr,
    )
    return 0


async def _keys_list() -> int:
    store = LocalStore(_db_path())
    await store.startup()
    try:
        rows = await store.list_mcp_clients(active_only=False)
    finally:
        await store.shutdown()
    safe = [
        {"id": r["id"], "name": r["name"],
         "created_at": r["created_at"], "revoked_at": r["revoked_at"]}
        for r in rows
    ]
    print(json.dumps(safe, indent=2))
    return 0


async def _keys_revoke(client_id: int) -> int:
    store = LocalStore(_db_path())
    await store.startup()
    try:
        ok = await store.revoke_mcp_client(client_id)
    finally:
        await store.shutdown()
    if not ok:
        print(f"client id={client_id} not found or already revoked", file=sys.stderr)
        return 1
    print(f"revoked client id={client_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "stdio":
        print("stdio: not implemented yet (Task 9)", file=sys.stderr)
        return 1
    if args.cmd == "keygen":
        return asyncio.run(_keygen(args.client))
    if args.cmd == "keys":
        if args.action == "list":
            return asyncio.run(_keys_list())
        if args.action == "revoke":
            if args.id is None:
                print("--id required for revoke", file=sys.stderr)
                return 2
            return asyncio.run(_keys_revoke(args.id))
    return 1


if __name__ == "__main__":
    sys.exit(main())
