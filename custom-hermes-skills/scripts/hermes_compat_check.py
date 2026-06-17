#!/usr/bin/env python3
"""Check that every skill folder matches the documented Hermes-compatible
agent-skills structure.

The structure expected here is the publicly documented format:
- skills/<name>/SKILL.md
- skills/<name>/metadata.json
- (optional) skills/<name>/scripts/
- (optional) skills/<name>/examples/
- (optional) skills/<name>/tests/

Plus this library's local additions:
- skills/<name>/SOURCE_INSPIRATION.md

This is a structural-conformance pass — the deep safety checks are in
validate_skills.py.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"

REQUIRED_FILES = ["SKILL.md", "metadata.json", "SOURCE_INSPIRATION.md"]
OPTIONAL_DIRS = ["scripts", "examples", "tests"]


def main() -> int:
    findings: list[str] = []
    if not SKILLS_DIR.exists():
        print(f"Skills dir not found: {SKILLS_DIR}")
        return 1
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        name = d.name
        for req in REQUIRED_FILES:
            if not (d / req).exists():
                findings.append(f"[MISS] {name}: required file '{req}' missing")
        meta_path = d / "metadata.json"
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                findings.append(f"[ERR] {name}/metadata.json: invalid JSON ({e})")
                continue
            if meta.get("name") != name:
                findings.append(
                    f"[WARN] {name}/metadata.json: name='{meta.get('name')}' "
                    f"does not match folder '{name}'"
                )
    print(f"Hermes-compat check: {len(findings)} findings")
    for f in findings:
        print(f"  {f}")
    return 1 if any(f.startswith("[MISS]") or f.startswith("[ERR]") for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main())
