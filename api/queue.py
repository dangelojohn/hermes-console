"""Outbound bridge-push retry worker.

The previous iteration of this module was a SQLite queue for inbound Odoo
write actions. This iteration repurposes the same retry pattern for *outbound*
tenant pushes: when a bridge fails to deliver a recommendation, the
``bridge_pushes`` row in :mod:`local_store` is the durable record, and this
worker re-attempts every pending push every ``RETRY_INTERVAL_SECONDS``.

State machine (one ``bridge_pushes`` row per attempt-set per recommendation):

    pending  ──► sending  ──► succeeded
       ▲           │
       │           ▼
       └──── failed (transient, attempts < MAX_RETRIES)
                    │
                    ▼
                 failed (permanent — application rejected, attempts ≥ MAX)

The store owns persistence; this module owns the dispatch + retry policy.
``enqueue`` is the entry point invoked by the apply route when a push fails or
must be deferred.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional

from .local_store import LocalStore, LocalStoreUnavailable
from .models import QueuedPush
from .tenant_bridges.base import BridgeRejected, BridgeUnreachable, TenantBridge

logger = logging.getLogger(__name__)

RETRY_INTERVAL_SECONDS = 30
MAX_RETRIES = 10


class OutboundQueue:
    """Retries deferred bridge pushes against tenant bridges."""

    def __init__(
        self,
        *,
        store: LocalStore,
        bridges: Mapping[str, TenantBridge],
        recommendation_fetcher: Callable[[int], Awaitable[Optional[Dict[str, Any]]]],
        retry_interval_seconds: int = RETRY_INTERVAL_SECONDS,
    ) -> None:
        self._store = store
        self._bridges = bridges
        self._fetch_rec = recommendation_fetcher
        self._retry_interval = retry_interval_seconds
        self._worker_task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        self._stop_event.clear()
        self._worker_task = asyncio.create_task(
            self._worker_loop(), name="hermes-outbound-queue"
        )
        logger.info("outbound queue worker started; interval=%ss", self._retry_interval)

    async def shutdown(self) -> None:
        self._stop_event.set()
        if self._worker_task is not None:
            try:
                await asyncio.wait_for(self._worker_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._worker_task.cancel()
            self._worker_task = None
        logger.info("outbound queue worker stopped")

    # ------------------------------------------------------------------
    # Enqueue (called by the apply route when push fails or is deferred)
    # ------------------------------------------------------------------

    async def enqueue(
        self, *, recommendation_id: int, bridge_name: str
    ) -> Dict[str, Any]:
        push = await self._store.create_bridge_push(
            recommendation_id=recommendation_id, bridge_name=bridge_name
        )
        logger.info(
            "queued bridge push id=%s recommendation=%s bridge=%s",
            push["id"],
            recommendation_id,
            bridge_name,
        )
        return push

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    async def depth(self) -> int:
        return await self._store.bridge_pushes_depth()

    async def list_all(self, *, limit: int = 200) -> List[QueuedPush]:
        rows = await self._store.list_bridge_pushes(limit=limit)
        return [QueuedPush(**r) for r in rows]

    # ------------------------------------------------------------------
    # Dispatch + retry
    # ------------------------------------------------------------------

    async def deliver_now(
        self, *, recommendation_id: int, bridge_name: str
    ) -> Dict[str, Any]:
        """Try to deliver a recommendation directly; create a push row first.

        Returns a dict with keys ``status`` (succeeded|failed|pending),
        ``bridge_push_id`` and optional ``error``. On a transient failure the
        row is left in ``pending`` for the worker to retry.
        """

        bridge = self._bridges.get(bridge_name)
        push = await self._store.create_bridge_push(
            recommendation_id=recommendation_id, bridge_name=bridge_name
        )
        if bridge is None:
            err = f"bridge {bridge_name!r} not configured"
            await self._store.mark_bridge_push(
                push["id"], status="failed", error=err, increment_attempts=True
            )
            return {
                "status": "failed",
                "bridge_push_id": push["id"],
                "error": err,
            }

        rec = await self._fetch_rec(recommendation_id)
        if rec is None:
            err = f"recommendation {recommendation_id} not found"
            await self._store.mark_bridge_push(
                push["id"], status="failed", error=err, increment_attempts=True
            )
            return {
                "status": "failed",
                "bridge_push_id": push["id"],
                "error": err,
            }

        await self._store.mark_bridge_push(push["id"], status="sending")
        try:
            response = await bridge.push(rec)
        except BridgeUnreachable as exc:
            err = f"unreachable: {exc}"
            await self._store.mark_bridge_push(
                push["id"], status="pending", error=err, increment_attempts=True
            )
            logger.warning(
                "bridge %s unreachable for rec=%s; left pending (%s)",
                bridge_name,
                recommendation_id,
                exc,
            )
            return {
                "status": "pending",
                "bridge_push_id": push["id"],
                "error": err,
            }
        except BridgeRejected as exc:
            err = f"rejected: {exc}"
            await self._store.mark_bridge_push(
                push["id"], status="failed", error=err, increment_attempts=True
            )
            logger.warning(
                "bridge %s rejected rec=%s: %s", bridge_name, recommendation_id, exc
            )
            return {
                "status": "failed",
                "bridge_push_id": push["id"],
                "error": err,
            }

        await self._store.mark_bridge_push(
            push["id"],
            status="succeeded",
            response_payload=response,
            increment_attempts=True,
        )
        return {
            "status": "succeeded",
            "bridge_push_id": push["id"],
            "response": response,
        }

    async def flush(self) -> Dict[str, int]:
        """Attempt every pending push once; return per-status counters."""

        pending = await self._store.list_pending_bridge_pushes()
        if not pending:
            return {"flushed": 0, "succeeded": 0, "failed": 0, "still_pending": 0}

        succeeded = failed = still_pending = 0
        for push in pending:
            push_id = push["id"]
            bridge_name = push["bridge_name"]
            rec_id = push["recommendation_id"]
            attempts = int(push["attempts"] or 0)

            bridge = self._bridges.get(bridge_name)
            if bridge is None:
                await self._store.mark_bridge_push(
                    push_id,
                    status="failed",
                    error=f"bridge {bridge_name!r} not configured",
                    increment_attempts=True,
                )
                failed += 1
                continue

            rec = await self._fetch_rec(rec_id)
            if rec is None:
                await self._store.mark_bridge_push(
                    push_id,
                    status="failed",
                    error=f"recommendation {rec_id} not found",
                    increment_attempts=True,
                )
                failed += 1
                continue

            logger.warning(
                "retry bridge push id=%s bridge=%s rec=%s attempt=%s",
                push_id,
                bridge_name,
                rec_id,
                attempts + 1,
            )
            await self._store.mark_bridge_push(push_id, status="sending")
            try:
                response = await bridge.push(rec)
            except BridgeUnreachable as exc:
                # Mark either pending-for-retry or terminal-failed.
                new_status = "failed" if attempts + 1 >= MAX_RETRIES else "pending"
                await self._store.mark_bridge_push(
                    push_id,
                    status=new_status,
                    error=f"unreachable: {exc}",
                    increment_attempts=True,
                )
                if new_status == "failed":
                    failed += 1
                else:
                    still_pending += 1
                continue
            except BridgeRejected as exc:
                await self._store.mark_bridge_push(
                    push_id,
                    status="failed",
                    error=f"rejected: {exc}",
                    increment_attempts=True,
                )
                failed += 1
                continue
            except LocalStoreUnavailable as exc:  # pragma: no cover
                logger.exception(
                    "store unavailable while marking push id=%s: %s", push_id, exc
                )
                still_pending += 1
                continue

            await self._store.mark_bridge_push(
                push_id,
                status="succeeded",
                response_payload=response,
                increment_attempts=True,
            )
            succeeded += 1

        return {
            "flushed": len(pending),
            "succeeded": succeeded,
            "failed": failed,
            "still_pending": still_pending,
        }

    # ------------------------------------------------------------------
    # Worker loop
    # ------------------------------------------------------------------

    async def _worker_loop(self) -> None:
        logger.info("outbound retry loop entering")
        while not self._stop_event.is_set():
            try:
                await self.flush()
            except Exception:  # pragma: no cover - defensive
                logger.exception("outbound queue iteration crashed")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(), timeout=self._retry_interval
                )
            except asyncio.TimeoutError:
                continue
