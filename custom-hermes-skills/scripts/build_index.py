#!/usr/bin/env python3
"""Rebuild SKILLS_INDEX.md from the current state of skills/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
INDEX_PATH = ROOT / "SKILLS_INDEX.md"

CATEGORIES = [
    "odoo-backend",
    "odoo-frontend",
    "odoo-cloud",
    "qnap",
    "forgejo",
    "web-services",
    "python",
    "javascript",
    "networking-cloudflare-web-services",
    "documentation",
    "meta",
]


def load_meta(skill_dir: Path) -> dict:
    m = skill_dir / "metadata.json"
    if not m.exists():
        return {}
    try:
        return json.loads(m.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main() -> int:
    if not SKILLS_DIR.exists():
        print(f"Skills dir not found: {SKILLS_DIR}")
        return 1
    rows = []
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        meta = load_meta(d)
        rows.append(
            {
                "name": meta.get("name") or d.name,
                "category": meta.get("category") or "unknown",
                "summary": (meta.get("summary") or meta.get("description") or "").strip(),
                "needs": ", ".join(meta.get("needs") or []),
                "jtbds": ", ".join(meta.get("jtbds") or []),
            }
        )
    rows.sort(key=lambda r: (CATEGORIES.index(r["category"]) if r["category"] in CATEGORIES else 999, r["name"]))

    out: list[str] = []
    out.append("# Skills Index")
    out.append("")
    out.append(f"_Auto-generated from `skills/` by `scripts/build_index.py`. {len(rows)} skills._")
    out.append("")
    out.append("| Skill | Category | Summary | Needs | JTBDs |")
    out.append("|---|---|---|---|---|")
    for r in rows:
        summary = r["summary"].replace("|", "\\|")
        out.append(
            f"| `{r['name']}` | {r['category']} | {summary} | {r['needs']} | {r['jtbds']} |"
        )
    out.append("")
    out.append("## By category")
    out.append("")
    for cat in CATEGORIES:
        cat_rows = [r for r in rows if r["category"] == cat]
        if not cat_rows:
            continue
        out.append(f"### {cat} ({len(cat_rows)})")
        out.append("")
        for r in cat_rows:
            out.append(f"- `{r['name']}` — {r['summary']}")
        out.append("")
    INDEX_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Wrote {INDEX_PATH.relative_to(ROOT)} with {len(rows)} skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
