"""Chat-thread read tools."""
from __future__ import annotations

from typing import Any, Dict

from api.mcp.tools import ToolSpec, register_tool

_STORE: Any = None


def _current_store():
    if _STORE is None:
        raise RuntimeError("MCP store not set; call set_store() first")
    return _STORE


def set_store(store: Any) -> None:
    global _STORE
    _STORE = store


async def _list_threads(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    limit = int(args.get("limit") or 50)
    rows = await _current_store().list_threads(limit=limit)
    return {"threads": rows, "count": len(rows)}


async def _get_messages(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    thread_id = int(args["thread_id"])
    store = _current_store()
    thread = await store.get_thread(thread_id)
    if thread is None:
        return {"messages": [], "thread": None}
    msgs = await store.list_messages(thread_id=thread_id)
    return {"thread": thread, "messages": msgs}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_list_chat_threads",
        description="List chat threads in the Hermes Console store.",
        input_schema={
            "type": "object",
            "properties": {"limit": {"type": "integer", "default": 50}},
        },
        handler=_list_threads,
    ))
    register_tool(ToolSpec(
        name="hermes_get_chat_messages",
        description="Fetch all messages in a chat thread by id.",
        input_schema={
            "type": "object",
            "required": ["thread_id"],
            "properties": {"thread_id": {"type": "integer"}},
        },
        handler=_get_messages,
    ))
