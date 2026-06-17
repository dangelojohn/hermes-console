#!/usr/bin/env python3
"""Set learning_enabled=true on every skill's metadata.json.

Idempotent: skills that already have learning_enabled keep their value.
Skills that are missing the key get learning_enabled=true added.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"


def main() -> int:
    changed = 0
    seen = 0
    for d in sorted(SKILLS_DIR.iterdir()):
        if not d.is_dir():
            continue
        m = d / "metadata.json"
        if not m.exists():
            continue
        seen += 1
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"  SKIP {d.name}: invalid JSON ({e})")
            continue
        if data.get("learning_enabled") is True:
            continue
        data["learning_enabled"] = True
        # Insert in a predictable place (after default_mode if present, else at end).
        ordered = {}
        for k, v in data.items():
            ordered[k] = v
        m.write_text(json.dumps(ordered, indent=2) + "\n", encoding="utf-8")
        changed += 1
        print(f"  + learning_enabled=true → {d.name}")
    print(f"\nProcessed {seen} skills; updated {changed}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
