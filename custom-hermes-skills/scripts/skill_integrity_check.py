#!/usr/bin/env python3
"""Entrypoint script for the skill-integrity-auditor skill.

Currently delegates to validate_skills.py (which has the secret-pattern scan
and structural checks). A future Phase 2 version will produce the per-skill
findings files documented in skills/skill-integrity-auditor/SKILL.md.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

if __name__ == "__main__":
    here = Path(__file__).resolve().parent
    raise SystemExit(subprocess.call([sys.executable, str(here / "validate_skills.py"), *sys.argv[1:]]))
