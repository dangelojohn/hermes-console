"""Skill catalog + read-only skill loader as MCP tools."""
from __future__ import annotations

from typing import Any, Dict, Optional

from api.mcp.skill_runner import (
    list_read_only_skills,
    load_skill_markdown,
    load_skill_metadata,
    SkillNotFound,
    SkillNotReadOnly,
)
from api.mcp.tools import ToolSpec, register_tool

_SKILLS_ROOT: Optional[str] = None


def set_skills_root(root: str) -> None:
    global _SKILLS_ROOT
    _SKILLS_ROOT = root


async def _list_skills(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    names = list_read_only_skills(skills_root=_SKILLS_ROOT)
    out = []
    for n in names:
        try:
            meta = load_skill_metadata(n, skills_root=_SKILLS_ROOT)
        except SkillNotFound:
            continue
        out.append({
            "name": meta["name"],
            "category": meta.get("category"),
            "summary": meta.get("summary"),
            "needs": meta.get("needs", []),
            "jtbds": meta.get("jtbds", []),
        })
    return {"skills": out, "count": len(out)}


async def _run_skill(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    name = args.get("name")
    if not name:
        return {"error": "missing 'name'"}
    try:
        meta = load_skill_metadata(
            name, skills_root=_SKILLS_ROOT, require_read_only=True,
        )
        markdown = load_skill_markdown(name, skills_root=_SKILLS_ROOT)
    except SkillNotReadOnly as exc:
        return {"error": f"destructive skill rejected: {exc}"}
    except SkillNotFound as exc:
        return {"error": str(exc)}
    return {"metadata": meta, "skill_markdown": markdown}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_list_skills",
        description="List read-only skills from custom-hermes-skills.",
        input_schema={"type": "object"},
        handler=_list_skills,
    ))
    register_tool(ToolSpec(
        name="hermes_run_skill",
        description="Fetch a read-only skill's metadata + SKILL.md text. "
                    "Phase 1 returns the procedure — calling agent executes "
                    "it in its own session.",
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        },
        handler=_run_skill,
    ))
