"""Thin Reolink local-LAN API client for the hermes_reolink_* MCP tools.

Talks directly to Reolink cameras on the LAN (no Reolink cloud account,
no app-side login). Read-only: device info, motion state, snapshot URL,
encoder/ISP settings, hard-drive/SD-card state.

Reolink cameras expose a JSON-RPC-ish API at ``POST /cgi-bin/api.cgi``.
The Login command returns a token; subsequent commands carry it via
``?token=<value>`` on the URL. Tokens last ~1 hour; we re-login when
the server returns ``-1 / "Please login first"``.

Auth: per-camera username + password. Password NEVER leaves this module
(the redactor already scrubs Reolink-style passwords from audit rows
generically — see api/mcp/redaction.py).

Hermes does NOT stream video. Video access stays in the camera app /
HA / NVR — this module is for state introspection only.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("api.mcp.clients.reolink")


class ReolinkError(RuntimeError):
    """Reolink API or transport error."""


@dataclass
class CameraConfig:
    name: str
    ip: str
    user: str
    password: str
    port: int = 80
    scheme: str = "http"


class ReolinkCameraClient:
    """One client per camera. Holds the auth token; re-logins on expiry."""

    def __init__(self, cfg: CameraConfig) -> None:
        self._cfg = cfg
        self._client: Optional[httpx.AsyncClient] = None
        self._token: Optional[str] = None
        # Lock is created lazily inside the running loop — avoids the
        # Python 3.9 "no current event loop" trap when this client is
        # constructed at module-import time (e.g. by env-var parsers).
        self._lock_holder: Optional[asyncio.Lock] = None

    def _lock(self) -> asyncio.Lock:
        if self._lock_holder is None:
            self._lock_holder = asyncio.Lock()
        return self._lock_holder

    @property
    def name(self) -> str:
        return self._cfg.name

    async def startup(self) -> None:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(8.0, connect=4.0),
                verify=False,  # cameras serve self-signed certs on :443
            )

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _base(self) -> str:
        return f"{self._cfg.scheme}://{self._cfg.ip}:{self._cfg.port}/cgi-bin/api.cgi"

    async def _ensure(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    async def _login(self) -> None:
        client = await self._ensure()
        body = [{
            "cmd": "Login", "action": 0,
            "param": {"User": {
                "userName": self._cfg.user,
                "password": self._cfg.password,
                "Version": "0",
            }},
        }]
        try:
            resp = await client.post(self._base(), json=body)
        except httpx.RequestError as exc:
            raise ReolinkError(
                f"reolink {self._cfg.name} login transport "
                f"({exc.__class__.__name__})"
            ) from exc
        if resp.status_code != 200:
            raise ReolinkError(
                f"reolink {self._cfg.name} login http {resp.status_code}"
            )
        try:
            data = resp.json()
        except ValueError as exc:
            raise ReolinkError(
                f"reolink {self._cfg.name} login non-json"
            ) from exc
        if not isinstance(data, list) or not data:
            raise ReolinkError(
                f"reolink {self._cfg.name} login unexpected shape"
            )
        first = data[0]
        if first.get("code") != 0:
            raise ReolinkError(
                f"reolink {self._cfg.name} login code={first.get('code')} "
                f"err={first.get('error')}"
            )
        token = (((first.get("value") or {}).get("Token") or {}).get("name"))
        if not token:
            raise ReolinkError(
                f"reolink {self._cfg.name} login returned no token"
            )
        self._token = token

    async def _cmd(self, cmd: str, param: Optional[Dict[str, Any]] = None) -> Any:
        async with self._lock():
            if self._token is None:
                await self._login()
            client = await self._ensure()
            body = [{"cmd": cmd, "action": 0, "param": param or {}}]
            url = f"{self._base()}?token={self._token}"
            try:
                resp = await client.post(url, json=body)
            except httpx.RequestError as exc:
                raise ReolinkError(
                    f"reolink {self._cfg.name} {cmd} transport "
                    f"({exc.__class__.__name__})"
                ) from exc
            if resp.status_code != 200:
                raise ReolinkError(
                    f"reolink {self._cfg.name} {cmd} http {resp.status_code}"
                )
            try:
                data = resp.json()
            except ValueError as exc:
                raise ReolinkError(
                    f"reolink {self._cfg.name} {cmd} non-json"
                ) from exc
            if not isinstance(data, list) or not data:
                raise ReolinkError(
                    f"reolink {self._cfg.name} {cmd} unexpected shape"
                )
            first = data[0]
            if first.get("code") != 0:
                # Token might have expired; one retry on "Please login first".
                err = (first.get("error") or {}).get("detail", "")
                if "login first" in err.lower():
                    self._token = None
                    await self._login()
                    return await self._cmd(cmd, param)
                raise ReolinkError(
                    f"reolink {self._cfg.name} {cmd} code={first.get('code')} "
                    f"err={first.get('error')}"
                )
            return first.get("value")

    async def get_dev_info(self) -> Dict[str, Any]:
        v = await self._cmd("GetDevInfo")
        return {
            "name": (v or {}).get("DevInfo", {}).get("name"),
            "model": (v or {}).get("DevInfo", {}).get("model"),
            "firmware": (v or {}).get("DevInfo", {}).get("firmVer"),
            "hardware": (v or {}).get("DevInfo", {}).get("hardVer"),
            "type": (v or {}).get("DevInfo", {}).get("type"),
            "serial": (v or {}).get("DevInfo", {}).get("serial"),
            "channel_num": (v or {}).get("DevInfo", {}).get("channelNum"),
        }

    async def get_motion_state(self, channel: int = 0) -> bool:
        v = await self._cmd("GetMdState", {"channel": channel})
        # A truthy "state" means motion in the last polling window.
        return bool((v or {}).get("state"))

    async def get_snapshot_url(self, channel: int = 0) -> str:
        # Snapshot is a static URL that requires the current token.
        await self._ensure()
        if self._token is None:
            await self._login()
        return (
            f"{self._cfg.scheme}://{self._cfg.ip}:{self._cfg.port}"
            f"/cgi-bin/api.cgi?cmd=Snap&channel={channel}&rs=hermes&token={self._token}"
        )
