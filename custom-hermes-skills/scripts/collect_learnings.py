#!/usr/bin/env python3
"""Collect + roll up per-skill outcome sidecars.

Walks runs/<skill>/*-outcome.json, appends each entry to learning/<skill>.md,
and (with --rollup) produces learning/_rollup-<ts>.md with success/partial/
failure/aborted counts and clustered lessons.

Secret-pattern scan rejects sidecars that contain credential-shaped strings —
the secret pattern bank mirrors scripts/validate_skills.py exactly.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
LEARNING_DIR = ROOT / "learning"

SECRET_PATTERNS = [
    re.compile(r"sk-(proj-)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-ant-api03-[A-Za-z0-9_-]{20,}"),
    re.compile(r"gsk_[A-Za-z0-9]{20,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"AQ\.Ab8[A-Za-z0-9_-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"ghp_[A-Za-z0-9]{20,}"),
    re.compile(r"xoxb-[0-9A-Za-z-]{20,}"),
    re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"),
]


def looks_secret(text: str) -> bool:
    return any(p.search(text) for p in SECRET_PATTERNS)


def collect_outcomes() -> dict:
    LEARNING_DIR.mkdir(exist_ok=True)
    out: dict[str, list[dict]] = {}
    if not RUNS_DIR.exists():
        return out
    for skill_dir in sorted(RUNS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        for f in skill_dir.glob("*-outcome.json"):
            try:
                raw = f.read_text(encoding="utf-8")
            except OSError:
                continue
            if looks_secret(raw):
                print(f"  REJECT (secret-shaped) {f.relative_to(ROOT)}")
                continue
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            out.setdefault(skill_dir.name, []).append(rec)
    return out


def write_per_skill(records: dict[str, list[dict]]) -> None:
    LEARNING_DIR.mkdir(exist_ok=True)
    for skill, recs in records.items():
        path = LEARNING_DIR / f"{skill}.md"
        with path.open("w", encoding="utf-8") as fp:
            fp.write(f"# Learning Journal — `{skill}`\n\n")
            fp.write(f"_Append-only. {len(recs)} runs recorded._\n\n")
            fp.write("| ts | outcome | duration_ms | lessons | blockers |\n")
            fp.write("|---|---|---|---|---|\n")
            for r in sorted(recs, key=lambda x: x.get("ts") or ""):
                lessons = "; ".join(r.get("lessons") or []).replace("|", "\\|")
                blockers = "; ".join(r.get("blockers_encountered") or []).replace("|", "\\|")
                fp.write(
                    f"| {r.get('ts','?')} | {r.get('outcome','?')} | {r.get('duration_ms','?')} | "
                    f"{lessons} | {blockers} |\n"
                )


def rollup(records: dict[str, list[dict]]) -> Path:
    LEARNING_DIR.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = LEARNING_DIR / f"_rollup-{now}.md"
    with path.open("w", encoding="utf-8") as fp:
        fp.write("# Library-wide rollup\n\n")
        fp.write(f"Generated at {now}\n\n")
        fp.write("## Outcomes per skill\n\n")
        fp.write("| Skill | total | success | partial | failure | aborted |\n")
        fp.write("|---|---|---|---|---|---|\n")
        for skill, recs in sorted(records.items()):
            c = Counter(r.get("outcome") for r in recs)
            fp.write(
                f"| `{skill}` | {len(recs)} | {c.get('success',0)} | "
                f"{c.get('partial',0)} | {c.get('failure',0)} | {c.get('aborted',0)} |\n"
            )
        fp.write("\n## Top recurring lessons\n\n")
        lessons: Counter[str] = Counter()
        for recs in records.values():
            for r in recs:
                for L in r.get("lessons") or []:
                    lessons[L.strip()] += 1
        for lesson, n in lessons.most_common(20):
            fp.write(f"- ({n}×) {lesson}\n")
    return path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rollup", action="store_true", help="Emit learning/_rollup-<ts>.md")
    ap.add_argument("--propose-edits", action="store_true", help="Emit proposed SKILL.md edits (stub)")
    args = ap.parse_args()

    records = collect_outcomes()
    if not records:
        print("No outcome sidecars found yet.")
        return 0
    write_per_skill(records)
    print(f"Per-skill journals updated for {len(records)} skill(s).")
    if args.rollup:
        p = rollup(records)
        print(f"Rollup written: {p.relative_to(ROOT)}")
    if args.propose_edits:
        print("(propose-edits: emit-stub mode — full implementation deferred to a later commit)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
