"""Tests for the skill loader + read-only filter."""
from __future__ import annotations

from pathlib import Path

import pytest

from api.mcp.skill_runner import (
    list_read_only_skills,
    load_skill_metadata,
    load_skill_markdown,
    SkillNotFound,
    SkillNotReadOnly,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_list_read_only_skills_filters_destructive() -> None:
    names = list_read_only_skills(skills_root=str(FIXTURES))
    assert "skill-fixture-ok" in names
    assert "skill-fixture-destructive" not in names


def test_load_skill_metadata_returns_dict() -> None:
    md = load_skill_metadata("skill-fixture-ok", skills_root=str(FIXTURES))
    assert md["name"] == "skill-fixture-ok"
    assert md["destructive_actions"] is False


def test_load_skill_metadata_raises_on_missing() -> None:
    with pytest.raises(SkillNotFound):
        load_skill_metadata("nope", skills_root=str(FIXTURES))


def test_load_skill_markdown_returns_text() -> None:
    md = load_skill_markdown("skill-fixture-ok", skills_root=str(FIXTURES))
    assert "Skill Fixture OK" in md


def test_load_destructive_skill_raises_when_read_only_required() -> None:
    with pytest.raises(SkillNotReadOnly):
        load_skill_metadata(
            "skill-fixture-destructive",
            skills_root=str(FIXTURES),
            require_read_only=True,
        )
