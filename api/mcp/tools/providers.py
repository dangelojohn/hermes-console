"""LLM provider health read tool."""
from __future__ import annotations

from typing import Any, Dict

from api.mcp.tools import ToolSpec, register_tool

_REGISTRY: Any = None


def set_provider_registry(reg: Any) -> None:
    global _REGISTRY
    _REGISTRY = reg


async def _provider_health(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    if _REGISTRY is None:
        return {"llm": {}, "error": "registry not configured"}
    return {"llm": await _REGISTRY.health()}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_get_provider_health",
        description="Health of every LLM provider configured in Hermes.",
        input_schema={"type": "object"},
        handler=_provider_health,
    ))
