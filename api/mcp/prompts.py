"""MCP prompts: review-queue + use-skill/<name>."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.mcp.skill_runner import (
    list_read_only_skills, load_skill_markdown, SkillNotFound,
)

_SKILLS_ROOT: Optional[str] = None


def set_prompts_context(*, skills_root: str) -> None:
    global _SKILLS_ROOT
    _SKILLS_ROOT = skills_root


async def list_prompts() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = [{
        "name": "review-queue",
        "description":
            "Show me what's open in the Hermes recommendation queue and "
            "propose the next action.",
    }]
    for name in list_read_only_skills(skills_root=_SKILLS_ROOT):
        out.append({
            "name": f"use-skill/{name}",
            "description": f"Guided template for invoking the '{name}' skill.",
        })
    return out


async def get_prompt(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    if name == "review-queue":
        return {
            "description": "Review the open Hermes queue and propose action.",
            "messages": [{
                "role": "user",
                "content": {"type": "text", "text": (
                    "Review the open recommendations in the Hermes Console. "
                    "Use the tool 'hermes_list_recommendations' with "
                    "state='ready' to fetch them, then propose the single "
                    "most important next action and why."
                )},
            }],
        }
    if name.startswith("use-skill/"):
        skill_name = name[len("use-skill/"):]
        try:
            md = load_skill_markdown(skill_name, skills_root=_SKILLS_ROOT)
        except SkillNotFound:
            raise ValueError(f"no such skill: {skill_name}")
        return {
            "description": f"Guided invocation of skill '{skill_name}'.",
            "messages": [{
                "role": "user",
                "content": {"type": "text", "text": (
                    f"You will invoke the Hermes skill '{skill_name}' via the "
                    "MCP tool 'hermes_run_skill'. Read the SKILL.md text "
                    "BELOW for inputs, outputs, safety constraints, and the "
                    "step-by-step operating procedure. Then carry out the "
                    "procedure in this session and report the findings.\n\n"
                    f"---\n\n{md}"
                )},
            }],
        }
    raise ValueError(f"no such prompt: {name}")
