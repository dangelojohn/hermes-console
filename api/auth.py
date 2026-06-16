"""Authentication hook.

For this iteration, Cloudflare Access OTP gates the upstream tunnel so no
per-request API key is required. This module exposes a single FastAPI dependency
``require_auth`` that currently returns the anonymous principal but is wired into
every protected endpoint so we can swap in an API-key or JWT check later without
touching every route.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Principal:
    """Represents the identity making a request.

    For now, every request resolves to the anonymous Cloudflare-gated principal.
    Future revisions can populate ``api_key_id`` / ``user_email`` from the
    incoming ``X-Api-Key`` or ``Cf-Access-Jwt-Assertion`` header.
    """

    api_key_id: Optional[str] = None
    user_email: Optional[str] = None
    is_anonymous: bool = True


async def require_auth(
    x_api_key: Optional[str] = Header(default=None, alias="X-Api-Key"),
    cf_access_jwt: Optional[str] = Header(default=None, alias="Cf-Access-Jwt-Assertion"),
) -> Principal:
    """Resolve the request principal.

    Iteration 1: no enforcement — Cloudflare Access gates the tunnel upstream.
    The header arguments are declared so that future iterations can switch to
    enforcing API-key or Cf-Access JWT validation without breaking callers.
    """

    if x_api_key:
        # Placeholder: future iteration will validate against a stored hash.
        logger.debug("X-Api-Key header present; ignored in this iteration")

    if cf_access_jwt:
        # Placeholder: future iteration will verify the JWT signature and pull
        # the user email from the claims.
        logger.debug("Cf-Access-Jwt-Assertion header present; ignored in this iteration")

    return Principal()


def _reject(message: str) -> HTTPException:
    """Helper kept so future implementations have a consistent rejection shape."""

    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=message)
