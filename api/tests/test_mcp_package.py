"""Package layout sanity checks for the new MCP module."""
from __future__ import annotations

import importlib
import subprocess
import sys


def test_package_imports() -> None:
    mod = importlib.import_module("api.mcp")
    assert mod.__name__ == "api.mcp"


def test_module_runnable_prints_help() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "api.mcp", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert "stdio" in result.stdout
    assert "keygen" in result.stdout
    assert "keys" in result.stdout
