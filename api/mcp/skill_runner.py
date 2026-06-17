"""Load + filter custom-hermes-skills entries for MCP exposure.

Phase 1 surfaces ONLY read-only skills (``destructive_actions == false``).
The runner is intentionally a metadata reader — Phase 1 does NOT execute
skill procedures from inside the MCP server (Phase 2 will). Phase 1 lets
the calling agent FETCH a skill's metadata + SKILL.md and act on them in
its own session — which is the correct safety boundary for v1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_SKILLS_ROOT = "/app/custom-hermes-skills/skills"


class SkillNotFound(Exception):
    pass


class SkillNotReadOnly(Exception):
    pass


def _root(skills_root: Optional[str]) -> Path:
    return Path(skills_root or os.environ.get(
        "HERMES_SKILLS_ROOT", DEFAULT_SKILLS_ROOT))


def list_read_only_skills(*, skills_root: Optional[str] = None) -> List[str]:
    root = _root(skills_root)
    out: List[str] = []
    if not root.exists():
        return out
    for d in sorted(root.iterdir()):
        if not d.is_dir():
            continue
        m = d / "metadata.json"
        if not m.exists():
            continue
        try:
            meta = json.loads(m.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if meta.get("destructive_actions") is False:
            out.append(d.name)
    return out


def load_skill_metadata(
    name: str, *, skills_root: Optional[str] = None,
    require_read_only: bool = False,
) -> Dict[str, Any]:
    root = _root(skills_root)
    m = root / name / "metadata.json"
    if not m.exists():
        raise SkillNotFound(f"skill not found: {name}")
    meta = json.loads(m.read_text(encoding="utf-8"))
    if require_read_only and meta.get("destructive_actions") is not False:
        raise SkillNotReadOnly(
            f"skill {name} is destructive; Phase 1 forbids exposure"
        )
    return meta


def load_skill_markdown(
    name: str, *, skills_root: Optional[str] = None
) -> str:
    root = _root(skills_root)
    p = root / name / "SKILL.md"
    if not p.exists():
        raise SkillNotFound(f"skill SKILL.md not found: {name}")
    return p.read_text(encoding="utf-8")
