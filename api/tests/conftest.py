"""Shared pytest fixtures.

The tests import the API as the top-level package ``api``. Adding the parent
directory to ``sys.path`` lets pytest discover the package regardless of where
it is invoked from, mirroring the Dockerfile's ``COPY . /app/api/`` layout.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_API_PKG_DIR = Path(__file__).resolve().parents[1]
_PARENT_DIR = _API_PKG_DIR.parent
if str(_PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(_PARENT_DIR))

# Fill in env vars before any module imports Settings.
os.environ.setdefault("HERMES_PRIMARY_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-1234567890ABCDEFGH")
os.environ.setdefault("OPENAI_BASE_URL", "http://openai.test/v1")
os.environ.setdefault("OPENAI_DEFAULT_MODEL", "gpt-4o-mini")
os.environ.setdefault("HERMES_TENANT_LABEL", "Hermes Test")
os.environ.setdefault("HERMES_TENANT_ICON", "\U0001F985")
os.environ.setdefault("HERMES_PUBLIC_URL", "https://hermes.test")
os.environ.setdefault("HERMES_CORS_ALLOW_ORIGINS", "http://localhost:3000")
os.environ.setdefault("HERMES_AGENT_LOOPS", "none")
os.environ.setdefault("SOUTHBROOK_HERMES_ENABLED", "false")
