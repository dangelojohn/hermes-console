"""Tenant-bridge status read tool."""
from __future__ import annotations

from typing import Any, Dict

from api.mcp.tools import ToolSpec, register_tool

_BRIDGES: Dict[str, Any] = {}


def set_bridges(bridges: Dict[str, Any]) -> None:
    global _BRIDGES
    _BRIDGES = bridges


async def _get_tenant_status(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, str] = {}
    for name, bridge in _BRIDGES.items():
        try:
            out[name] = await bridge.health()
        except Exception as exc:  # noqa: BLE001
            out[name] = f"error: {exc.__class__.__name__}"
    return {"bridges": out}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_get_tenant_status",
        description="Health status of every tenant bridge registered in Hermes.",
        input_schema={"type": "object"},
        handler=_get_tenant_status,
    ))
