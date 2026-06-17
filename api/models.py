"""Pydantic models for request/response payloads + Settings.

Kept separate from the route handlers so they can be imported by tests and
potentially generated into a client SDK. The Settings class fails fast on
startup when a required env var is missing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Settings (env vars)
# ---------------------------------------------------------------------------


ProviderName = Literal["openai", "hermes_harness", "anthropic"]


class Settings(BaseSettings):
    """Service configuration sourced from env vars.

    Required env vars are validated at startup. The provider keys are
    conditionally required — OPENAI_API_KEY is mandatory only when
    HERMES_PRIMARY_PROVIDER=openai, and the SOUTHBROOK_HERMES_* block is
    mandatory only when SOUTHBROOK_HERMES_ENABLED=true.
    """

    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    # --- LLM providers ---
    hermes_primary_provider: ProviderName = Field(
        default="openai", alias="HERMES_PRIMARY_PROVIDER"
    )

    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    openai_base_url: str = Field(
        default="https://api.openai.com/v1", alias="OPENAI_BASE_URL"
    )
    openai_default_model: str = Field(default="gpt-4o", alias="OPENAI_DEFAULT_MODEL")

    hermes_harness_api_key: str = Field(default="", alias="HERMES_HARNESS_API_KEY")
    hermes_harness_base_url: str = Field(default="", alias="HERMES_HARNESS_BASE_URL")
    hermes_harness_default_model: str = Field(
        default="", alias="HERMES_HARNESS_DEFAULT_MODEL"
    )

    # --- Anthropic (Claude API, native /v1/messages — not OpenAI-compat) ---
    # Optional; provider is registered only when ANTHROPIC_API_KEY is set.
    # Default model defers to api/llm.py's claude-api skill guidance.
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com/v1", alias="ANTHROPIC_BASE_URL"
    )
    anthropic_default_model: str = Field(
        default="claude-opus-4-8", alias="ANTHROPIC_DEFAULT_MODEL"
    )
    anthropic_default_max_tokens: int = Field(
        default=4096, alias="ANTHROPIC_DEFAULT_MAX_TOKENS"
    )

    # --- WhatsApp notification + command channel ---
    # Disabled by default so existing deploys are unchanged. When enabled,
    # hermes-whatsapp sidecar must be running on hermes-net and reachable at
    # the bridge URL below; otherwise sends quietly no-op.
    hermes_whatsapp_enabled: bool = Field(
        default=False, alias="HERMES_WHATSAPP_ENABLED"
    )
    hermes_whatsapp_bridge_url: str = Field(
        default="http://hermes-whatsapp:8901", alias="HERMES_WHATSAPP_BRIDGE_URL"
    )
    hermes_whatsapp_shared_secret: str = Field(
        default="", alias="HERMES_WHATSAPP_SHARED_SECRET"
    )
    # E.164 without "+" — the single human operator that recommendation
    # notifications go to AND the only sender allowed to issue commands.
    hermes_whatsapp_operator: str = Field(
        default="", alias="HERMES_WHATSAPP_OPERATOR"
    )

    # --- Southbrook tenant bridge ---
    southbrook_hermes_enabled: bool = Field(
        default=False, alias="SOUTHBROOK_HERMES_ENABLED"
    )
    southbrook_hermes_url: str = Field(default="", alias="SOUTHBROOK_HERMES_URL")
    southbrook_hermes_db: str = Field(default="", alias="SOUTHBROOK_HERMES_DB")
    southbrook_hermes_user: str = Field(default="", alias="SOUTHBROOK_HERMES_USER")
    southbrook_hermes_password: str = Field(
        default="", alias="SOUTHBROOK_HERMES_PASSWORD"
    )
    southbrook_hermes_api_key: str = Field(
        default="", alias="SOUTHBROOK_HERMES_API_KEY"
    )

    # --- Home Assistant tenant bridge ---
    # When enabled, approved recommendations get pushed to a Home Assistant
    # instance as persistent notifications (default) or via a custom HA
    # service. Optionally read a small allowlist of HA entity states for
    # agent-loop context. Long-lived access token only; never echoed.
    home_assistant_enabled: bool = Field(
        default=False, alias="HOME_ASSISTANT_ENABLED"
    )
    home_assistant_url: str = Field(default="", alias="HOME_ASSISTANT_URL")
    home_assistant_token: str = Field(default="", alias="HOME_ASSISTANT_TOKEN")
    home_assistant_push_service: str = Field(
        default="", alias="HOME_ASSISTANT_PUSH_SERVICE"
    )
    # Comma-separated; e.g. "sensor.office_temperature,binary_sensor.front_door"
    home_assistant_context_entities: str = Field(
        default="", alias="HOME_ASSISTANT_CONTEXT_ENTITIES"
    )

    # --- Cloudflare API (read-only via hermes_cloudflare_* MCP tools) ---
    # Generate at https://dash.cloudflare.com/profile/api-tokens with the
    # least-privilege scopes: Zone:Zone:Read, Zone:DNS:Read,
    # Account:Cloudflare Tunnel:Read, Account:Access:Apps and Policies:Read.
    # account_id enables the tunnel + Access tools.
    cloudflare_api_token: str = Field(
        default="", alias="CLOUDFLARE_API_TOKEN"
    )
    cloudflare_account_id: str = Field(
        default="", alias="CLOUDFLARE_ACCOUNT_ID"
    )

    # --- API / display ---
    hermes_sqlite_path: str = Field(
        default="/data/hermes.sqlite", alias="HERMES_SQLITE_PATH"
    )
    hermes_tenant_label: str = Field(default="Hermes", alias="HERMES_TENANT_LABEL")
    hermes_tenant_icon: str = Field(
        default="\U0001F985", alias="HERMES_TENANT_ICON"
    )  # eagle
    hermes_public_url: str = Field(default="", alias="HERMES_PUBLIC_URL")

    # --- Agent loops ---
    hermes_agent_loops: str = Field(
        default="platform_health", alias="HERMES_AGENT_LOOPS"
    )
    hermes_platform_health_interval: int = Field(
        default=900, alias="HERMES_PLATFORM_HEALTH_INTERVAL"
    )

    # Backup-health loop: reads the nightly-backup status JSON and emits a
    # recommendation when the last run failed or is older than the
    # max-age threshold. Defaults to a 1-hour poll cadence; status file
    # path matches the mount documented in backup/README.md.
    hermes_backup_health_interval: int = Field(
        default=3600, alias="HERMES_BACKUP_HEALTH_INTERVAL"
    )
    hermes_backup_status_path: str = Field(
        default="/data/backup-status/last-run.json",
        alias="HERMES_BACKUP_STATUS_PATH",
    )
    hermes_backup_max_age_hours: int = Field(
        default=26, alias="HERMES_BACKUP_MAX_AGE_HOURS"
    )

    cors_allow_origins: str = Field(
        default="https://hermes.odooiq.com",
        alias="HERMES_CORS_ALLOW_ORIGINS",
    )

    # Degraded-mode flags surfaced by the validator. When True, certain
    # endpoints (notably /api/chat/*) return 503 with a clear "LLM not
    # configured" message instead of the API refusing to boot at all.
    # The UI's StatusBanner reads these via /api/health and amber-flags
    # the affected provider pills.
    llm_disabled_openai: bool = Field(default=False, exclude=True)
    llm_disabled_hermes_harness: bool = Field(default=False, exclude=True)
    llm_disabled_anthropic: bool = Field(default=False, exclude=True)
    llm_disabled_reason: str = Field(default="", exclude=True)

    @model_validator(mode="after")
    def _validate_conditional_requirements(self) -> "Settings":
        # Soft-validation: missing LLM credentials degrade chat to 503
        # rather than crashing the API. The UI and queue/recommendation/
        # tenant endpoints all keep working — operators can populate the
        # key later without redeploying the container.
        if self.hermes_primary_provider == "openai" and not self.openai_api_key:
            self.llm_disabled_openai = True
            self.llm_disabled_reason = (
                "OPENAI_API_KEY is blank. Chat is disabled until the key is "
                "set in .env and the api container is restarted."
            )
        if self.hermes_primary_provider == "hermes_harness":
            if not self.hermes_harness_api_key or not self.hermes_harness_base_url:
                self.llm_disabled_hermes_harness = True
                self.llm_disabled_reason = (
                    "HERMES_HARNESS_API_KEY and HERMES_HARNESS_BASE_URL are "
                    "both required when primary provider is hermes_harness. "
                    "Chat is disabled until both are set."
                )
        if self.hermes_primary_provider == "anthropic" and not self.anthropic_api_key:
            self.llm_disabled_anthropic = True
            self.llm_disabled_reason = (
                "ANTHROPIC_API_KEY is blank. Chat is disabled until the key "
                "is set in .env and the api container is restarted."
            )
        # Harness key supplied without a base URL is still a misconfiguration
        # — but treat as degraded rather than fatal.
        if self.hermes_harness_api_key and not self.hermes_harness_base_url:
            self.llm_disabled_hermes_harness = True
            self.llm_disabled_reason = (
                "HERMES_HARNESS_BASE_URL is required when "
                "HERMES_HARNESS_API_KEY is set. Harness provider disabled."
            )
        # Southbrook bridge: when enabled, all 4 connection fields must be set.
        if self.southbrook_hermes_enabled:
            missing = [
                name
                for name, val in (
                    ("SOUTHBROOK_HERMES_URL", self.southbrook_hermes_url),
                    ("SOUTHBROOK_HERMES_DB", self.southbrook_hermes_db),
                    ("SOUTHBROOK_HERMES_USER", self.southbrook_hermes_user),
                    ("SOUTHBROOK_HERMES_PASSWORD", self.southbrook_hermes_password),
                )
                if not val
            ]
            if missing:
                raise ValueError(
                    f"Southbrook bridge enabled but missing: {', '.join(missing)}"
                )
        # Home Assistant bridge: when enabled, url + token are mandatory.
        if self.home_assistant_enabled:
            missing_ha = [
                name
                for name, val in (
                    ("HOME_ASSISTANT_URL", self.home_assistant_url),
                    ("HOME_ASSISTANT_TOKEN", self.home_assistant_token),
                )
                if not val
            ]
            if missing_ha:
                raise ValueError(
                    f"Home Assistant bridge enabled but missing: {', '.join(missing_ha)}"
                )
        return self

    @field_validator("hermes_agent_loops")
    @classmethod
    def _normalise_loops(cls, v: str) -> str:
        return (v or "").strip()

    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]

    def enabled_agent_loops(self) -> List[str]:
        raw = self.hermes_agent_loops.strip().lower()
        if not raw or raw == "none":
            return []
        return [n.strip() for n in raw.split(",") if n.strip()]


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


RecommendationState = Literal["draft", "ready", "approved", "rejected", "applied"]
Priority = Literal["low", "normal", "high", "blocker"]
ChatRole = Literal["user", "assistant", "system", "tool"]
BridgeStatus = Literal["pending", "sending", "succeeded", "failed"]
AgentRunStatus = Literal["ok", "error"]


class RecommendationSummary(BaseModel):
    id: int
    state: RecommendationState
    title: str
    summary: Optional[str] = None
    priority: Priority = "normal"
    source: Optional[str] = None
    tenant_hint: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    created_at: datetime
    reviewed_at: Optional[datetime] = None
    applied_at: Optional[datetime] = None


class Recommendation(RecommendationSummary):
    rationale: Optional[str] = None
    proposed_action: Optional[str] = None
    payload: Optional[Any] = None
    reviewer_id: Optional[str] = None


class ChatThread(BaseModel):
    id: int
    title: Optional[str] = None
    provider: ProviderName
    model: str
    created_at: datetime
    updated_at: datetime


class ChatMessage(BaseModel):
    id: int
    thread_id: int
    role: ChatRole
    content: str
    provider: Optional[str] = None
    model: Optional[str] = None
    tokens_in: Optional[int] = None
    tokens_out: Optional[int] = None
    spawned_recommendation_id: Optional[int] = None
    created_at: datetime


class AgentRunSummary(BaseModel):
    name: str
    interval_seconds: Optional[int] = None
    last_run_at: Optional[datetime] = None
    last_run_status: Optional[AgentRunStatus] = None
    recommendation_count: int = 0


class TenantStatus(BaseModel):
    name: str
    enabled: bool
    last_test_at: Optional[datetime] = None
    last_test_status: Optional[Literal["ok", "unreachable", "rejected"]] = None
    last_error: Optional[str] = None


class QueuedPush(BaseModel):
    id: int
    recommendation_id: int
    bridge_name: str
    status: BridgeStatus
    attempts: int
    last_error: Optional[str] = None
    queued_at: datetime
    last_attempt_at: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Request payloads
# ---------------------------------------------------------------------------


class RecommendationCreate(BaseModel):
    title: str
    summary: Optional[str] = None
    rationale: Optional[str] = None
    proposed_action: Optional[str] = None
    priority: Priority = "normal"
    source: Optional[str] = None
    tenant_hint: Optional[str] = None
    payload: Optional[Any] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None


class RecommendationActionIn(BaseModel):
    reviewer_note: Optional[str] = None
    tenant: Optional[str] = None  # only used by /apply


def _empty_to_none(v):
    """Treat empty-string provider/model as 'use the default'.

    The UI's ModelPicker historically emitted `provider: ""` for the
    'Default' option, which Pydantic's Literal validator rejected with
    422. This validator collapses empty strings to None so the endpoint
    can fall back to thread.provider / settings.hermes_primary_provider.
    """
    if isinstance(v, str) and v == "":
        return None
    return v


class ChatThreadCreate(BaseModel):
    title: Optional[str] = None
    provider: Optional[ProviderName] = None
    model: Optional[str] = None

    _normalize_provider = field_validator("provider", mode="before")(_empty_to_none)
    _normalize_model = field_validator("model", mode="before")(_empty_to_none)


class ChatMessageIn(BaseModel):
    content: str
    provider: Optional[ProviderName] = None
    model: Optional[str] = None

    _normalize_provider = field_validator("provider", mode="before")(_empty_to_none)
    _normalize_model = field_validator("model", mode="before")(_empty_to_none)


class QueueRecommendationFromMessageIn(BaseModel):
    title: Optional[str] = None
    priority: Priority = "normal"
    summary: Optional[str] = None
    tenant_hint: Optional[str] = None


# ---------------------------------------------------------------------------
# Response payloads
# ---------------------------------------------------------------------------


class ActionResult(BaseModel):
    ok: bool
    new_state: RecommendationState
    bridge_push_id: Optional[int] = None
    bridge_status: Optional[BridgeStatus] = None
    queued: bool = False
    error: Optional[str] = None


class LLMHealth(BaseModel):
    # 'rate_limited' added to surface free-tier quota exhaustion distinctly
    # from outright unavailability; the UI flips the pill to amber rather
    # than red and shows a wait-time hint instead of an alarming banner.
    openai: Literal["ok", "unavailable", "disabled", "rate_limited"]
    hermes_harness: Literal["ok", "unavailable", "disabled", "rate_limited"]
    anthropic: Literal["ok", "unavailable", "disabled", "rate_limited"] = "disabled"


class BridgesHealth(BaseModel):
    southbrook_hermes: Literal["ok", "disabled", "unreachable"]
    home_assistant: Literal["ok", "disabled", "unreachable"] = "disabled"


class WhatsAppHealth(BaseModel):
    """Status of the hermes-whatsapp sidecar bridge.

    ``ok`` requires both the bridge HTTP endpoint reachable AND the WhatsApp
    session linked (QR scanned). ``unreachable`` covers both transport and
    "linked but not initialised" — surface a single state to the UI.
    """
    status: Literal["ok", "unreachable", "disabled"] = "disabled"


class WhatsAppInboundIn(BaseModel):
    """Payload posted by hermes-whatsapp when a message arrives."""
    from_: str = Field(alias="from")
    body: str
    received_at: Optional[str] = None
    message_id: Optional[str] = None
    has_media: bool = False

    model_config = {"populate_by_name": True}


class WhatsAppInboundResponse(BaseModel):
    """Echoed back to the bridge so the operator sees what Hermes did.

    The bridge optionally sends ``reply`` back to the user; ``handled``
    distinguishes "Hermes acted on it" from "Hermes filed it as chat".
    """
    handled: bool
    kind: Literal["approve", "reject", "chat", "unknown_rec", "unauthorized"]
    rec_id: Optional[int] = None
    reply: Optional[str] = None


class HealthResponse(BaseModel):
    api: Literal["ok"]
    sqlite: Literal["ok", "down"]
    llm: LLMHealth
    bridges: BridgesHealth
    whatsapp: WhatsAppHealth = WhatsAppHealth()
    queue_depth: int
    tenant_label: str
    tenant_icon: str
    public_url: str
    version: str
    # If chat is unavailable for a configuration reason (e.g. blank API key),
    # this carries the human-readable explanation. Surfaced by the UI's
    # StatusBanner as an amber tooltip on the affected provider pill.
    llm_disabled_reason: str = ""


class FlushResponse(BaseModel):
    flushed: int
    succeeded: int
    failed: int
    still_pending: int


class AgentTriggerResult(BaseModel):
    ok: bool
    agent: str
    recommendations_created: List[int]
    status: AgentRunStatus
    error: Optional[str] = None
