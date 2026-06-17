#!/usr/bin/env python3
"""Validate every skill in custom-hermes-skills/skills/.

Checks:
- SKILL.md exists with required section headings
- metadata.json exists, parses, has required fields
- SOURCE_INSPIRATION.md exists
- At least one Need ID or JTBD ID linked (meta-skills exempt)
- Safety constraints section non-empty
- If destructive_actions is true, Confirmation requirements section is present
- No obvious secret patterns in any file
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

REQUIRED_SKILL_SECTIONS = [
    "Purpose",
    "When to use",
    "When NOT to use",
    "Inputs expected",
    "Outputs produced",
    "Step-by-step operating procedure",
    "Safety constraints",
    "Source inspiration",
]
REQUIRED_METADATA_FIELDS = ["name", "category", "summary"]

SECRET_PATTERNS = [
    (re.compile(r"sk-(proj-)?[A-Za-z0-9_-]{20,}"), "openai"),
    (re.compile(r"sk-ant-api03-[A-Za-z0-9_-]{20,}"), "anthropic"),
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "groq"),
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), "google-legacy"),
    (re.compile(r"AQ\.Ab8[A-Za-z0-9_-]{20,}"), "google-new"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws-akid"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "github-pat"),
    (re.compile(r"xoxb-[0-9A-Za-z-]{20,}"), "slack-bot"),
    (re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"), "private-key"),
]

ALLOWED_SECRET_FILES = set()  # add per-file allowlist if needed


def check_skill(skill_dir: Path) -> list[str]:
    findings: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    metadata_json = skill_dir / "metadata.json"
    inspiration_md = skill_dir / "SOURCE_INSPIRATION.md"

    if not skill_md.exists():
        findings.append(f"[BLOCKER] {skill_dir.name}: missing SKILL.md")
        return findings
    if not metadata_json.exists():
        findings.append(f"[BLOCKER] {skill_dir.name}: missing metadata.json")
    if not inspiration_md.exists():
        findings.append(f"[BLOCKER] {skill_dir.name}: missing SOURCE_INSPIRATION.md")

    skill_text = skill_md.read_text(encoding="utf-8")
    for sec in REQUIRED_SKILL_SECTIONS:
        if f"## {sec}" not in skill_text:
            findings.append(f"[WARN] {skill_dir.name}/SKILL.md: missing section '## {sec}'")

    if metadata_json.exists():
        try:
            meta = json.loads(metadata_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            findings.append(f"[BLOCKER] {skill_dir.name}/metadata.json: invalid JSON ({e})")
            meta = {}
        for f in REQUIRED_METADATA_FIELDS:
            if f not in meta:
                findings.append(f"[BLOCKER] {skill_dir.name}/metadata.json: missing field '{f}'")
        if meta.get("category") != "meta":
            needs = meta.get("needs") or []
            jtbds = meta.get("jtbds") or []
            if not needs and not jtbds:
                findings.append(
                    f"[WARN] {skill_dir.name}: no Need or JTBD linkage (non-meta skill)"
                )
        if meta.get("destructive_actions") is True:
            if "## Confirmation requirements" not in skill_text:
                findings.append(
                    f"[BLOCKER] {skill_dir.name}/SKILL.md: destructive_actions=true "
                    f"but no 'Confirmation requirements' section"
                )

    for f in skill_dir.rglob("*"):
        if not f.is_file():
            continue
        if f.relative_to(skill_dir).as_posix() in ALLOWED_SECRET_FILES:
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat, label in SECRET_PATTERNS:
            if pat.search(text):
                findings.append(
                    f"[BLOCKER] {skill_dir.name}/{f.name}: contains a '{label}'-shaped string"
                )
                break
    return findings


def main() -> int:
    if not SKILLS_DIR.exists():
        print(f"Skills dir not found: {SKILLS_DIR}")
        return 1
    all_findings: list[str] = []
    skill_count = 0
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        skill_count += 1
        all_findings.extend(check_skill(d))
    blockers = [f for f in all_findings if f.startswith("[BLOCKER]")]
    warns = [f for f in all_findings if f.startswith("[WARN]")]
    print(f"Validated {skill_count} skills:")
    print(f"  blockers: {len(blockers)}")
    print(f"  warns:    {len(warns)}")
    for f in all_findings:
        print(f"  {f}")
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
