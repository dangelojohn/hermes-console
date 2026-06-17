"""Per-call audit: one row per MCP tool invocation.

Async context manager. Default outcome is 'error' unless ``ctx.set_outcome('ok')``
is called explicitly before exit. If an exception escapes the with-block, the
outcome stays 'error' and ``error_text`` carries the exception repr (redacted).
"""
from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, Optional

from api.local_store import LocalStore
from api.mcp.redaction import redact


class AuditContext:
    def __init__(self) -> None:
        self.outcome: str = "error"
        self.error_text: Optional[str] = None

    def set_outcome(self, outcome: str) -> None:
        self.outcome = outcome


@asynccontextmanager
async def audit_call(
    store: LocalStore,
    *,
    client_id: int,
    tool_name: str,
    args: Dict[str, Any],
) -> AsyncIterator[AuditContext]:
    ctx = AuditContext()
    started = time.perf_counter()
    args_redacted = redact(args)
    try:
        yield ctx
    except Exception as exc:  # noqa: BLE001 — we want to log anything
        ctx.error_text = _short_repr_redacted(exc)
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        await store.log_mcp_call(
            client_id=client_id,
            tool_name=tool_name,
            args_redacted=args_redacted,
            outcome=ctx.outcome,
            error_text=ctx.error_text,
            duration_ms=duration_ms,
        )


def _short_repr_redacted(exc: Exception) -> str:
    s = f"{exc.__class__.__name__}: {exc}"
    # redact strings inside an exception repr the same way as tool args.
    redacted_obj = redact({"_": s})
    return redacted_obj["_"][:500]
