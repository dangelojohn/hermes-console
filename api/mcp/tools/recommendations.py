"""Recommendation read tools."""
from __future__ import annotations

from typing import Any, Dict

from api.mcp.tools import ToolSpec, register_tool

_STORE: Any = None


def set_store(store: Any) -> None:
    global _STORE
    _STORE = store


def _current_store():
    if _STORE is None:
        raise RuntimeError("MCP store not set; call set_store() first")
    return _STORE


async def _list_recommendations(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    state = args.get("state")
    limit = int(args.get("limit") or 50)
    store = _current_store()
    rows = await store.list_recommendations(state=state, limit=limit)
    return {
        "recommendations": [
            {
                "id": r["id"], "state": r["state"], "title": r["title"],
                "priority": r["priority"], "source": r.get("source"),
                "created_at": r["created_at"],
            }
            for r in rows
        ],
        "count": len(rows),
    }


async def _get_recommendation(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    rec_id = int(args["id"])
    row = await _current_store().get_recommendation(rec_id)
    if row is None:
        return {"error": f"recommendation id={rec_id} not found"}
    return {"recommendation": row}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_list_recommendations",
        description="List recommendations, optionally filtered by state "
                    "(ready|approved|rejected|applied|draft).",
        input_schema={
            "type": "object",
            "properties": {
                "state": {"type": "string"},
                "limit": {"type": "integer", "default": 50},
            },
        },
        handler=_list_recommendations,
    ))
    register_tool(ToolSpec(
        name="hermes_get_recommendation",
        description="Fetch a single recommendation by id.",
        input_schema={
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "integer"}},
        },
        handler=_get_recommendation,
    ))
