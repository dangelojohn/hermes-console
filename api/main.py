"""FastAPI app entry point for the Hermes Console API tier.

Boots the local SQLite store, the LLM provider registry, the tenant bridges,
the agent loop runner, and the outbound retry queue inside a single
:func:`lifespan` context. Routes delegate persistence to :class:`LocalStore`,
LLM calls to :class:`ProviderRegistry`, and outbound pushes to
:class:`OutboundQueue`.

Error policy:

* Write paths return **503** when :class:`LocalStore` is unavailable (the
  service is up, the store is down — the client should retry).
* The recommendation apply route returns **502** with the bridge detail when
  a bridge rejects the push synchronously. A transient (Unreachable) failure
  is queued instead and the route still returns 200 with ``queued=true``.
* All other failures fall back to FastAPI's default 500 handler.

Logging is structured JSON via a tiny custom formatter so log lines stay
machine-greppable in the QNAP container log files.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Mapping, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware

from .agent_loops import AgentEnv, AgentLoopRunner, build_enabled_loops, execute_loop
from .auth import Principal, require_auth
from .llm import LLMError, LLMRateLimited, ProviderRegistry
from .local_store import LocalStore, LocalStoreUnavailable
from .models import (
    ActionResult,
    AgentRunSummary,
    AgentTriggerResult,
    BridgesHealth,
    ChatMessage,
    ChatMessageIn,
    ChatThread,
    ChatThreadCreate,
    FlushResponse,
    HealthResponse,
    LLMHealth,
    QueueRecommendationFromMessageIn,
    QueuedPush,
    Recommendation,
    RecommendationActionIn,
    RecommendationCreate,
    RecommendationSummary,
    Settings,
    TenantStatus,
    WhatsAppHealth,
    WhatsAppInboundIn,
    WhatsAppInboundResponse,
)
from .queue import OutboundQueue
from .tenant_bridges import SouthbrookHermesBridge
from .tenant_bridges.base import TenantBridge
from .whatsapp import (
    InboundCommand,
    WhatsAppClient,
    parse_inbound_command,
    render_new_recommendation_message,
)

logger = logging.getLogger(__name__)

API_VERSION = "0.2.0"


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        out: Dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


def _configure_logging() -> None:
    root = logging.getLogger()
    if any(isinstance(h, logging.StreamHandler) and isinstance(h.formatter, _JsonFormatter) for h in root.handlers):
        return
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(logging.INFO)


def _build_bridges(settings: Settings) -> Dict[str, TenantBridge]:
    bridges: Dict[str, TenantBridge] = {}
    if settings.southbrook_hermes_enabled:
        bridges["southbrook_hermes"] = SouthbrookHermesBridge(
            url=settings.southbrook_hermes_url,
            db=settings.southbrook_hermes_db,
            user=settings.southbrook_hermes_user,
            password=settings.southbrook_hermes_password,
            api_key=settings.southbrook_hermes_api_key,
        )
    return bridges


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    _configure_logging()
    settings = Settings()  # type: ignore[call-arg]

    store = LocalStore(settings.hermes_sqlite_path)
    await store.startup()

    providers = ProviderRegistry.from_settings(settings)
    await providers.startup()

    bridges = _build_bridges(settings)
    for bridge in bridges.values():
        await bridge.startup()

    whatsapp = WhatsAppClient(
        enabled=settings.hermes_whatsapp_enabled,
        bridge_url=settings.hermes_whatsapp_bridge_url,
        shared_secret=settings.hermes_whatsapp_shared_secret,
        operator_e164=settings.hermes_whatsapp_operator,
    )
    await whatsapp.startup()

    queue = OutboundQueue(
        store=store,
        bridges=bridges,
        recommendation_fetcher=store.get_recommendation,
    )
    await queue.startup()

    loops = build_enabled_loops(settings)
    runner = AgentLoopRunner(
        loops=loops,
        env_factory=lambda: AgentEnv(
            llm=providers,
            store=store,
            settings=settings,
            logger=logger,
            notifier=_make_whatsapp_notifier(whatsapp),
        ),
    )
    await runner.startup()

    app.state.settings = settings
    app.state.store = store
    app.state.providers = providers
    app.state.bridges = bridges
    app.state.whatsapp = whatsapp
    app.state.queue = queue
    app.state.agent_runner = runner
    app.state.tenant_test_results = {}  # type: Dict[str, Dict[str, Any]]

    logger.info("hermes-console-api startup complete; version=%s", API_VERSION)
    try:
        yield
    finally:
        await runner.shutdown()
        await queue.shutdown()
        await whatsapp.shutdown()
        for bridge in bridges.values():
            await bridge.shutdown()
        await providers.shutdown()
        await store.shutdown()


def _make_whatsapp_notifier(whatsapp: WhatsAppClient):
    """Build the notifier closure handed to AgentEnv.

    The notifier is called by ``execute_loop`` after each freshly-persisted
    recommendation. It never raises — a broken notification channel must
    never poison agent runs.
    """
    async def _notify(rec: Dict[str, Any]) -> None:
        if not whatsapp.enabled or not whatsapp.operator:
            return
        try:
            body = render_new_recommendation_message(rec)
            await whatsapp.notify_operator(body)
        except Exception:  # pragma: no cover - defensive
            logger.exception("whatsapp notifier failed (suppressed)")

    return _notify


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hermes Console API",
        version=API_VERSION,
        docs_url="/api",
        openapi_url="/api/openapi.json",
        redoc_url=None,
        lifespan=lifespan,
    )

    cors_settings = Settings()  # type: ignore[call-arg]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_settings.cors_origins(),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "X-Api-Key"],
    )

    _register_routes(app)
    return app


# ---------------------------------------------------------------------------
# DI helpers
# ---------------------------------------------------------------------------


def _store(request: Request) -> LocalStore:
    return request.app.state.store


def _providers(request: Request) -> ProviderRegistry:
    return request.app.state.providers


def _bridges(request: Request) -> Mapping[str, TenantBridge]:
    return request.app.state.bridges


def _queue(request: Request) -> OutboundQueue:
    return request.app.state.queue


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _runner(request: Request) -> AgentLoopRunner:
    return request.app.state.agent_runner


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def _register_routes(app: FastAPI) -> None:

    # ---------------- Health ----------------

    @app.get("/api/health", response_model=HealthResponse)
    async def health(request: Request) -> HealthResponse:
        store = _store(request)
        providers = _providers(request)
        bridges = _bridges(request)
        queue = _queue(request)
        settings = _settings(request)

        sqlite_ok = await store.ping()
        llm_status = await providers.health()
        bridges_status = {"southbrook_hermes": "disabled"}
        if "southbrook_hermes" in bridges:
            try:
                bridges_status["southbrook_hermes"] = await bridges[
                    "southbrook_hermes"
                ].health()
            except Exception:  # pragma: no cover - defensive
                bridges_status["southbrook_hermes"] = "unreachable"

        depth = await queue.depth() if sqlite_ok else 0

        # Compose a runtime-aware llm_disabled_reason that surfaces both
        # config-time issues (settings.llm_disabled_reason populated when
        # a provider isn't configured) AND runtime degradation (a provider
        # is configured but rate-limited or unreachable right now).
        reasons: list[str] = []
        if settings.llm_disabled_reason:
            reasons.append(settings.llm_disabled_reason)
        for name in ("openai", "hermes_harness", "anthropic"):
            st = llm_status.get(name)
            if st == "rate_limited":
                reasons.append(
                    f"{name}: rate-limited (quota window — retries should "
                    "recover within ~1 minute)."
                )
            elif st == "unavailable":
                reasons.append(
                    f"{name}: unavailable (probe failed — check provider "
                    "status, network, or API key validity)."
                )
        composed_reason = " ".join(reasons) if reasons else ""

        whatsapp_status = "disabled"
        whatsapp_client: Optional[WhatsAppClient] = getattr(
            request.app.state, "whatsapp", None
        )
        if whatsapp_client is not None:
            try:
                whatsapp_status = await whatsapp_client.health()
            except Exception:  # pragma: no cover - defensive
                whatsapp_status = "unreachable"

        return HealthResponse(
            api="ok",
            sqlite="ok" if sqlite_ok else "down",
            llm=LLMHealth(
                openai=llm_status.get("openai", "disabled"),  # type: ignore[arg-type]
                hermes_harness=llm_status.get("hermes_harness", "disabled"),  # type: ignore[arg-type]
                anthropic=llm_status.get("anthropic", "disabled"),  # type: ignore[arg-type]
            ),
            bridges=BridgesHealth(
                southbrook_hermes=bridges_status["southbrook_hermes"],  # type: ignore[arg-type]
            ),
            whatsapp=WhatsAppHealth(status=whatsapp_status),  # type: ignore[arg-type]
            queue_depth=depth,
            tenant_label=settings.hermes_tenant_label,
            tenant_icon=settings.hermes_tenant_icon,
            public_url=settings.hermes_public_url,
            version=API_VERSION,
            llm_disabled_reason=composed_reason,
        )

    # ---------------- Recommendations ----------------

    @app.get("/api/recommendations", response_model=List[RecommendationSummary])
    async def list_recommendations(
        request: Request,
        _: Principal = Depends(require_auth),
        state: Optional[str] = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
    ) -> List[RecommendationSummary]:
        rows = await _store(request).list_recommendations(
            state=state, limit=limit, offset=offset
        )
        return [RecommendationSummary(**row) for row in rows]

    @app.get("/api/recommendations/{rec_id}", response_model=Recommendation)
    async def get_recommendation(
        request: Request,
        rec_id: int,
        _: Principal = Depends(require_auth),
    ) -> Recommendation:
        row = await _store(request).get_recommendation(rec_id)
        if row is None:
            raise HTTPException(status_code=404, detail="recommendation not found")
        return Recommendation(**row)

    @app.post(
        "/api/recommendations",
        response_model=Recommendation,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_recommendation(
        request: Request,
        body: RecommendationCreate,
        _: Principal = Depends(require_auth),
    ) -> Recommendation:
        try:
            row = await _store(request).create_recommendation(
                {**body.model_dump(), "state": "ready"}
            )
        except LocalStoreUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"local store unavailable: {exc}",
            ) from exc
        return Recommendation(**row)

    async def _transition(
        request: Request,
        rec_id: int,
        new_state: str,
        body: Optional[RecommendationActionIn],
    ) -> ActionResult:
        body = body or RecommendationActionIn()
        try:
            updated = await _store(request).update_recommendation_state(
                rec_id,
                new_state,
                reviewer_note=body.reviewer_note,
            )
        except LocalStoreUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"local store unavailable: {exc}",
            ) from exc
        if updated is None:
            raise HTTPException(status_code=404, detail="recommendation not found")
        return ActionResult(ok=True, new_state=updated["state"])  # type: ignore[arg-type]

    @app.post("/api/recommendations/{rec_id}/approve", response_model=ActionResult)
    async def approve(
        request: Request,
        rec_id: int,
        body: Optional[RecommendationActionIn] = None,
        _: Principal = Depends(require_auth),
    ) -> ActionResult:
        return await _transition(request, rec_id, "approved", body)

    @app.post("/api/recommendations/{rec_id}/reject", response_model=ActionResult)
    async def reject(
        request: Request,
        rec_id: int,
        body: Optional[RecommendationActionIn] = None,
        _: Principal = Depends(require_auth),
    ) -> ActionResult:
        return await _transition(request, rec_id, "rejected", body)

    @app.post("/api/recommendations/{rec_id}/apply", response_model=ActionResult)
    async def apply(
        request: Request,
        rec_id: int,
        body: Optional[RecommendationActionIn] = None,
        _: Principal = Depends(require_auth),
    ) -> ActionResult:
        body = body or RecommendationActionIn()
        store = _store(request)
        rec = await store.get_recommendation(rec_id)
        if rec is None:
            raise HTTPException(status_code=404, detail="recommendation not found")

        try:
            updated = await store.update_recommendation_state(rec_id, "applied")
        except LocalStoreUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"local store unavailable: {exc}",
            ) from exc
        assert updated is not None

        # Decide which bridge (if any) to push to.
        bridge_name = body.tenant or rec.get("tenant_hint")
        bridges = _bridges(request)
        if not bridge_name:
            # Audit-only — no bridges fired.
            return ActionResult(ok=True, new_state="applied")
        if bridge_name not in bridges:
            # Configured tenant we don't know — still 200 + audit, but flag.
            return ActionResult(
                ok=True,
                new_state="applied",
                error=f"bridge {bridge_name!r} not configured",
            )

        result = await _queue(request).deliver_now(
            recommendation_id=rec_id, bridge_name=bridge_name
        )
        status_val = result["status"]
        if status_val == "succeeded":
            return ActionResult(
                ok=True,
                new_state="applied",
                bridge_push_id=result["bridge_push_id"],
                bridge_status="succeeded",
            )
        if status_val == "pending":
            return ActionResult(
                ok=True,
                new_state="applied",
                bridge_push_id=result["bridge_push_id"],
                bridge_status="pending",
                queued=True,
                error=result.get("error"),
            )
        # status == 'failed' — non-retry-able. The local apply still stuck;
        # surface 502 so the operator sees the bridge problem clearly.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "ok": False,
                "new_state": "applied",
                "bridge_push_id": result["bridge_push_id"],
                "bridge_status": "failed",
                "error": result.get("error"),
            },
        )

    # ---------------- Chat ----------------

    @app.get("/api/chat/threads", response_model=List[ChatThread])
    async def list_threads(
        request: Request,
        _: Principal = Depends(require_auth),
        limit: int = Query(default=50, ge=1, le=200),
    ) -> List[ChatThread]:
        rows = await _store(request).list_threads(limit=limit)
        return [ChatThread(**r) for r in rows]

    @app.post(
        "/api/chat/threads",
        response_model=ChatThread,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_thread(
        request: Request,
        body: ChatThreadCreate,
        _: Principal = Depends(require_auth),
    ) -> ChatThread:
        settings = _settings(request)
        providers = _providers(request)
        provider_name = body.provider or settings.hermes_primary_provider
        if not providers.has(provider_name):
            raise HTTPException(
                status_code=400,
                detail=f"provider {provider_name!r} not configured",
            )
        client = providers.get(provider_name)
        model = body.model or client.default_model or ""
        try:
            row = await _store(request).create_thread(
                title=body.title, provider=provider_name, model=model
            )
        except LocalStoreUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"local store unavailable: {exc}",
            ) from exc
        return ChatThread(**row)

    @app.get(
        "/api/chat/threads/{thread_id}/messages",
        response_model=List[ChatMessage],
    )
    async def list_messages(
        request: Request,
        thread_id: int,
        _: Principal = Depends(require_auth),
    ) -> List[ChatMessage]:
        store = _store(request)
        if await store.get_thread(thread_id) is None:
            raise HTTPException(status_code=404, detail="thread not found")
        rows = await store.list_messages(thread_id)
        return [ChatMessage(**r) for r in rows]

    @app.post(
        "/api/chat/threads/{thread_id}/messages",
        response_model=ChatMessage,
        status_code=status.HTTP_201_CREATED,
    )
    async def post_message(
        request: Request,
        thread_id: int,
        body: ChatMessageIn,
        _: Principal = Depends(require_auth),
    ) -> ChatMessage:
        # TODO: switch to SSE streaming for the assistant reply once the UI
        # supports it. For MVP we return the persisted assistant message as a
        # plain JSON response.
        store = _store(request)
        thread = await store.get_thread(thread_id)
        if thread is None:
            raise HTTPException(status_code=404, detail="thread not found")

        provider_name = body.provider or thread["provider"]
        model = body.model or thread["model"]
        providers = _providers(request)
        if not providers.has(provider_name):
            raise HTTPException(
                status_code=400,
                detail=f"provider {provider_name!r} not configured",
            )
        client = providers.get(provider_name)

        try:
            await store.add_message(
                thread_id=thread_id,
                role="user",
                content=body.content,
                provider=provider_name,
                model=model,
            )
        except LocalStoreUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"local store unavailable: {exc}",
            ) from exc

        history = await store.list_messages(thread_id)
        messages = [{"role": m["role"], "content": m["content"]} for m in history]

        try:
            resp = await client.chat(messages, model=model or None)
        except LLMRateLimited as exc:
            # Surface 429 to the client so the UI can show a clean
            # "rate-limited — wait a minute" message instead of a
            # generic 502 gateway error. Important for free-tier
            # providers like Gemini (20 req/min on 2.5-flash).
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"llm rate limited: {exc}",
            ) from exc
        except LLMError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"llm error: {exc}",
            ) from exc

        try:
            assistant_msg = await store.add_message(
                thread_id=thread_id,
                role="assistant",
                content=resp.content,
                provider=provider_name,
                model=resp.model,
                tokens_in=resp.usage.get("prompt_tokens"),
                tokens_out=resp.usage.get("completion_tokens"),
            )
        except LocalStoreUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"local store unavailable: {exc}",
            ) from exc
        return ChatMessage(**assistant_msg)

    @app.post(
        "/api/chat/threads/{thread_id}/messages/{msg_id}/queue-recommendation",
        response_model=Recommendation,
        status_code=status.HTTP_201_CREATED,
    )
    async def queue_recommendation_from_message(
        request: Request,
        thread_id: int,
        msg_id: int,
        body: QueueRecommendationFromMessageIn,
        _: Principal = Depends(require_auth),
    ) -> Recommendation:
        store = _store(request)
        msg = await store.get_message(msg_id)
        if msg is None or msg["thread_id"] != thread_id:
            raise HTTPException(status_code=404, detail="message not found in thread")
        if msg["role"] != "assistant":
            raise HTTPException(
                status_code=400,
                detail="only assistant messages can be queued as recommendations",
            )

        title = body.title or (msg["content"] or "")[:80].strip() or "Untitled"
        try:
            rec = await store.create_recommendation(
                {
                    "title": title,
                    "summary": body.summary or (msg["content"] or "")[:240],
                    "rationale": msg["content"],
                    "priority": body.priority,
                    "source": "chat",
                    "tenant_hint": body.tenant_hint,
                    "llm_provider": msg["provider"],
                    "llm_model": msg["model"],
                    "state": "ready",
                }
            )
            await store.link_message_recommendation(
                message_id=msg_id, recommendation_id=rec["id"]
            )
        except LocalStoreUnavailable as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"local store unavailable: {exc}",
            ) from exc
        return Recommendation(**rec)

    # ---------------- Tenant bridges ----------------

    @app.get("/api/tenants", response_model=List[TenantStatus])
    async def list_tenants(
        request: Request,
        _: Principal = Depends(require_auth),
    ) -> List[TenantStatus]:
        settings = _settings(request)
        bridges = _bridges(request)
        results: List[TenantStatus] = []

        known = {"southbrook_hermes": settings.southbrook_hermes_enabled}
        test_results = request.app.state.tenant_test_results
        for name, enabled in known.items():
            last = test_results.get(name, {})
            results.append(
                TenantStatus(
                    name=name,
                    enabled=enabled and name in bridges,
                    last_test_at=last.get("at"),
                    last_test_status=last.get("status"),
                    last_error=last.get("error"),
                )
            )
        return results

    @app.post("/api/tenants/{name}/test", response_model=TenantStatus)
    async def test_tenant(
        request: Request,
        name: str,
        _: Principal = Depends(require_auth),
    ) -> TenantStatus:
        bridges = _bridges(request)
        if name not in bridges:
            raise HTTPException(
                status_code=404, detail=f"bridge {name!r} not configured"
            )
        bridge = bridges[name]
        status_str = "ok"
        err: Optional[str] = None
        try:
            health_str = await bridge.health()
            if health_str != "ok":
                status_str = "unreachable"
                err = health_str
        except Exception as exc:  # pragma: no cover - defensive
            status_str = "unreachable"
            err = f"{exc.__class__.__name__}: {exc}"

        now = datetime.now(tz=timezone.utc)
        request.app.state.tenant_test_results[name] = {
            "at": now,
            "status": status_str,
            "error": err,
        }
        return TenantStatus(
            name=name,
            enabled=True,
            last_test_at=now,
            last_test_status=status_str,  # type: ignore[arg-type]
            last_error=err,
        )

    # ---------------- Agents ----------------

    @app.get("/api/agents", response_model=List[AgentRunSummary])
    async def list_agents(
        request: Request,
        _: Principal = Depends(require_auth),
    ) -> List[AgentRunSummary]:
        runner = _runner(request)
        store = _store(request)
        out: List[AgentRunSummary] = []
        for name in runner.loop_names():
            summary = await store.agent_summary(name)
            loop = runner.find(name)
            out.append(
                AgentRunSummary(
                    name=name,
                    interval_seconds=loop.interval_seconds if loop else None,
                    last_run_at=summary.get("last_run_at"),
                    last_run_status=summary.get("last_run_status"),
                    recommendation_count=summary.get("recommendation_count", 0),
                )
            )
        return out

    @app.post("/api/agents/{name}/trigger", response_model=AgentTriggerResult)
    async def trigger_agent(
        request: Request,
        name: str,
        _: Principal = Depends(require_auth),
    ) -> AgentTriggerResult:
        runner = _runner(request)
        try:
            result = await runner.trigger(name)
        except KeyError:
            raise HTTPException(
                status_code=404, detail=f"agent {name!r} not enabled"
            ) from None
        return AgentTriggerResult(
            ok=result["status"] == "ok",
            agent=name,
            recommendations_created=result["recommendations_created"],
            status=result["status"],
            error=result.get("error_message"),
        )

    # ---------------- Outbound queue ----------------

    @app.get("/api/queue", response_model=List[QueuedPush])
    async def list_queue(
        request: Request,
        _: Principal = Depends(require_auth),
    ) -> List[QueuedPush]:
        return await _queue(request).list_all()

    @app.post("/api/queue/flush", response_model=FlushResponse)
    async def flush_queue(
        request: Request,
        _: Principal = Depends(require_auth),
    ) -> FlushResponse:
        result = await _queue(request).flush()
        return FlushResponse(**result)

    # ---------------- WhatsApp ----------------

    @app.post("/api/whatsapp/inbound", response_model=WhatsAppInboundResponse)
    async def whatsapp_inbound(
        request: Request,
        body: WhatsAppInboundIn,
    ) -> WhatsAppInboundResponse:
        """Receive a message from the hermes-whatsapp sidecar.

        Auth: ``X-Hermes-Token`` matching ``HERMES_WHATSAPP_SHARED_SECRET``.
        Sender allow-listing is done at the sidecar (it forwards only from
        ``HERMES_WHATSAPP_ALLOWED_SENDERS``), but the endpoint also re-checks
        against the configured operator number — defence in depth.

        Returns a structured response describing what Hermes did so the
        sidecar can echo a reply back to the user.
        """
        settings = _settings(request)
        provided = request.headers.get("X-Hermes-Token", "")
        if (
            not settings.hermes_whatsapp_shared_secret
            or provided != settings.hermes_whatsapp_shared_secret
        ):
            raise HTTPException(status_code=401, detail="unauthorized")

        # Defence-in-depth: only accept commands from the configured operator.
        # Anything else is filed as chat-without-action.
        from_e164 = body.from_.lstrip("+")
        operator = settings.hermes_whatsapp_operator.lstrip("+")
        if not operator or from_e164 != operator:
            return WhatsAppInboundResponse(
                handled=False,
                kind="unauthorized",
                reply=None,
            )

        cmd: InboundCommand = parse_inbound_command(body.body)
        store = _store(request)
        whatsapp_client: Optional[WhatsAppClient] = getattr(
            request.app.state, "whatsapp", None
        )

        if cmd.kind in ("approve", "reject") and cmd.rec_id is not None:
            new_state = "approved" if cmd.kind == "approve" else "rejected"
            try:
                updated = await store.update_recommendation_state(
                    cmd.rec_id,
                    new_state,
                    reviewer_note=f"via WhatsApp: {cmd.text[:200]}",
                )
            except LocalStoreUnavailable as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"local store unavailable: {exc}",
                ) from exc
            if updated is None:
                reply = f"❓ recommendation #{cmd.rec_id} not found"
                if whatsapp_client is not None:
                    await whatsapp_client.send(body.from_, reply)
                return WhatsAppInboundResponse(
                    handled=False,
                    kind="unknown_rec",
                    rec_id=cmd.rec_id,
                    reply=reply,
                )
            verb = "✅ approved" if cmd.kind == "approve" else "🚫 rejected"
            reply = f"{verb} #{cmd.rec_id} — {updated.get('title', '').strip()[:80]}"
            if whatsapp_client is not None:
                await whatsapp_client.send(body.from_, reply)
            return WhatsAppInboundResponse(
                handled=True,
                kind=cmd.kind,  # type: ignore[arg-type]
                rec_id=cmd.rec_id,
                reply=reply,
            )

        # Free-form text: not yet wired into the chat thread surface. Echo
        # a usage hint so the user knows what commands are supported. The
        # chat thread integration is a follow-on once the approval loop is
        # confirmed working end-to-end.
        reply = (
            "Hermes here. Reply `approve <id>` or `reject <id>` to act on a "
            "recommendation (e.g. `approve 47`). Free-form chat is not yet "
            "wired."
        )
        if whatsapp_client is not None and cmd.text:
            await whatsapp_client.send(body.from_, reply)
        return WhatsAppInboundResponse(
            handled=False,
            kind="chat",
            reply=reply,
        )


app = create_app()
