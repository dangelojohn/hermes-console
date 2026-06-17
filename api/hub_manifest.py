"""Persistence layer for the Hermes Hub intra-net dashboard.

Stores a single JSON manifest on disk (default: ``/data/hub-manifest.json``)
that lists every link Hermes knows about: Odoo stacks, home-automation devices,
network infrastructure, code & CI, QNAP services, documentation.

The dashboard at ``hub/index.html`` fetches this manifest at runtime; Hermes
maintains it via the ``hermes_hub_*`` MCP tools. There is no SQLite table
because the manifest is a single document that the dashboard renders top-to-
bottom — denormalising into rows would make ordering, grouping, and
roundtripping the MCP tools more complex than necessary.

File access is wrapped in ``asyncio.to_thread`` so we don't block the event
loop when the manifest is large (it won't be, but the discipline costs us
nothing). Writes are atomic via the ``tmp + rename`` pattern so a partial
crash never corrupts the file the dashboard is polling.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("api.hub_manifest")

MANIFEST_VERSION = 2
DEFAULT_PATH = "/data/hub-manifest.json"


@dataclass
class HubStore:
    """A tiny CRUD layer over the hub manifest JSON file.

    All operations take an ``asyncio.Lock`` so concurrent MCP write calls
    can't tear the file. Reads return a fresh deep-copy so callers can't
    mutate the in-memory cache.
    """
    path: str = DEFAULT_PATH
    _lock: Optional[asyncio.Lock] = field(default=None, init=False, repr=False)
    _cache: Optional[Dict[str, Any]] = field(default=None, init=False, repr=False)

    def _ensure_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def startup(self) -> None:
        async with self._ensure_lock():
            await asyncio.to_thread(self._load_or_seed)

    def _load_or_seed(self) -> None:
        p = Path(self.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            seed = _seed_manifest()
            tmp = p.with_suffix(p.suffix + ".tmp")
            tmp.write_text(json.dumps(seed, indent=2, sort_keys=True))
            os.replace(tmp, p)
            self._cache = seed
            logger.info("hub manifest seeded at %s with %d categories",
                        self.path, len(seed.get("categories", [])))
            return
        try:
            self._cache = json.loads(p.read_text())
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("hub manifest unreadable (%s) — re-seeding", exc)
            backup = p.with_suffix(p.suffix + f".broken-{int(time.time())}")
            try:
                p.rename(backup)
            except OSError:
                pass
            seed = _seed_manifest()
            p.write_text(json.dumps(seed, indent=2, sort_keys=True))
            self._cache = seed

    def _persist(self) -> None:
        if self._cache is None:
            return
        self._cache["updated_at"] = _now()
        p = Path(self.path)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_text(json.dumps(self._cache, indent=2, sort_keys=True))
        os.replace(tmp, p)

    async def read(self) -> Dict[str, Any]:
        async with self._ensure_lock():
            if self._cache is None:
                await asyncio.to_thread(self._load_or_seed)
            return json.loads(json.dumps(self._cache))  # deep-copy

    async def replace(self, manifest: Dict[str, Any], *, who: str = "hermes") -> Dict[str, Any]:
        manifest = _validate_manifest(manifest)
        manifest["version"] = MANIFEST_VERSION
        manifest["webmaster"] = who
        async with self._ensure_lock():
            self._cache = manifest
            await asyncio.to_thread(self._persist)
            return json.loads(json.dumps(self._cache))

    async def add_link(self, *, category_id: str, name: str, url: str,
                        description: str = "", health_url: Optional[str] = None,
                        tags: Optional[List[str]] = None,
                        icon: Optional[str] = None,
                        who: str = "hermes") -> Dict[str, Any]:
        link = _make_link(name=name, url=url, description=description,
                           health_url=health_url, tags=tags or [], icon=icon)
        async with self._ensure_lock():
            if self._cache is None:
                await asyncio.to_thread(self._load_or_seed)
            cat = _find_category(self._cache, category_id, create=True)
            cat["links"].append(link)
            self._cache["last_change"] = {"who": who, "what": f"added {link['name']}", "at": _now()}
            await asyncio.to_thread(self._persist)
            return link

    async def update_link(self, *, link_id: str, fields: Dict[str, Any],
                           who: str = "hermes") -> Optional[Dict[str, Any]]:
        async with self._ensure_lock():
            if self._cache is None:
                await asyncio.to_thread(self._load_or_seed)
            for cat in self._cache.get("categories", []):
                for link in cat.get("links", []):
                    if link.get("id") == link_id:
                        for k in ("name", "url", "description", "health_url",
                                  "icon", "tags"):
                            if k in fields and fields[k] is not None:
                                link[k] = fields[k]
                        link["updated_at"] = _now()
                        self._cache["last_change"] = {"who": who,
                                                       "what": f"updated {link['name']}",
                                                       "at": _now()}
                        await asyncio.to_thread(self._persist)
                        return link
            return None

    async def remove_link(self, *, link_id: str, who: str = "hermes") -> bool:
        async with self._ensure_lock():
            if self._cache is None:
                await asyncio.to_thread(self._load_or_seed)
            for cat in self._cache.get("categories", []):
                links = cat.get("links", [])
                for idx, link in enumerate(links):
                    if link.get("id") == link_id:
                        removed = links.pop(idx)
                        self._cache["last_change"] = {"who": who,
                                                       "what": f"removed {removed.get('name')}",
                                                       "at": _now()}
                        await asyncio.to_thread(self._persist)
                        return True
            return False

    async def upsert_category(self, *, id: str, name: str, icon: str = "",
                               accent: str = "#7c5cff",
                               order: Optional[int] = None,
                               who: str = "hermes") -> Dict[str, Any]:
        async with self._ensure_lock():
            if self._cache is None:
                await asyncio.to_thread(self._load_or_seed)
            cat = _find_category(self._cache, id, create=True)
            cat["name"] = name
            if icon:
                cat["icon"] = icon
            if accent:
                cat["accent"] = accent
            if order is not None:
                cat["order"] = order
            self._cache["categories"].sort(key=lambda c: c.get("order", 999))
            self._cache["last_change"] = {"who": who,
                                           "what": f"upserted category {id}",
                                           "at": _now()}
            await asyncio.to_thread(self._persist)
            return cat


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _make_link(*, name: str, url: str, description: str,
                health_url: Optional[str], tags: List[str],
                icon: Optional[str]) -> Dict[str, Any]:
    return {
        "id": uuid.uuid4().hex[:12],
        "name": name,
        "url": url,
        "description": description,
        "health_url": health_url,
        "tags": tags,
        "icon": icon,
        "added_at": _now(),
        "updated_at": _now(),
    }


def _find_category(manifest: Dict[str, Any], cat_id: str, *,
                    create: bool = False) -> Dict[str, Any]:
    for c in manifest.setdefault("categories", []):
        if c.get("id") == cat_id:
            return c
    if not create:
        raise KeyError(cat_id)
    new = {"id": cat_id, "name": cat_id.replace("_", " ").title(),
            "icon": "", "accent": "#7c5cff", "links": [], "order": 999}
    manifest["categories"].append(new)
    return new


def _validate_manifest(m: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(m, dict):
        raise ValueError("manifest must be an object")
    cats = m.get("categories")
    if not isinstance(cats, list):
        raise ValueError("manifest.categories must be a list")
    for c in cats:
        if not isinstance(c, dict) or not c.get("id") or not c.get("name"):
            raise ValueError("each category needs an id and a name")
        if not isinstance(c.get("links", []), list):
            raise ValueError(f"category {c.get('id')} links must be a list")
    return m


def _seed_manifest() -> Dict[str, Any]:
    """Initial manifest preloaded with every link Hermes already knows about.

    Hermes can replace/extend any of this at runtime via the MCP tools.
    """
    cats: List[Dict[str, Any]] = []

    def cat(cid, name, icon, accent, order, links):
        c = {"id": cid, "name": name, "icon": icon, "accent": accent,
              "order": order, "links": []}
        for ln in links:
            c["links"].append(_make_link(
                name=ln["name"], url=ln["url"],
                description=ln.get("description", ""),
                health_url=ln.get("health_url"),
                tags=ln.get("tags", []), icon=ln.get("icon"),
            ))
        cats.append(c)

    cat("hermes", "Hermes Console", "🤖", "#7c5cff", 10, [
        {"name": "Hermes Console UI",
         "url": "https://hermes.odooiq.com/",
         "description": "Main agent control plane — chats, recommendations, tenants, agents",
         "health_url": "https://hermes.odooiq.com/api/health",
         "tags": ["fastapi", "prod"], "icon": "🛡️"},
        {"name": "Hermes API health",
         "url": "https://hermes.odooiq.com/api/health",
         "description": "JSON health: sqlite + LLM providers + bridges",
         "health_url": "https://hermes.odooiq.com/api/health",
         "tags": ["api", "health"], "icon": "❤️"},
        {"name": "Hermes Hub (this page)",
         "url": "https://hermes.odooiq.com/hub/",
         "description": "You are here. Maintained by Hermes via MCP.",
         "tags": ["dashboard"], "icon": "🧭"},
    ])

    cat("odoo", "Odoo Hosted Sites", "🏢", "#a855f7", 20, [
        {"name": "Southbrook Cabinetry (PROD)",
         "url": "https://southbrookcabinetry.space/",
         "description": "Production Odoo 19 CE — full PLM/MRP/CRM platform",
         "health_url": "https://southbrookcabinetry.space/web/login",
         "tags": ["production", "v19", "tier-1"], "icon": "🪵"},
        {"name": "Sapienzium (demo)",
         "url": "https://sapienzium.com/",
         "description": "Odoo 19 CE demo stack",
         "health_url": "https://sapienzium.com/web/login",
         "tags": ["demo", "v19"]},
        {"name": "Porterly (demo)",
         "url": "https://porterly.com/",
         "description": "Odoo 19 CE demo stack",
         "tags": ["demo", "v19"]},
        {"name": "Tribancs (demo)",
         "url": "https://tribancs.com/",
         "description": "Odoo 19 CE demo stack",
         "tags": ["demo", "v19"]},
        {"name": "OdooIQ (demo)",
         "url": "https://odooiq.com/",
         "description": "Odoo 19 CE demo stack — also hosts Cloudflare-tunnel ingress",
         "tags": ["demo", "v19", "tunnel"]},
        {"name": "Quattroporte (demo)",
         "url": "https://quattroporte.io/",
         "description": "Odoo 19 CE demo stack",
         "tags": ["demo", "v19"]},
        {"name": "OdooAI (demo)",
         "url": "https://odooai.com/",
         "description": "Odoo 19 CE demo stack",
         "tags": ["demo", "v19"]},
    ])

    cat("home_automation", "Home Automation", "🏠", "#22d3ee", 30, [
        {"name": "Home Assistant (Nabu Casa)",
         "url": "https://my.home-assistant.io/",
         "description": "Front door — Ecobee, Lutron, Phyn, Google Home, more",
         "tags": ["hub", "ha"], "icon": "🏡"},
        {"name": "Ecobee web portal",
         "url": "https://home.ee.co/",
         "description": "Thermostat status, schedules, energy reports",
         "tags": ["climate"]},
        {"name": "Lutron Caseta",
         "url": "https://lutron.com/myaccount/",
         "description": "Lighting scenes + Picos",
         "tags": ["lighting"]},
        {"name": "Reolink Argus",
         "url": "https://reolink.com/argus/",
         "description": "Camera cloud account — local LAN API used by Hermes",
         "tags": ["camera", "local-api"]},
        {"name": "Phyn cloud",
         "url": "https://phyn.com/",
         "description": "Water flow, pressure, leaks — read via HA bridge",
         "tags": ["water", "ha-bridge"]},
        {"name": "Google Home",
         "url": "https://home.google.com/",
         "description": "Voice + automations endpoint",
         "tags": ["voice"]},
        {"name": "Omada Cloud Controller",
         "url": "https://omada.tplinkcloud.com/",
         "description": "TP-Link Omada — switches, APs, OC200",
         "tags": ["network", "omada"]},
    ])

    cat("network", "Network & Infra", "🌐", "#38bdf8", 40, [
        {"name": "Cloudflare dashboard",
         "url": "https://dash.cloudflare.com/",
         "description": "All zones, tunnels, Access policies — Hermes has read-only API",
         "tags": ["cdn", "tunnel"], "icon": "☁️"},
        {"name": "Cloudflare Zero Trust",
         "url": "https://one.dash.cloudflare.com/",
         "description": "Access + Tunnel + Gateway dashboard",
         "tags": ["zero-trust"]},
        {"name": "cloudflared tunnel logs",
         "url": "https://hermes.odooiq.com/api/health",
         "description": "Hermes-side health surface for the tunnel + caddy",
         "tags": ["tunnel", "diagnostic"]},
    ])

    cat("code", "Code & CI", "💾", "#f59e0b", 50, [
        {"name": "Forgejo (self-hosted Git)",
         "url": "https://git.southbrookcabinetry.space/",
         "description": "Primary git origin — qnap/ org hosts all stacks",
         "health_url": "https://git.southbrookcabinetry.space/api/v1/version",
         "tags": ["git", "self-hosted"], "icon": "🦊"},
        {"name": "Forgejo Actions runner",
         "url": "https://git.southbrookcabinetry.space/-/admin/runners",
         "description": "act_runner — linux-amd64 label, mounts system-docker.sock",
         "tags": ["ci", "runner"]},
        {"name": "GitHub mirror",
         "url": "https://github.com/dangelojohn/",
         "description": "Public mirror for OCA / community PRs",
         "tags": ["mirror"]},
    ])

    cat("qnap", "QNAP Services", "📊", "#10b981", 60, [
        {"name": "QTS Admin",
         "url": "https://192.168.68.76:8443/",
         "description": "QNAP web UI — system-docker, NAS settings",
         "tags": ["nas", "admin"], "icon": "🗄️"},
        {"name": "Container Station",
         "url": "https://192.168.68.76:8443/container-station/",
         "description": "qpkg container manager — 'system-docker.sock' quirk",
         "tags": ["docker"]},
        {"name": "QNAP File Station",
         "url": "https://192.168.68.76:8443/filestation/",
         "description": "Filesystem browser — /share/CACHEDEV3_DATA roots",
         "tags": ["fs"]},
        {"name": "Backup directory (CACHEDEV3)",
         "url": "https://192.168.68.76:8443/filestation/?path=/OdooIQ-Backups",
         "description": "Nightly 3am backups — 14/12/12 retention",
         "tags": ["backup"]},
    ])

    cat("docs", "Documentation & References", "📚", "#ef4444", 70, [
        {"name": "Cloudflare Docs MCP",
         "url": "https://docs.mcp.cloudflare.com/mcp",
         "description": "Upstream MCP — surfaces as cf_docs__* tools in Hermes",
         "tags": ["mcp", "upstream"]},
        {"name": "Anthropic console",
         "url": "https://console.anthropic.com/",
         "description": "Claude API + usage — Hermes calls via this",
         "tags": ["llm", "billing"]},
        {"name": "Google AI Studio",
         "url": "https://aistudio.google.com/",
         "description": "Gemini 2.5 free tier — OpenAI-compat shim",
         "tags": ["llm", "free"]},
        {"name": "Hermes skills library",
         "url": "https://hermes.odooiq.com/api/mcp/calls",
         "description": "Audit log of every MCP tool call",
         "tags": ["audit"]},
    ])

    return {
        "version": MANIFEST_VERSION,
        "webmaster": "Hermes Console",
        "generated_at": _now(),
        "updated_at": _now(),
        "categories": cats,
        "last_change": {"who": "system", "what": "seeded manifest", "at": _now()},
    }
