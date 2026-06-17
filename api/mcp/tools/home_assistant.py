"""Home Assistant MCP tools.

Exposes HA state to Claude Code / Codex through Hermes:
  hermes_ha_get_context     — read the configured allowlist (fetch_context).
  hermes_ha_list_entities   — discover what HA exposes (no allowlist).
  hermes_ha_get_state       — read one entity (must be in allowlist).
  hermes_ha_call_service    — call a service from the HOME_ASSISTANT_
                                ALLOWED_SERVICES allowlist. Gated by env.

Devices reachable through this — assuming the HA-side integrations are
configured — include Ecobee thermostats, Lutron Caséta lights/shades,
TP-Link Omada (via HACS tp_link_omada integration), Google Home / Nest
products, and anything else with an HA integration. Hermes doesn't talk
to the devices directly; it talks to HA, which talks to the devices.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.mcp.tools import ToolSpec, register_tool

_BRIDGE: Any = None
_ALLOWED_SERVICES: List[str] = []


def set_ha_context(*, bridge: Any, allowed_services: List[str]) -> None:
    global _BRIDGE, _ALLOWED_SERVICES
    _BRIDGE = bridge
    _ALLOWED_SERVICES = allowed_services or []


def _require_bridge():
    if _BRIDGE is None:
        raise RuntimeError(
            "Home Assistant bridge not configured — set HOME_ASSISTANT_ENABLED=true "
            "+ HOME_ASSISTANT_TOKEN in .env and restart hermes-api"
        )
    return _BRIDGE


async def _ha_get_context(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    try:
        result = await _require_bridge().fetch_context()
        return {"context": result, "count": len(result)}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


async def _ha_list_entities(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    domain_filter = args.get("domain")
    name_filter = args.get("name_contains")
    try:
        entities = await _require_bridge().list_entities(
            domain_filter=domain_filter, name_filter=name_filter,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}
    return {"entities": entities, "count": len(entities)}


async def _ha_get_state(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    entity_id = args.get("entity_id") or ""
    if not entity_id:
        return {"error": "entity_id is required"}
    bridge = _require_bridge()
    # respect the allowlist: only entities in HOME_ASSISTANT_CONTEXT_ENTITIES.
    if entity_id not in bridge._context_entities:  # noqa: SLF001
        return {
            "error": (
                f"entity_id '{entity_id}' is not in HOME_ASSISTANT_CONTEXT_ENTITIES "
                f"allowlist. Add it to .env to read this entity. "
                f"Use hermes_ha_list_entities to discover entity_ids — that does NOT "
                f"require allowlist membership."
            )
        }
    try:
        ctx_data = await bridge.fetch_context()
        return {"entity_id": entity_id, "data": ctx_data.get(entity_id, {})}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


async def _ha_call_service(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    domain = args.get("domain") or ""
    service = args.get("service") or ""
    data = args.get("data") or {}
    if not domain or not service:
        return {"error": "domain and service are required"}
    if not _ALLOWED_SERVICES:
        return {
            "error": (
                "HA service calls are disabled — set "
                "HOME_ASSISTANT_ALLOWED_SERVICES in .env to a comma-separated "
                "list of 'domain.service' strings (e.g. climate.set_temperature,"
                "light.turn_on) and restart hermes-api"
            )
        }
    try:
        return await _require_bridge().call_service(
            domain=domain, service=service, data=data,
            allowed_services=_ALLOWED_SERVICES,
        )
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_ha_list_entities",
        description=(
            "List entities Home Assistant exposes. Optional 'domain' filter "
            "(e.g. 'climate', 'light', 'sensor', 'binary_sensor', 'switch', "
            "'cover'). Optional 'name_contains' substring filter (matches "
            "entity_id and friendly_name). Returns entity_id, state, "
            "friendly_name, device_class, unit_of_measurement. "
            "NOT subject to the read-allowlist — this is directory discovery."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "domain": {"type": "string"},
                "name_contains": {"type": "string"},
            },
        },
        handler=_ha_list_entities,
    ))
    register_tool(ToolSpec(
        name="hermes_ha_get_context",
        description=(
            "Read every entity in HOME_ASSISTANT_CONTEXT_ENTITIES (the "
            "operator-defined allowlist). Returns "
            "{entity_id: {state, last_changed, attributes}}. Use this for a "
            "single snapshot of home state. For one entity see hermes_ha_get_state."
        ),
        input_schema={"type": "object"},
        handler=_ha_get_context,
    ))
    register_tool(ToolSpec(
        name="hermes_ha_get_state",
        description=(
            "Read one HA entity's state + attributes. Must be in the "
            "HOME_ASSISTANT_CONTEXT_ENTITIES allowlist; otherwise the call "
            "returns an error directing the operator to add it. To find "
            "available entity_ids, use hermes_ha_list_entities (no allowlist)."
        ),
        input_schema={
            "type": "object",
            "required": ["entity_id"],
            "properties": {"entity_id": {"type": "string"}},
        },
        handler=_ha_get_state,
    ))
    register_tool(ToolSpec(
        name="hermes_ha_call_service",
        description=(
            "Call a Home Assistant service (e.g. climate.set_temperature, "
            "light.turn_on, cover.open_cover). Gated by the "
            "HOME_ASSISTANT_ALLOWED_SERVICES allowlist — empty list means "
            "every service is denied (safe default). "
            "data is the service body (e.g. "
            "{\"entity_id\": \"climate.ecobee\", \"temperature\": 21.5})."
        ),
        input_schema={
            "type": "object",
            "required": ["domain", "service"],
            "properties": {
                "domain": {"type": "string"},
                "service": {"type": "string"},
                "data": {"type": "object"},
            },
        },
        handler=_ha_call_service,
    ))
