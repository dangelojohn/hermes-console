"""CLI entry: ``python -m api.mcp <subcommand>``.

Subcommands:
  stdio   Run the MCP stdio server (Claude Code spawns this).
  keygen  Create a new per-agent API key.
  keys    List or revoke existing keys.
"""
from __future__ import annotations

import argparse
import sys


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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.cmd == "stdio":
        print("stdio: not implemented yet (Task 9)", file=sys.stderr)
        return 1
    if args.cmd == "keygen":
        print(f"keygen: not implemented yet (Task 8) client={args.client}", file=sys.stderr)
        return 1
    if args.cmd == "keys":
        print(f"keys {args.action}: not implemented yet (Task 8)", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
