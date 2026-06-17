"""MCP resources: enumerate + read."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from api.local_store import LocalStore
from api.mcp.skill_runner import (
    list_read_only_skills, load_skill_markdown, load_skill_metadata,
    SkillNotFound,
)

_STORE: Optional[LocalStore] = None
_SKILLS_ROOT: Optional[str] = None


def set_resources_context(*, store: LocalStore, skills_root: str) -> None:
    global _STORE, _SKILLS_ROOT
    _STORE = store
    _SKILLS_ROOT = skills_root


def _require_store() -> LocalStore:
    if _STORE is None:
        raise RuntimeError("resources store not set")
    return _STORE


async def list_resources() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    out.append({
        "uri": "hermes://recommendations",
        "name": "All recommendations (JSON)",
        "mimeType": "application/json",
    })
    out.append({
        "uri": "hermes://chat-threads",
        "name": "All chat threads (JSON)",
        "mimeType": "application/json",
    })
    out.append({
        "uri": "hermes://audit/today",
        "name": "MCP tool-call audit for the last 24h",
        "mimeType": "application/json",
    })
    for name in list_read_only_skills(skills_root=_SKILLS_ROOT):
        out.append({
            "uri": f"hermes://skills/{name}/SKILL.md",
            "name": f"Skill: {name} (SKILL.md)",
            "mimeType": "text/markdown",
        })
        out.append({
            "uri": f"hermes://skills/{name}/metadata.json",
            "name": f"Skill: {name} (metadata.json)",
            "mimeType": "application/json",
        })
    return out


async def read_resource(uri: str) -> Dict[str, Any]:
    if uri == "hermes://recommendations":
        rows = await _require_store().list_recommendations()
        return _json(uri, {"recommendations": rows, "count": len(rows)})
    if uri == "hermes://chat-threads":
        rows = await _require_store().list_threads()
        return _json(uri, {"threads": rows, "count": len(rows)})
    if uri == "hermes://audit/today":
        rows = await _require_store().list_mcp_calls(since_hours=24)
        return _json(uri, {"calls": rows, "count": len(rows)})
    if uri.startswith("hermes://skills/"):
        rest = uri[len("hermes://skills/"):]
        if "/" not in rest:
            raise ValueError(f"unknown resource: {uri}")
        name, filename = rest.split("/", 1)
        try:
            if filename == "SKILL.md":
                return _markdown(uri, load_skill_markdown(
                    name, skills_root=_SKILLS_ROOT))
            if filename == "metadata.json":
                return _json(uri, load_skill_metadata(
                    name, skills_root=_SKILLS_ROOT))
        except SkillNotFound as exc:
            raise ValueError(str(exc))
    raise ValueError(f"unknown resource: {uri}")


def _json(uri: str, body: Any) -> Dict[str, Any]:
    return {
        "contents": [{
            "uri": uri,
            "mimeType": "application/json",
            "text": json.dumps(body, default=str, indent=2),
        }],
    }


def _markdown(uri: str, text: str) -> Dict[str, Any]:
    return {
        "contents": [{
            "uri": uri,
            "mimeType": "text/markdown",
            "text": text,
        }],
    }
