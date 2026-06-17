#!/usr/bin/env python3
"""Cross-reference NEEDS_ASSESSMENT.md and JTBD_MAP.md against skill metadata
and report which Need / JTBD IDs have no covering skill yet.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
NEEDS_DOC = ROOT / "NEEDS_ASSESSMENT.md"
JTBD_DOC = ROOT / "JTBD_MAP.md"

NEED_PATTERN = re.compile(r"\bN-\d{2,3}\b")
JTBD_PATTERN = re.compile(r"\bJ-\d{2,3}\b")


def extract_ids(text: str, pat: re.Pattern[str]) -> set[str]:
    return set(pat.findall(text))


def main() -> int:
    if not SKILLS_DIR.exists() or not NEEDS_DOC.exists() or not JTBD_DOC.exists():
        print("Missing one of: skills/, NEEDS_ASSESSMENT.md, JTBD_MAP.md")
        return 1

    declared_needs = extract_ids(NEEDS_DOC.read_text(encoding="utf-8"), NEED_PATTERN)
    declared_jtbds = extract_ids(JTBD_DOC.read_text(encoding="utf-8"), JTBD_PATTERN)
    covered_needs: set[str] = set()
    covered_jtbds: set[str] = set()
    skills_per_need: dict[str, list[str]] = {}
    skills_per_jtbd: dict[str, list[str]] = {}

    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        m = d / "metadata.json"
        if not m.exists():
            continue
        try:
            meta = json.loads(m.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for n in meta.get("needs") or []:
            covered_needs.add(n)
            skills_per_need.setdefault(n, []).append(meta.get("name") or d.name)
        for j in meta.get("jtbds") or []:
            covered_jtbds.add(j)
            skills_per_jtbd.setdefault(j, []).append(meta.get("name") or d.name)

    uncovered_needs = sorted(declared_needs - covered_needs)
    uncovered_jtbds = sorted(declared_jtbds - covered_jtbds)

    print(f"Declared Need IDs: {len(declared_needs)} / covered: {len(declared_needs & covered_needs)}")
    print(f"Declared JTBD IDs: {len(declared_jtbds)} / covered: {len(declared_jtbds & covered_jtbds)}")
    if uncovered_needs:
        print("Uncovered Needs:")
        for n in uncovered_needs:
            print(f"  {n}")
    if uncovered_jtbds:
        print("Uncovered JTBDs:")
        for j in uncovered_jtbds:
            print(f"  {j}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
