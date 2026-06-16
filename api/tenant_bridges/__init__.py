"""Outbound tenant bridges.

A *tenant bridge* publishes approved recommendations into a downstream consumer
system. Each bridge is a thin async class that:

* identifies itself with a ``name`` (matches the key in /api/tenants),
* implements ``async health()`` for the /api/tenants/.../test endpoint and the
  /api/health roll-up,
* implements ``async push(recommendation)`` to deliver a recommendation,
  raising :class:`BridgeUnreachable` for transport errors (queue + retry) or
  :class:`BridgeRejected` for application errors (mark failed, surface 502).

The bridges are constructed in ``main.lifespan`` from :class:`Settings` and
held on ``app.state.bridges``. Disabled bridges are simply not constructed.
"""

from __future__ import annotations

from .base import BridgeRejected, BridgeUnreachable, TenantBridge
from .southbrook_hermes import SouthbrookHermesBridge

__all__ = [
    "BridgeRejected",
    "BridgeUnreachable",
    "SouthbrookHermesBridge",
    "TenantBridge",
]
