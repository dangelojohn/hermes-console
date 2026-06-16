"""Tenant bridge protocol.

A bridge is the outbound side of the agent control plane: when a
recommendation is approved + applied, the bridge ships it to a downstream
consumer system. Each concrete bridge owns its own auth (session cookie, API
key, OAuth — whatever the consumer demands) and its own httpx client.

Two distinct error classes so callers can decide what to do:

* :class:`BridgeUnreachable` — transport error (DNS, timeout, 5xx). The route
  layer queues the push and the retry worker tries again every 30s.
* :class:`BridgeRejected` — application error (4xx, validation failure). The
  push is marked failed and not retried, since the consumer will reject the
  same payload forever.
"""

from __future__ import annotations

from typing import Any, Dict, Protocol, runtime_checkable


class BridgeUnreachable(RuntimeError):
    """Transport-level failure — retry-able."""


class BridgeRejected(RuntimeError):
    """Application-level failure — not retry-able."""


@runtime_checkable
class TenantBridge(Protocol):
    """Outbound publisher of approved recommendations."""

    name: str

    async def startup(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def health(self) -> str:
        """Return 'ok', 'unreachable', or 'disabled'."""
        ...

    async def push(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        """Deliver a recommendation; return whatever the consumer responded.

        Raises :class:`BridgeUnreachable` on transport errors, or
        :class:`BridgeRejected` on application errors.
        """
        ...
