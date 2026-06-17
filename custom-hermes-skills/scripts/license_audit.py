#!/usr/bin/env python3
"""License + secret-leak audit.

Confirms every skill has a SOURCE_INSPIRATION.md and that no file in the
library contains an obvious credential pattern.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
LICENSE_DOC = ROOT / "LICENSE_AND_ATTRIBUTION.md"

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


def main() -> int:
    findings: list[str] = []
    if not LICENSE_DOC.exists():
        findings.append(f"[BLOCKER] missing LICENSE_AND_ATTRIBUTION.md at {LICENSE_DOC}")
    if not SKILLS_DIR.exists():
        print(f"Skills dir not found: {SKILLS_DIR}")
        return 1
    skill_count = 0
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        skill_count += 1
        si = d / "SOURCE_INSPIRATION.md"
        if not si.exists():
            findings.append(f"[BLOCKER] {d.name}: missing SOURCE_INSPIRATION.md")
    for f in ROOT.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix in (".pyc", ".png", ".jpg", ".pdf"):
            continue
        if any(part in {".git", "node_modules", "__pycache__", "runs"} for part in f.parts):
            continue
        if "license_audit.py" in f.name or "validate_skills.py" in f.name or "skill_integrity_check.py" in f.name:
            # patterns are listed here as detectors; skip self-scan
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for pat, label in SECRET_PATTERNS:
            if pat.search(text):
                findings.append(
                    f"[BLOCKER] {f.relative_to(ROOT)}: contains a '{label}'-shaped string"
                )
                break
    blockers = [f for f in findings if f.startswith("[BLOCKER]")]
    print(f"License audit complete. Skills checked: {skill_count}. Blockers: {len(blockers)}.")
    for f in findings:
        print(f"  {f}")
    return 1 if blockers else 0


if __name__ == "__main__":
    sys.exit(main())
