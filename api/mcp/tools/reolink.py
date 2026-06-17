"""Reolink camera MCP tools.

Read-only: device info, motion state, snapshot URL. No streaming — video
playback stays in the Reolink app / HA / NVR.

Cameras come from the ``REOLINK_CAMERAS_JSON`` env var (a JSON list of
``{name, ip, user, password, port?, scheme?}`` dicts). Hermes spins up one
``ReolinkCameraClient`` per camera at startup and re-uses it across calls.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from api.mcp.clients.reolink import CameraConfig, ReolinkCameraClient, ReolinkError
from api.mcp.tools import ToolSpec, register_tool

_CAMERAS: Dict[str, ReolinkCameraClient] = {}


def set_cameras(cameras: Dict[str, ReolinkCameraClient]) -> None:
    global _CAMERAS
    _CAMERAS = cameras


def _require(name: str) -> ReolinkCameraClient:
    cam = _CAMERAS.get(name)
    if cam is None:
        raise ReolinkError(
            f"camera '{name}' not configured — set REOLINK_CAMERAS_JSON in .env"
        )
    return cam


async def _list_cameras(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    return {"cameras": sorted(_CAMERAS.keys()), "count": len(_CAMERAS)}


async def _get_dev_info(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    name = args.get("name") or ""
    if not name:
        return {"error": "name is required"}
    try:
        cam = _require(name)
        info = await cam.get_dev_info()
        return {"camera": name, "info": info}
    except ReolinkError as exc:
        return {"error": str(exc)}


async def _get_motion(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    name = args.get("name") or ""
    channel = int(args.get("channel") or 0)
    if not name:
        return {"error": "name is required"}
    try:
        cam = _require(name)
        return {"camera": name, "channel": channel,
                 "motion": await cam.get_motion_state(channel)}
    except ReolinkError as exc:
        return {"error": str(exc)}


async def _get_snapshot_url(ctx, args: Dict[str, Any]) -> Dict[str, Any]:
    name = args.get("name") or ""
    channel = int(args.get("channel") or 0)
    if not name:
        return {"error": "name is required"}
    try:
        cam = _require(name)
        return {"camera": name, "channel": channel,
                 "snapshot_url": await cam.get_snapshot_url(channel)}
    except ReolinkError as exc:
        return {"error": str(exc)}


def register() -> None:
    register_tool(ToolSpec(
        name="hermes_reolink_list_cameras",
        description=(
            "List the Reolink cameras Hermes has been told about via "
            "REOLINK_CAMERAS_JSON. Returns names only — no IPs or creds."
        ),
        input_schema={"type": "object"},
        handler=_list_cameras,
    ))
    register_tool(ToolSpec(
        name="hermes_reolink_get_device_info",
        description=(
            "Read a camera's model, firmware, hardware version, serial, "
            "and channel count. Useful for inventory + firmware-currency "
            "checks."
        ),
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}},
        },
        handler=_get_dev_info,
    ))
    register_tool(ToolSpec(
        name="hermes_reolink_get_motion_state",
        description=(
            "Read whether motion has been detected on a channel in the "
            "camera's recent polling window. Returns boolean. channel "
            "defaults to 0 (main lens of a single-lens camera)."
        ),
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "channel": {"type": "integer", "default": 0},
            },
        },
        handler=_get_motion,
    ))
    register_tool(ToolSpec(
        name="hermes_reolink_get_snapshot_url",
        description=(
            "Return a tokenised URL that fetches a JPEG snapshot from the "
            "camera. The URL is time-bounded by the current Reolink session "
            "token (≈1 hour). Useful for embedding in a recommendation's "
            "payload so the operator can click through and see what tripped "
            "motion."
        ),
        input_schema={
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "channel": {"type": "integer", "default": 0},
            },
        },
        handler=_get_snapshot_url,
    ))


def build_cameras_from_env(env_value: str) -> Dict[str, ReolinkCameraClient]:
    """Parse REOLINK_CAMERAS_JSON and instantiate one client per camera."""
    import json as _json
    try:
        cams_list = _json.loads(env_value or "[]")
    except _json.JSONDecodeError:
        return {}
    out: Dict[str, ReolinkCameraClient] = {}
    if not isinstance(cams_list, list):
        return {}
    for raw in cams_list:
        if not isinstance(raw, dict):
            continue
        name = raw.get("name") or ""
        ip = raw.get("ip") or ""
        user = raw.get("user") or ""
        password = raw.get("password") or ""
        if not (name and ip and user and password):
            continue
        cfg = CameraConfig(
            name=name, ip=ip, user=user, password=password,
            port=int(raw.get("port") or 80),
            scheme=raw.get("scheme") or "http",
        )
        out[name] = ReolinkCameraClient(cfg)
    return out
