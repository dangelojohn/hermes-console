"""Phyn Smart Water Assistant MCP tools.

Phyn devices are cloud-only — there's no documented local API. The
canonical path to talk to them is via Home Assistant's Phyn integration,
which surfaces entities like:

  sensor.phyn_water_consumption       (cumulative gallons)
  sensor.phyn_current_flow_rate       (gal/min, instantaneous)
  sensor.phyn_water_pressure          (psi)
  sensor.phyn_water_temperature       (°F)
  binary_sensor.phyn_leak             (true when Phyn detects a leak)
  binary_sensor.phyn_away_mode        (true when away mode is on)
  valve.phyn_water_valve              (open/closed; setting requires a service call)

These tools wrap the HA bridge with Phyn-friendly defaults so the calling
agent doesn't need to remember the exact HA entity_ids. Discovery is
automatic — every HA entity whose ID contains 'phyn' (or matches a
configured override) gets exposed.

For control (closing the valve in an emergency), the operator opts in via
HOME_ASSISTANT_ALLOWED_SERVICES (e.g. add ``valve.close_valve``) and the
existing hermes_ha_call_service tool handles the actual call. We do NOT
add a phyn-specific write tool — that would duplicate the safety surface.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.mcp.tools import ToolSpec, register_tool

_BRIDGE: Any = None
_HINT: str = "phyn"


def set_phyn_context(*, bridge: Any, name_hint: Optional[str] = None) -> None:
    """Wire the HA bridge so the phyn tools can read its entity catalog.

    ``name_hint`` is the substring matched against entity_id / friendly_name
    when scanning HA for Phyn devices. Default 'phyn' is right for stock HA
    integrations; override via ``HERMES_PHYN_NAME_HINT`` if the operator
    renamed entities.
    """
    global _BRIDGE, _HINT
    _BRIDGE = bridge
    if name_hint:
        _HINT = name_hint


def _require_bridge():
    if _BRIDGE is None:
        raise RuntimeError(
            "Phyn tools require the Home Assistant bridge — set "
            "HOME_ASSISTANT_ENABLED=true + HOME_ASSISTANT_TOKEN in .env, "
            "make sure HA has the Phyn integration configured, then restart "
            "hermes-api."
        )
    return _BRIDGE


async def _discover(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    """List every HA entity whose ID/name contains the Phyn hint."""
    try:
        bridge = _require_bridge()
        entities = await bridge.list_entities(name_filter=_HINT)
        return {"entities": entities, "count": len(entities), "hint": _HINT}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


async def _snapshot(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    """Return the current values of every Phyn entity HA exposes.

    Bypasses HOME_ASSISTANT_CONTEXT_ENTITIES (this is device-family
    discovery, not arbitrary read). Operator-visible entities only —
    HA's own auth still applies.
    """
    try:
        bridge = _require_bridge()
        entities = await bridge.list_entities(name_filter=_HINT)
        # Trim to fields that matter for water monitoring.
        snapshot: List[Dict[str, Any]] = []
        for e in entities:
            snapshot.append({
                "entity_id": e.get("entity_id"),
                "friendly_name": e.get("friendly_name"),
                "state": e.get("state"),
                "unit": e.get("unit_of_measurement"),
                "device_class": e.get("device_class"),
                "last_changed": e.get("last_changed"),
            })
        # Highlight likely-actionable signals.
        leaks = [s for s in snapshot
                 if (s.get("device_class") == "moisture" or "leak" in (s.get("entity_id") or ""))
                 and str(s.get("state")).lower() in ("on", "true", "detected")]
        return {
            "snapshot": snapshot,
            "count": len(snapshot),
            "active_leak_signals": leaks,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_phyn_discover",
        description=(
            "List every Home Assistant entity whose entity_id or "
            "friendly_name contains 'phyn' (or the operator-configured "
            "HERMES_PHYN_NAME_HINT). Useful for an agent to find which "
            "Phyn sensors are wired in HA before snapshotting them."
        ),
        input_schema={"type": "object"},
        handler=_discover,
    ))
    register_tool(ToolSpec(
        name="hermes_phyn_snapshot",
        description=(
            "Snapshot of every Phyn entity HA knows about: water consumption, "
            "current flow rate, pressure, temperature, leak status, away mode, "
            "valve position. Flags any entity reporting an active leak in "
            "the ``active_leak_signals`` field."
        ),
        input_schema={"type": "object"},
        handler=_snapshot,
    ))
