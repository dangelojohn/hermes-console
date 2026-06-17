"""Tool registry + dispatcher for the MCP server."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List

from api.local_store import LocalStore
from api.mcp.audit import audit_call

ToolHandler = Callable[[Any, Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class ToolSpec:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: ToolHandler


_REGISTRY: Dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> None:
    _REGISTRY[spec.name] = spec


def reset_registry_for_tests() -> None:
    _REGISTRY.clear()


def list_tools() -> List[Dict[str, Any]]:
    return [
        {"name": s.name, "description": s.description, "inputSchema": s.input_schema}
        for s in _REGISTRY.values()
    ]


async def call_tool(
    store: LocalStore, *, client_id: int, tool_name: str, arguments: Dict[str, Any]
) -> Dict[str, Any]:
    spec = _REGISTRY.get(tool_name)
    if spec is None:
        raise KeyError(f"tool not registered: {tool_name}")
    async with audit_call(
        store, client_id=client_id, tool_name=tool_name, args=arguments,
    ) as ctx:
        result = await spec.handler(ctx, arguments)
        ctx.set_outcome("ok")
    return {
        "content": [
            {"type": "text", "text": json.dumps(result, default=str, indent=2)},
        ],
    }
