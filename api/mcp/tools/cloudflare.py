"""Cloudflare read tools exposed via Hermes MCP.

Backed by ``api.mcp.clients.cloudflare.CloudflareClient`` which is a thin
v4 REST wrapper. Auth lives in ``CLOUDFLARE_API_TOKEN`` (the token is never
returned to clients). ``CLOUDFLARE_ACCOUNT_ID`` is optional but enables the
tunnel + Access app tools.

Phase 2 read surface (mirrors the ``cloudflare-dns-zero-trust-ops`` skill,
which previously could only describe these operations):
  hermes_cloudflare_list_zones
  hermes_cloudflare_list_dns_records
  hermes_cloudflare_get_tunnel
  hermes_cloudflare_list_access_apps

Writes (DNS edits, WAF changes, tunnel ingress edits) intentionally go
through the recommendation queue + operator approval, NOT through these
tools. Phase 2 ships read; Phase 3 adds approval-gated write.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from api.mcp.clients.cloudflare import CloudflareClient, CloudflareError
from api.mcp.tools import ToolSpec, register_tool

_CLIENT: Optional[CloudflareClient] = None


def set_cloudflare_client(client: Optional[CloudflareClient]) -> None:
    global _CLIENT
    _CLIENT = client


def _require_client() -> CloudflareClient:
    if _CLIENT is None:
        raise CloudflareError(
            "cloudflare client not configured — set CLOUDFLARE_API_TOKEN "
            "in .env and restart hermes-api"
        )
    return _CLIENT


async def _list_zones(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        zones = await _require_client().list_zones()
        return {"zones": zones, "count": len(zones)}
    except CloudflareError as exc:
        return {"error": str(exc)}


async def _list_dns_records(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    zone_id = args.get("zone_id")
    if not zone_id:
        return {"error": "missing 'zone_id'"}
    record_type = args.get("type")
    try:
        records = await _require_client().list_dns_records(zone_id, type=record_type)
        return {"records": records, "count": len(records), "zone_id": zone_id}
    except CloudflareError as exc:
        return {"error": str(exc)}


async def _get_tunnel(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    tunnel_id = args.get("tunnel_id")
    if not tunnel_id:
        return {"error": "missing 'tunnel_id'"}
    try:
        return {"tunnel": await _require_client().get_tunnel(tunnel_id)}
    except CloudflareError as exc:
        return {"error": str(exc)}


async def _list_access_apps(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        apps = await _require_client().list_access_apps()
        return {"apps": apps, "count": len(apps)}
    except CloudflareError as exc:
        return {"error": str(exc)}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_cloudflare_list_zones",
        description="List every Cloudflare zone the Hermes-side API token "
                    "can see. Returns id, name, status, plan, name_servers.",
        input_schema={"type": "object"},
        handler=_list_zones,
    ))
    register_tool(ToolSpec(
        name="hermes_cloudflare_list_dns_records",
        description="List DNS records in a zone. Optional 'type' filter "
                    "(A, AAAA, CNAME, MX, TXT, …).",
        input_schema={
            "type": "object",
            "required": ["zone_id"],
            "properties": {
                "zone_id": {"type": "string"},
                "type": {"type": "string"},
            },
        },
        handler=_list_dns_records,
    ))
    register_tool(ToolSpec(
        name="hermes_cloudflare_get_tunnel",
        description="Fetch a Cloudflare tunnel's metadata + ingress map "
                    "(public hostname → local origin). Useful for diagnosing "
                    "routing flakes like the .108→.76 IP drift.",
        input_schema={
            "type": "object",
            "required": ["tunnel_id"],
            "properties": {"tunnel_id": {"type": "string"}},
        },
        handler=_get_tunnel,
    ))
    register_tool(ToolSpec(
        name="hermes_cloudflare_list_access_apps",
        description="List Zero Trust Access applications + their policy "
                    "counts. Read-only.",
        input_schema={"type": "object"},
        handler=_list_access_apps,
    ))
