// Thin fetch wrapper for the Hermes API.
// - 8s timeout via AbortController
// - one retry on network error (not on HTTP error)
// - parses JSON, throws ApiError on failure
// - caches tenant config (label/icon) from /api/health for header rendering

const BASE = '/api';
const DEFAULT_TIMEOUT = 8000;
const CHAT_TIMEOUT = 60000; // chat replies can take a while

export class ApiError extends Error {
  constructor(message, { status = 0, body = null, cause = null } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
    this.cause = cause;
  }
}

let tenantCache = null; // { label, icon, public_url }

async function rawFetch(path, options = {}, attempt = 0) {
  const controller = new AbortController();
  const t = setTimeout(() => controller.abort(), options.timeout || DEFAULT_TIMEOUT);
  try {
    const resp = await fetch(`${BASE}${path}`, {
      ...options,
      signal: controller.signal,
      headers: {
        'accept': 'application/json',
        ...(options.body ? { 'content-type': 'application/json' } : {}),
        ...(options.headers || {}),
      },
    });
    clearTimeout(t);
    const text = await resp.text();
    const body = text ? safeJson(text) : null;
    if (!resp.ok) {
      throw new ApiError(`HTTP ${resp.status} on ${path}`, { status: resp.status, body });
    }
    return body;
  } catch (err) {
    clearTimeout(t);
    if (err instanceof ApiError) throw err;
    // Network/abort — retry once.
    if (attempt === 0) return rawFetch(path, options, 1);
    throw new ApiError(`Network error on ${path}`, { cause: err });
  }
}

function safeJson(text) {
  try { return JSON.parse(text); } catch { return text; }
}

/* ---------- health ---------- */
export async function getHealth() {
  const h = await rawFetch('/health');
  if (h && (h.tenant_label || h.tenant_icon)) {
    tenantCache = {
      label: h.tenant_label || 'Hermes',
      icon: h.tenant_icon || '/icons/icon-192.svg',
      public_url: h.public_url || '',
    };
  }
  return h;
}

export function getTenantConfig() {
  return tenantCache || { label: 'Hermes', icon: '/icons/icon-192.svg', public_url: '' };
}

/* ---------- recommendations ---------- */
export function listRecommendations({ state = 'ready', limit = 50, offset = 0 } = {}) {
  const qs = new URLSearchParams({ state, limit, offset });
  return rawFetch(`/recommendations?${qs.toString()}`);
}

export function getRecommendation(id) {
  return rawFetch(`/recommendations/${encodeURIComponent(id)}`);
}

export function createRecommendation(payload) {
  return rawFetch('/recommendations', {
    method: 'POST',
    body: JSON.stringify(payload || {}),
  });
}

export function approveRecommendation(id, reviewer_note = '') {
  return rawFetch(`/recommendations/${encodeURIComponent(id)}/approve`, {
    method: 'POST',
    body: JSON.stringify({ reviewer_note }),
  });
}

export function rejectRecommendation(id, reviewer_note = '') {
  return rawFetch(`/recommendations/${encodeURIComponent(id)}/reject`, {
    method: 'POST',
    body: JSON.stringify({ reviewer_note }),
  });
}

export function applyRecommendation(id, tenant = null) {
  const body = tenant ? { tenant } : {};
  return rawFetch(`/recommendations/${encodeURIComponent(id)}/apply`, {
    method: 'POST',
    body: JSON.stringify(body),
  });
}

/* ---------- local queue (outbound failed pushes) ---------- */
export function getLocalQueue() {
  return rawFetch('/queue');
}

export function flushLocalQueue() {
  return rawFetch('/queue/flush', { method: 'POST' });
}

/* ---------- chat ----------
 * MVP: POST messages returns the assistant reply in the response body.
 * TODO: switch to SSE streaming once the backend supports text/event-stream.
 */
export function listChatThreads({ limit = 50 } = {}) {
  const qs = new URLSearchParams({ limit });
  return rawFetch(`/chat/threads?${qs.toString()}`);
}

export function createChatThread({ title = '', provider = '', model = '' } = {}) {
  return rawFetch('/chat/threads', {
    method: 'POST',
    body: JSON.stringify({ title, provider, model }),
  });
}

export function getChatMessages(threadId) {
  return rawFetch(`/chat/threads/${encodeURIComponent(threadId)}/messages`);
}

export function postChatMessage(threadId, { content, provider = '', model = '' } = {}) {
  return rawFetch(`/chat/threads/${encodeURIComponent(threadId)}/messages`, {
    method: 'POST',
    timeout: CHAT_TIMEOUT,
    body: JSON.stringify({ content, provider, model }),
  });
}

export function queueChatRecommendation(threadId, msgId, { title = '', priority = '' } = {}) {
  return rawFetch(
    `/chat/threads/${encodeURIComponent(threadId)}/messages/${encodeURIComponent(msgId)}/queue-recommendation`,
    {
      method: 'POST',
      body: JSON.stringify({ title, priority }),
    },
  );
}

/* ---------- tenants ---------- */
export function listTenants() {
  return rawFetch('/tenants');
}

export function testTenant(name) {
  return rawFetch(`/tenants/${encodeURIComponent(name)}/test`, { method: 'POST' });
}

/* ---------- agents ---------- */
export function listAgents() {
  return rawFetch('/agents');
}

export function triggerAgent(name) {
  return rawFetch(`/agents/${encodeURIComponent(name)}/trigger`, { method: 'POST' });
}
