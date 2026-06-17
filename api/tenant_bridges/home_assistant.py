"""Home Assistant outbound bridge.

Hermes Console can push approved recommendations to a Home Assistant instance
as persistent notifications (always available, no add-on required) and
optionally read selected entity states back as agent-loop context.

Auth model: Home Assistant uses a long-lived access token (Bearer). The token
is created from the HA frontend under Profile → Long-Lived Access Tokens.
The token never leaves the HA-side `.env` block and is masked in every log.

Wire format:
- Push (notification): ``POST /api/services/persistent_notification/create``
  body ``{"title": ..., "message": ..., "notification_id": "<recommendation_id>"}``
- Optional callback service: if HA-side automation defines an input_button or
  custom service, the operator can configure ``HOME_ASSISTANT_PUSH_SERVICE`` to
  e.g. ``script.hermes_recommendation_received`` and this bridge will call
  that service instead of the generic persistent_notification.
- Health: ``GET /api/`` returns ``{"message": "API running."}`` when healthy.
- Optional context fetch: ``GET /api/states/<entity_id>`` for any entities
  named in ``HOME_ASSISTANT_CONTEXT_ENTITIES`` (comma-separated). This is
  read-only and limited to the entities explicitly named, never a wildcard.

Idempotency: the ``notification_id`` is the Hermes recommendation id, so
repeat pushes of the same recommendation overwrite the same HA notification
instead of accumulating clutter.

Errors map to:
- :class:`BridgeUnreachable` on DNS / timeout / 5xx → queue + retry
- :class:`BridgeRejected` on 4xx (bad token, malformed payload) → no retry
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import BridgeRejected, BridgeUnreachable

logger = logging.getLogger(__name__)


HEALTH_TIMEOUT = httpx.Timeout(5.0, connect=5.0)
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class HomeAssistantBridge:
    name = "home_assistant"

    def __init__(
        self,
        *,
        url: str,
        token: str,
        push_service: Optional[str] = None,
        context_entities: Optional[List[str]] = None,
    ) -> None:
        if not url:
            raise ValueError("home_assistant: url required")
        if not token:
            raise ValueError("home_assistant: token required")
        self._url = url.rstrip("/")
        self._token = token
        self._push_service = (push_service or "").strip()
        self._context_entities = [e.strip() for e in (context_entities or []) if e.strip()]
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=self._url,
                    timeout=DEFAULT_TIMEOUT,
                    headers={
                        "Authorization": f"Bearer {self._token}",
                        "Content-Type": "application/json",
                    },
                )
        masked = self._token[:6] + "…" if len(self._token) > 6 else "<redacted>"
        logger.info(
            "home_assistant bridge ready url=%s push_service=%s context_entities=%d token=%s",
            self._url,
            self._push_service or "(default persistent_notification)",
            len(self._context_entities),
            masked,
        )

    async def shutdown(self) -> None:
        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    async def health(self) -> str:
        try:
            client = await self._ensure()
            resp = await client.get("/api/", timeout=HEALTH_TIMEOUT)
        except (httpx.RequestError, httpx.HTTPStatusError):
            return "unreachable"
        if resp.status_code != 200:
            return "unreachable"
        try:
            data = resp.json()
        except ValueError:
            return "unreachable"
        return "ok" if data.get("message") == "API running." else "unreachable"

    async def push(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        client = await self._ensure()
        title = recommendation.get("title") or "Hermes recommendation"
        summary = recommendation.get("summary") or ""
        rec_id = str(recommendation.get("id") or "")

        if self._push_service:
            # Custom HA service path (e.g. "script.hermes_recommendation_received").
            domain, _, service = self._push_service.partition(".")
            if not (domain and service):
                raise BridgeRejected(
                    f"home_assistant: HOME_ASSISTANT_PUSH_SERVICE='{self._push_service}' "
                    "must be 'domain.service'"
                )
            path = f"/api/services/{domain}/{service}"
            body = {
                "title": title,
                "message": summary,
                "recommendation_id": rec_id,
                "priority": recommendation.get("priority") or "normal",
                "source": "hermes-console",
            }
        else:
            # Default path: persistent_notification.create.
            path = "/api/services/persistent_notification/create"
            body = {
                "title": title,
                "message": summary,
                "notification_id": f"hermes-{rec_id}" if rec_id else "hermes",
            }

        try:
            resp = await client.post(path, json=body)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise BridgeUnreachable(
                f"home_assistant: transport ({exc.__class__.__name__})"
            ) from exc
        except httpx.RequestError as exc:
            raise BridgeUnreachable(
                f"home_assistant: request ({exc.__class__.__name__})"
            ) from exc

        if resp.status_code >= 500:
            raise BridgeUnreachable(f"home_assistant: 5xx ({resp.status_code})")
        if resp.status_code == 401:
            raise BridgeRejected("home_assistant: 401 — long-lived token rejected")
        if resp.status_code >= 400:
            raise BridgeRejected(
                f"home_assistant: {resp.status_code} {resp.text[:200]}"
            )
        # HA returns 200 with an array of changed states on success.
        try:
            data = resp.json()
        except ValueError:
            data = {"raw": resp.text[:200]}
        return {"ok": True, "service": path, "ha_response": data}

    async def fetch_context(self) -> Dict[str, Any]:
        """Read the named context entities. Read-only, allowlisted, never wildcard.

        Returns a dict of {entity_id: {state, last_changed, attributes}} for each
        entity in ``HOME_ASSISTANT_CONTEXT_ENTITIES``. Designed to feed agent
        loops a tiny snapshot of "home state" — e.g. is anyone home, is the
        garage open, what is the office temperature. Never reads arbitrary
        entities; the operator opts-in to each one.
        """
        if not self._context_entities:
            return {}
        client = await self._ensure()
        out: Dict[str, Any] = {}
        for ent in self._context_entities:
            try:
                resp = await client.get(f"/api/states/{ent}", timeout=HEALTH_TIMEOUT)
            except httpx.RequestError as exc:
                out[ent] = {"error": f"transport {exc.__class__.__name__}"}
                continue
            if resp.status_code != 200:
                out[ent] = {"error": f"http {resp.status_code}"}
                continue
            try:
                data = resp.json()
            except ValueError:
                out[ent] = {"error": "non-json"}
                continue
            out[ent] = {
                "state": data.get("state"),
                "last_changed": data.get("last_changed"),
                "attributes": data.get("attributes") or {},
            }
        return out
