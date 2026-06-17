"""MCP tools that let Hermes maintain the intra-net Hub dashboard.

Hermes is the Hub's webmaster. As the operator discovers new services or
existing services move/rename, Hermes can:

  hermes_hub_list_links      — enumerate everything currently on the dashboard
  hermes_hub_add_link        — append a link to a category (creates the
                                 category if it doesn't exist yet)
  hermes_hub_update_link     — partial update to one link by id
  hermes_hub_remove_link     — delete a link by id
  hermes_hub_replace_manifest — wholesale replace, for batch reorganisation
  hermes_hub_upsert_category — add/rename/recolour a category

Reads happen through ``HubStore.read()``, which deep-copies the cache so
callers can't mutate shared state. Writes go through ``_lock`` so concurrent
MCP sessions don't tear the file.

The dashboard at ``/hub/`` polls ``GET /api/hub/manifest`` every minute —
changes from these tools show up there without a redeploy.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.mcp.tools import ToolSpec, register_tool

_STORE: Any = None


def set_hub_store(store: Any) -> None:
    global _STORE
    _STORE = store


def _require_store():
    if _STORE is None:
        raise RuntimeError(
            "Hub manifest store is not wired up — this means hermes-api "
            "started in a degraded mode. Restart hermes-api."
        )
    return _STORE


async def _list_links(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        store = _require_store()
        m = await store.read()
        out: List[Dict[str, Any]] = []
        for cat in m.get("categories", []):
            for link in cat.get("links", []):
                out.append({
                    "id": link.get("id"),
                    "category_id": cat.get("id"),
                    "category_name": cat.get("name"),
                    "name": link.get("name"),
                    "url": link.get("url"),
                    "description": link.get("description"),
                    "tags": link.get("tags", []),
                })
        return {"count": len(out), "links": out,
                "categories": [{"id": c["id"], "name": c["name"],
                                  "count": len(c.get("links", []))}
                                for c in m.get("categories", [])],
                "updated_at": m.get("updated_at")}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


async def _add_link(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        store = _require_store()
        link = await store.add_link(
            category_id=args["category_id"],
            name=args["name"],
            url=args["url"],
            description=args.get("description", ""),
            health_url=args.get("health_url"),
            tags=args.get("tags", []),
            icon=args.get("icon"),
            who=getattr(ctx, "client_name", None) or "hermes",
        )
        return {"ok": True, "link": link}
    except KeyError as exc:
        return {"error": f"missing argument: {exc.args[0]}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


async def _update_link(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        store = _require_store()
        link_id = args.get("id") or args.get("link_id")
        if not link_id:
            return {"error": "missing argument: id"}
        fields = {k: v for k, v in args.items() if k not in ("id", "link_id")}
        link = await store.update_link(link_id=link_id, fields=fields,
                                          who=getattr(ctx, "client_name", None) or "hermes")
        if link is None:
            return {"error": f"link id {link_id!r} not found"}
        return {"ok": True, "link": link}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


async def _remove_link(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        store = _require_store()
        link_id = args.get("id") or args.get("link_id")
        if not link_id:
            return {"error": "missing argument: id"}
        ok = await store.remove_link(link_id=link_id,
                                        who=getattr(ctx, "client_name", None) or "hermes")
        return {"ok": ok, "removed_id": link_id if ok else None}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


async def _replace_manifest(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        store = _require_store()
        m = args.get("manifest")
        if not isinstance(m, dict):
            return {"error": "manifest must be an object"}
        new = await store.replace(m, who=getattr(ctx, "client_name", None) or "hermes")
        return {"ok": True, "categories": len(new.get("categories", []))}
    except ValueError as exc:
        return {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


async def _upsert_category(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        store = _require_store()
        cat = await store.upsert_category(
            id=args["id"],
            name=args["name"],
            icon=args.get("icon", ""),
            accent=args.get("accent", "#7c5cff"),
            order=args.get("order"),
            who=getattr(ctx, "client_name", None) or "hermes",
        )
        return {"ok": True, "category": {"id": cat["id"], "name": cat["name"],
                                            "icon": cat.get("icon"),
                                            "accent": cat.get("accent")}}
    except KeyError as exc:
        return {"error": f"missing argument: {exc.args[0]}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_hub_list_links",
        description=(
            "List every link currently displayed on the intra-net Hub dashboard, "
            "grouped by category. Useful before deciding to add/update/remove "
            "links so the agent doesn't duplicate work."
        ),
        input_schema={"type": "object"},
        handler=_list_links,
    ))
    register_tool(ToolSpec(
        name="hermes_hub_add_link",
        description=(
            "Add a link to the Hub dashboard. Pass category_id (e.g. 'odoo', "
            "'home_automation', 'network', 'code', 'qnap', 'docs') — if the "
            "category doesn't exist it is created with default styling. "
            "health_url is optional; when set the dashboard pings it client-side "
            "and renders a coloured status pill."
        ),
        input_schema={
            "type": "object",
            "required": ["category_id", "name", "url"],
            "properties": {
                "category_id": {"type": "string"},
                "name": {"type": "string"},
                "url": {"type": "string"},
                "description": {"type": "string"},
                "health_url": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "icon": {"type": "string",
                          "description": "Emoji or short symbol (e.g. '🦊')"},
            },
        },
        handler=_add_link,
    ))
    register_tool(ToolSpec(
        name="hermes_hub_update_link",
        description=(
            "Partial update to one link on the Hub dashboard. Identify the "
            "link by its 'id' (from hermes_hub_list_links) and pass only "
            "the fields you want to change."
        ),
        input_schema={
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "url": {"type": "string"},
                "description": {"type": "string"},
                "health_url": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "icon": {"type": "string"},
            },
        },
        handler=_update_link,
    ))
    register_tool(ToolSpec(
        name="hermes_hub_remove_link",
        description="Remove a link from the Hub dashboard by id.",
        input_schema={
            "type": "object",
            "required": ["id"],
            "properties": {"id": {"type": "string"}},
        },
        handler=_remove_link,
    ))
    register_tool(ToolSpec(
        name="hermes_hub_replace_manifest",
        description=(
            "Wholesale replace the Hub manifest. Pass the entire new manifest "
            "object under 'manifest' — must include a 'categories' list. "
            "Use sparingly; prefer add/update/remove for incremental changes."
        ),
        input_schema={
            "type": "object",
            "required": ["manifest"],
            "properties": {"manifest": {"type": "object"}},
        },
        handler=_replace_manifest,
    ))
    register_tool(ToolSpec(
        name="hermes_hub_upsert_category",
        description=(
            "Add a new category or rename / restyle an existing one. "
            "Categories are rendered as section headers on the dashboard. "
            "'accent' takes a CSS hex colour."
        ),
        input_schema={
            "type": "object",
            "required": ["id", "name"],
            "properties": {
                "id": {"type": "string"},
                "name": {"type": "string"},
                "icon": {"type": "string"},
                "accent": {"type": "string",
                            "description": "CSS hex colour, e.g. '#7c5cff'"},
                "order": {"type": "integer"},
            },
        },
        handler=_upsert_category,
    ))
