"""Southbrook Hermes outbound bridge.

The southbrook_hermes Odoo addon already exposes
``POST /hermes/api/v1/recommendations`` (see the controller in
``addons/southbrook_hermes/controllers/main.py``) which is the cheap, intended
path. We try that first when an API key is supplied; otherwise we fall back to
session-cookie auth + JSON-RPC ``call_kw`` against
``southbrook.hermes.recommendation``.

The httpx ``AsyncClient`` carries the Odoo ``session_id`` cookie automatically
once we authenticate, so subsequent ``call_kw`` posts re-use the same session
for as long as it lives. 401/SessionExpired triggers a single re-auth retry.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .base import BridgeRejected, BridgeUnreachable

logger = logging.getLogger(__name__)


HEALTH_TIMEOUT = httpx.Timeout(5.0, connect=5.0)
DEFAULT_TIMEOUT = httpx.Timeout(15.0, connect=5.0)


class SouthbrookHermesBridge:
    name = "southbrook_hermes"

    def __init__(
        self,
        *,
        url: str,
        db: str,
        user: str,
        password: str,
        api_key: Optional[str] = None,
    ) -> None:
        self._url = url.rstrip("/")
        self._db = db
        self._user = user
        self._password = password
        self._api_key = api_key or ""
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
        self._authenticated = False

    async def startup(self) -> None:
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=self._url,
                    timeout=DEFAULT_TIMEOUT,
                    follow_redirects=False,
                )

    async def shutdown(self) -> None:
        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None
                self._authenticated = False

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> str:
        """Return 'ok' if the Odoo node is reachable, else 'unreachable'.

        Odoo 19 exposes ``/web/webclient/version_info`` (no auth needed) which
        is the cheapest reachability probe; ``/web/health`` is module-gated.
        """

        client = await self._ensure_client()
        try:
            resp = await client.post(
                "/web/webclient/version_info",
                json={"jsonrpc": "2.0", "params": {}},
                timeout=HEALTH_TIMEOUT,
            )
        except httpx.RequestError:
            return "unreachable"
        if resp.status_code >= 500:
            return "unreachable"
        return "ok"

    # ------------------------------------------------------------------
    # Push
    # ------------------------------------------------------------------

    async def push(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        # When an API key is supplied we prefer the lightweight controller path;
        # it accepts the exact shape the addon expects and skips session auth.
        if self._api_key:
            return await self._push_controller(recommendation)
        return await self._push_call_kw(recommendation)

    # ------------------------------------------------------------------
    # Strategy 1: controller endpoint
    # ------------------------------------------------------------------

    async def _push_controller(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        client = await self._ensure_client()
        body = self._map_to_controller_payload(recommendation)
        try:
            resp = await client.post(
                "/hermes/api/v1/recommendations",
                json=body,
                headers={"X-Api-Key": self._api_key},
            )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes transport: {exc.__class__.__name__}"
            ) from exc
        except httpx.RequestError as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes request: {exc.__class__.__name__}"
            ) from exc

        if resp.status_code >= 500:
            raise BridgeUnreachable(
                f"southbrook_hermes 5xx: {resp.status_code}"
            )
        if resp.status_code >= 400:
            raise BridgeRejected(
                f"southbrook_hermes {resp.status_code}: {resp.text[:300]}"
            )

        try:
            return resp.json()
        except ValueError as exc:
            raise BridgeRejected(
                f"southbrook_hermes non-json response: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Strategy 2: session-cookie + JSON-RPC create
    # ------------------------------------------------------------------

    async def _authenticate(self) -> None:
        client = await self._ensure_client()
        body = {
            "jsonrpc": "2.0",
            "params": {
                "db": self._db,
                "login": self._user,
                "password": self._password,
            },
        }
        try:
            resp = await client.post("/web/session/authenticate", json=body)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes auth transport: {exc.__class__.__name__}"
            ) from exc
        except httpx.RequestError as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes auth request: {exc.__class__.__name__}"
            ) from exc

        if resp.status_code >= 500:
            raise BridgeUnreachable(
                f"southbrook_hermes auth 5xx: {resp.status_code}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes auth non-json: {exc}"
            ) from exc

        if "error" in data:
            err = data["error"].get("data", {})
            raise BridgeRejected(
                f"southbrook_hermes auth rejected: {err.get('name')} "
                f"{err.get('message')}"
            )

        result = data.get("result") or {}
        if not result.get("uid"):
            raise BridgeRejected("southbrook_hermes auth returned no uid")

        self._authenticated = True
        logger.info("southbrook_hermes authenticated uid=%s", result.get("uid"))

    async def _push_call_kw(self, recommendation: Dict[str, Any]) -> Dict[str, Any]:
        client = await self._ensure_client()
        values = self._map_to_call_kw_values(recommendation)

        async def _do_call() -> Dict[str, Any]:
            body = {
                "jsonrpc": "2.0",
                "params": {
                    "model": "southbrook.hermes.recommendation",
                    "method": "create",
                    "args": [values],
                    "kwargs": {},
                },
            }
            try:
                resp = await client.post("/web/dataset/call_kw", json=body)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
                raise BridgeUnreachable(
                    f"southbrook_hermes call_kw transport: {exc.__class__.__name__}"
                ) from exc
            except httpx.RequestError as exc:
                raise BridgeUnreachable(
                    f"southbrook_hermes call_kw request: {exc.__class__.__name__}"
                ) from exc

            if resp.status_code >= 500:
                raise BridgeUnreachable(
                    f"southbrook_hermes call_kw 5xx: {resp.status_code}"
                )

            try:
                return resp.json()
            except ValueError as exc:
                raise BridgeUnreachable(
                    f"southbrook_hermes call_kw non-json: {exc}"
                ) from exc

        if not self._authenticated:
            await self._authenticate()

        data = await _do_call()

        if "error" in data:
            err = data["error"].get("data", {})
            name = err.get("name", "")
            if "SessionExpired" in name:
                logger.info("southbrook_hermes session expired; re-authenticating")
                self._authenticated = False
                await self._authenticate()
                data = await _do_call()
                if "error" in data:
                    err = data["error"].get("data", {})
                    raise BridgeRejected(
                        f"southbrook_hermes create error: {err.get('name')} "
                        f"{err.get('message')}"
                    )
            else:
                raise BridgeRejected(
                    f"southbrook_hermes create error: {name} {err.get('message')}"
                )

        rec_id = data.get("result")
        return {
            "ok": True,
            "recommendation_id": rec_id if isinstance(rec_id, int) else None,
            "raw": data,
        }

    # ------------------------------------------------------------------
    # JWT-bearer tool surface (used by /api/hermes/ask agent loop)
    # ------------------------------------------------------------------

    @staticmethod
    def _redact_jwt(jwt_token: str) -> str:
        """Return a short prefix of a JWT for structured logging.

        JWTs are self-contained bearer credentials — leaking one to a log
        file is the same as leaking a session cookie. We keep the first 8
        chars so an operator can spot the persona-band header in-flight,
        no more.
        """

        if not jwt_token:
            return "<empty>"
        if len(jwt_token) <= 8:
            return "<redacted>"
        return f"{jwt_token[:8]}…"

    async def list_tools(self, *, jwt: str) -> List[Dict[str, Any]]:
        """Fetch the persona/tier-filtered tool catalog via JWT-bearer auth.

        Wire: ``GET /api/hermes/tools`` with ``Authorization: Bearer <jwt>``.
        The Odoo side (``hermes_tools_api.py``) decodes the JWT, resolves
        the persona + tier from the claims, and returns a ``{tenant,
        persona, tier, tools}`` envelope where ``tools`` is a list of tool
        descriptors matching this caller's registry membership.

        Returns the ``tools`` list. Raises :class:`BridgeRejected` on
        4xx (auth/scope error) and :class:`BridgeUnreachable` on
        transport failure or 5xx.
        """

        client = await self._ensure_client()
        try:
            resp = await client.get(
                "/api/hermes/tools",
                headers={"Authorization": f"Bearer {jwt}"},
                timeout=DEFAULT_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes tools transport: {exc.__class__.__name__}"
            ) from exc
        except httpx.RequestError as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes tools request: {exc.__class__.__name__}"
            ) from exc

        if resp.status_code >= 500:
            raise BridgeUnreachable(
                f"southbrook_hermes tools 5xx: {resp.status_code}"
            )
        if resp.status_code >= 400:
            raise BridgeRejected(
                f"southbrook_hermes tools {resp.status_code}: {resp.text[:300]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes tools non-json: {exc}"
            ) from exc

        tools = data.get("tools") if isinstance(data, dict) else None
        if not isinstance(tools, list):
            raise BridgeRejected(
                "southbrook_hermes tools response missing 'tools' list"
            )
        logger.info(
            "southbrook_hermes list_tools ok jwt=%s count=%d",
            self._redact_jwt(jwt),
            len(tools),
        )
        return tools

    async def call_tool(
        self,
        slug: str,
        *,
        jwt: str,
        args: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute one tool by slug on the Odoo side.

        Wire: ``POST /api/hermes/tools/<slug>`` with the JWT in the
        ``Authorization`` header and the tool's arguments as the JSON
        body. Odoo re-binds claim-derived args (``persona``,
        ``partner_id``, ``tenant``) authoritatively — the LLM can't
        spoof them even if it hallucinates values for them.

        Returns the raw response dict. Raises :class:`BridgeRejected`
        on 4xx (auth, unknown slug, tier scope) and
        :class:`BridgeUnreachable` on transport failure or 5xx.
        """

        client = await self._ensure_client()
        try:
            resp = await client.post(
                f"/api/hermes/tools/{slug}",
                json=args or {},
                headers={
                    "Authorization": f"Bearer {jwt}",
                    "Content-Type": "application/json",
                },
                timeout=DEFAULT_TIMEOUT,
            )
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes call_tool transport: {exc.__class__.__name__}"
            ) from exc
        except httpx.RequestError as exc:
            raise BridgeUnreachable(
                f"southbrook_hermes call_tool request: {exc.__class__.__name__}"
            ) from exc

        if resp.status_code >= 500:
            logger.warning(
                "southbrook_hermes call_tool slug=%s jwt=%s status=%d",
                slug, self._redact_jwt(jwt), resp.status_code,
            )
            raise BridgeUnreachable(
                f"southbrook_hermes call_tool 5xx: {resp.status_code}"
            )
        if resp.status_code >= 400:
            logger.info(
                "southbrook_hermes call_tool slug=%s jwt=%s rejected=%d",
                slug, self._redact_jwt(jwt), resp.status_code,
            )
            raise BridgeRejected(
                f"southbrook_hermes call_tool {slug} {resp.status_code}: "
                f"{resp.text[:300]}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise BridgeRejected(
                f"southbrook_hermes call_tool non-json: {exc}"
            ) from exc
        if not isinstance(data, dict):
            raise BridgeRejected(
                f"southbrook_hermes call_tool {slug} non-object result"
            )
        logger.info(
            "southbrook_hermes call_tool slug=%s jwt=%s status=%d",
            slug, self._redact_jwt(jwt), resp.status_code,
        )
        return data

    # ------------------------------------------------------------------
    # Payload mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _recommendation_type_for(rec: Dict[str, Any]) -> str:
        """Derive the Odoo-side recommendation_type from the rec's source.

        Most agent loops file generic actionable items → ``task``. The
        lead_prospector loop produces sales prospects → ``prospect``
        (which the southbrook_hermes addon's action_apply handler routes
        to ``crm.lead`` creation on approval+apply).
        """
        source = (rec.get("source") or "").lower()
        if source == "lead_prospector":
            return "prospect"
        return "task"

    @staticmethod
    def _map_to_controller_payload(rec: Dict[str, Any]) -> Dict[str, Any]:
        rec_type = SouthbrookHermesBridge._recommendation_type_for(rec)
        return {
            "name": rec.get("title") or "",
            "summary": rec.get("summary") or "",
            "recommendation_type": rec_type,
            "priority": rec.get("priority") or "normal",
            "rationale": rec.get("rationale"),
            "proposed_action": rec.get("proposed_action"),
            "payload": rec.get("payload") or {},
            "agent_run_id": (rec.get("payload") or {}).get("agent_run_id")
            if isinstance(rec.get("payload"), dict)
            else None,
            "model_provider": rec.get("llm_provider"),
            "model_name": rec.get("llm_model"),
            # Skip the in-Odoo approval boundary for prospects: the user
            # has already approved via the Hermes Console UI/WhatsApp, so
            # we can drive the rec straight to applied (which triggers
            # crm.lead creation in /odoo/crm). Generic task pushes go
            # through the normal Fabio approval gate.
            "auto_apply": rec_type == "prospect",
        }

    @staticmethod
    def _map_to_call_kw_values(rec: Dict[str, Any]) -> Dict[str, Any]:
        payload = rec.get("payload") or {}
        payload_json = json.dumps(payload, sort_keys=True, default=str) if payload else "{}"
        return {
            "name": rec.get("title") or "",
            "summary": rec.get("summary") or "",
            "recommendation_type": SouthbrookHermesBridge._recommendation_type_for(rec),
            "priority": rec.get("priority") or "normal",
            "rationale": rec.get("rationale") or False,
            "proposed_action": rec.get("proposed_action") or False,
            "payload_json": payload_json,
            "model_provider": rec.get("llm_provider") or False,
            "model_name": rec.get("llm_model") or False,
        }
