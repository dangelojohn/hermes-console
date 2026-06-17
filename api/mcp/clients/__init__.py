"""Outbound clients to upstream MCP servers and Cloudflare/etc REST APIs.

This package holds the connectors Hermes uses to talk to external services
that it then re-exposes as MCP tools to its own clients (Claude Code, Codex).

Phase 2 inhabitants:
  cloudflare.py — direct REST client against the Cloudflare API v4, used by
    the hermes_cloudflare_* tools in api/mcp/tools/cloudflare.py.

Phase 3 (designed, not implemented):
  upstream_mcp.py — connector to an upstream MCP server (e.g. the
    product-graph-mcp container on QNAP) so its tools can be re-exported
    under a namespace prefix.
"""

__all__: list[str] = []
