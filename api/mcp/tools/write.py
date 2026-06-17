"""Phase 2 write tools.

These let MCP clients (Claude Code, Codex) FILE work and TRIGGER agent loops
without bypassing Hermes's safety model:

  hermes_file_recommendation  — adds a new row to the queue in state=ready.
                                 The operator still approves before any
                                 production-impacting bridge push happens.
  hermes_trigger_agent_loop   — runs platform_health / backup_health /
                                 daily_digest on-demand. Outputs are
                                 deterministic per-loop; no LLM call for
                                 backup_health.
  hermes_apply_recommendation — applies a recommendation that has reached
                                 state=approved by pushing it through the
                                 tenant bridge. Refuses if state is not
                                 'approved' — the same gate the REST
                                 /api/recommendations/{id}/apply endpoint
                                 uses.

Phase 2 ships file + trigger. apply is included so the round-trip
"agent files → operator approves → agent applies" works end-to-end.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from api.mcp.tools import ToolSpec, register_tool

_STORE: Any = None
_AGENT_RUNNER: Any = None
_BRIDGES: Dict[str, Any] = {}


def set_write_context(*, store: Any, agent_runner: Any, bridges: Dict[str, Any]) -> None:
    global _STORE, _AGENT_RUNNER, _BRIDGES
    _STORE = store
    _AGENT_RUNNER = agent_runner
    _BRIDGES = bridges or {}


def _require_store():
    if _STORE is None:
        raise RuntimeError("MCP write store not set")
    return _STORE


async def _file_recommendation(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    title = (args.get("title") or "").strip()
    if not title:
        return {"error": "title is required"}
    priority = args.get("priority") or "normal"
    if priority not in ("low", "normal", "high", "blocker"):
        return {"error": f"invalid priority: {priority}"}
    vals = {
        "title": title,
        "summary": args.get("summary"),
        "rationale": args.get("rationale"),
        "proposed_action": args.get("proposed_action"),
        "priority": priority,
        "source": args.get("source") or "mcp",
        "tenant_hint": args.get("tenant_hint"),
        "payload": args.get("payload"),
        "state": "ready",
    }
    rec = await _require_store().create_recommendation(vals)
    return {
        "recommendation": {
            "id": rec["id"], "state": rec["state"], "title": rec["title"],
            "priority": rec["priority"], "created_at": rec["created_at"],
        }
    }


async def _trigger_agent_loop(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    name = (args.get("name") or "").strip()
    if not name:
        return {"error": "name is required (platform_health|backup_health|daily_digest)"}
    if _AGENT_RUNNER is None:
        return {"error": "agent runner not configured in this MCP process"}
    try:
        result = await _AGENT_RUNNER.run_once(name)
    except KeyError:
        return {"error": f"unknown agent loop: {name}"}
    except Exception as exc:  # noqa: BLE001
        return {"error": f"{exc.__class__.__name__}: {exc}"}
    return {"loop": name, "result": result}


async def _apply_recommendation(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    rec_id = args.get("id")
    tenant_hint = args.get("tenant")
    if rec_id is None:
        return {"error": "id is required"}
    rec_id = int(rec_id)
    store = _require_store()
    rec = await store.get_recommendation(rec_id)
    if rec is None:
        return {"error": f"recommendation id={rec_id} not found"}
    if rec["state"] != "approved":
        return {
            "error": (
                f"recommendation id={rec_id} is in state '{rec['state']}'; "
                "only 'approved' recs can be applied. Operator must approve first."
            )
        }
    target = tenant_hint or rec.get("tenant_hint") or _default_bridge()
    if not target:
        return {"error": "no tenant bridge specified and no default available"}
    bridge = _BRIDGES.get(target)
    if bridge is None:
        return {
            "error": (
                f"tenant bridge '{target}' is not configured in this hermes-api "
                "process. Set the bridge's *_ENABLED env var and restart."
            )
        }
    try:
        push_result = await bridge.push(rec)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"bridge push failed: {exc.__class__.__name__}: {exc}"}
    updated = await store.update_recommendation_state(
        rec_id, "applied", reviewer_note="applied via MCP"
    )
    return {
        "recommendation": {"id": updated["id"], "state": updated["state"]} if updated else None,
        "bridge": target,
        "bridge_response": push_result,
    }


def _default_bridge() -> Optional[str]:
    # If exactly one bridge is configured, that's the default. Otherwise
    # require the caller to be explicit.
    if len(_BRIDGES) == 1:
        return next(iter(_BRIDGES.keys()))
    return None


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_file_recommendation",
        description=(
            "File a new recommendation into the Hermes queue. Lands in "
            "state=ready; the operator approves before any production "
            "action. Required: title. Optional: summary, rationale, "
            "proposed_action, priority (low|normal|high|blocker, default "
            "normal), source, tenant_hint (e.g. southbrook_hermes), "
            "payload (arbitrary JSON)."
        ),
        input_schema={
            "type": "object",
            "required": ["title"],
            "properties": {
                "title": {"type": "string"},
                "summary": {"type": "string"},
                "rationale": {"type": "string"},
                "proposed_action": {"type": "string"},
                "priority": {"type": "string",
                              "enum": ["low", "normal", "high", "blocker"]},
                "source": {"type": "string"},
                "tenant_hint": {"type": "string"},
                "payload": {"type": "object"},
            },
        },
        handler=_file_recommendation,
    ))
    register_tool(ToolSpec(
        name="hermes_trigger_agent_loop",
        description=(
            "Run a Hermes agent loop on-demand. Names: 'platform_health', "
            "'backup_health', 'daily_digest'. Returns the loop's structured "
            "result. backup_health is deterministic (no LLM call); the "
            "others may invoke the LLM router."
        ),
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        },
        handler=_trigger_agent_loop,
    ))
    register_tool(ToolSpec(
        name="hermes_apply_recommendation",
        description=(
            "Apply a recommendation that has reached state=approved by "
            "pushing it through the appropriate tenant bridge. Refuses "
            "non-approved recs. tenant defaults to the recommendation's "
            "tenant_hint or the single configured bridge."
        ),
        input_schema={
            "type": "object",
            "required": ["id"],
            "properties": {
                "id": {"type": "integer"},
                "tenant": {"type": "string"},
            },
        },
        handler=_apply_recommendation,
    ))
