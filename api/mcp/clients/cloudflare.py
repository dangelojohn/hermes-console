"""Thin Cloudflare API v4 client for the hermes_cloudflare_* MCP tools.

Read-only by design — Phase 2 surface exposes ``list_zones``,
``list_dns_records``, ``get_tunnel``, and ``list_access_apps``. Writes go
through the existing recommendation queue + bridge layer, NOT through this
client directly (that's the differentiator from Cloudflare's official MCP).

Auth: a single Cloudflare API token in the ``CLOUDFLARE_API_TOKEN`` env var.
The token's scope determines what tools can do — least privilege is
``Zone:Zone:Read``, ``Zone:DNS:Read``, ``Account:Cloudflare Tunnel:Read``,
``Account:Access: Apps and Policies:Read``.

The token is NEVER returned to MCP clients and NEVER appears in audit rows
(the existing api.mcp.redaction module already scrubs it).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("api.mcp.clients.cloudflare")

API_BASE = "https://api.cloudflare.com/client/v4"
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class CloudflareError(RuntimeError):
    """Raised when the Cloudflare API returns an error or is unreachable."""


class CloudflareClient:
    def __init__(self, *, api_token: str, account_id: Optional[str] = None) -> None:
        if not api_token:
            raise ValueError("CLOUDFLARE_API_TOKEN required")
        self._api_token = api_token
        self._account_id = account_id
        self._client: Optional[httpx.AsyncClient] = None

    async def startup(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=API_BASE,
                timeout=DEFAULT_TIMEOUT,
                headers={
                    "Authorization": f"Bearer {self._api_token}",
                    "Content-Type": "application/json",
                },
            )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    async def _get(self, path: str, **params: Any) -> Dict[str, Any]:
        client = await self._ensure()
        try:
            resp = await client.get(path, params=params or None)
        except httpx.RequestError as exc:
            raise CloudflareError(
                f"cloudflare transport error: {exc.__class__.__name__}"
            ) from exc
        if resp.status_code == 401:
            raise CloudflareError("cloudflare auth rejected (401)")
        if resp.status_code == 403:
            raise CloudflareError("cloudflare token lacks permission (403)")
        if resp.status_code >= 400:
            raise CloudflareError(
                f"cloudflare {resp.status_code}: {resp.text[:200]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise CloudflareError("cloudflare non-json response") from exc
        if not data.get("success"):
            errs = data.get("errors") or []
            raise CloudflareError(f"cloudflare api errors: {errs}")
        return data

    # ------------------------------------------------------------------
    # Read endpoints — Phase 2 surface
    # ------------------------------------------------------------------

    async def list_zones(self) -> List[Dict[str, Any]]:
        """List zones the token can see. Useful Phase-2 root: every other
        tool is parametrised by zone_id."""
        data = await self._get("/zones", per_page=50)
        return [
            {
                "id": z["id"],
                "name": z["name"],
                "status": z["status"],
                "plan": (z.get("plan") or {}).get("name"),
                "name_servers": z.get("name_servers"),
            }
            for z in (data.get("result") or [])
        ]

    async def list_dns_records(
        self, zone_id: str, *, type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List DNS records in a zone. ``type`` filters (A, AAAA, CNAME, MX, …)."""
        params = {"per_page": 200}
        if type:
            params["type"] = type
        data = await self._get(f"/zones/{zone_id}/dns_records", **params)
        return [
            {
                "id": r["id"],
                "type": r["type"],
                "name": r["name"],
                "content": r["content"],
                "proxied": r.get("proxied"),
                "ttl": r.get("ttl"),
                "comment": r.get("comment"),
            }
            for r in (data.get("result") or [])
        ]

    async def get_tunnel(self, tunnel_id: str) -> Dict[str, Any]:
        """Fetch tunnel + its current configuration (ingress map).

        Requires ``account_id`` to be set at construction time.
        """
        if not self._account_id:
            raise CloudflareError(
                "account_id required for get_tunnel; "
                "set CLOUDFLARE_ACCOUNT_ID in the env"
            )
        meta = await self._get(
            f"/accounts/{self._account_id}/cfd_tunnel/{tunnel_id}"
        )
        cfg = await self._get(
            f"/accounts/{self._account_id}/cfd_tunnel/{tunnel_id}/configurations"
        )
        tunnel = meta.get("result") or {}
        config = cfg.get("result") or {}
        ingress = ((config.get("config") or {}).get("ingress")) or []
        return {
            "id": tunnel.get("id"),
            "name": tunnel.get("name"),
            "status": tunnel.get("status"),
            "connections": tunnel.get("connections"),
            "ingress": [
                {
                    "hostname": i.get("hostname"),
                    "service": i.get("service"),
                    "path": i.get("path"),
                }
                for i in ingress
            ],
            "ingress_count": len(ingress),
        }

    async def list_access_apps(self) -> List[Dict[str, Any]]:
        """List Zero Trust Access applications."""
        if not self._account_id:
            raise CloudflareError(
                "account_id required for list_access_apps; "
                "set CLOUDFLARE_ACCOUNT_ID in the env"
            )
        data = await self._get(f"/accounts/{self._account_id}/access/apps")
        return [
            {
                "id": a["id"],
                "name": a["name"],
                "type": a.get("type"),
                "domain": a.get("domain"),
                "policies_count": len(a.get("policies") or []),
            }
            for a in (data.get("result") or [])
        ]
