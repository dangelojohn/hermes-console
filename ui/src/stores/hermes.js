import { defineStore } from 'pinia';
import * as api from '../services/api.js';

// Central Pinia store. Holds health, recommendations, chat, tenants, agents,
// local queue, toasts, and offline status surfaced by the service worker.
export const useHermesStore = defineStore('hermes', {
  state: () => ({
    health: {
      api: 'unknown', sqlite: 'unknown', queue_depth: 0,
      tenant_label: 'Hermes', tenant_icon: '/icons/icon-192.svg', public_url: '',
      // new slices
      llm: {},      // { openai: 'ok'|'unavailable', hermes: 'ok'|'unavailable', ... }
      bridges: {},  // { southbrook_hermes: 'ok'|'down', ... }
    },
    healthError: null,
    healthPollHandle: null,

    /* recommendations */
    recommendations: [],
    recsByState: { ready: [], approved: [], applied: [], rejected: [], all: [] },
    currentState: 'ready',
    loadingList: false,
    listError: null,
    detail: null,
    loadingDetail: false,
    detailError: null,

    /* local queue */
    localQueue: [],
    loadingLocalQueue: false,

    /* chat */
    threads: [],
    activeThreadId: null,
    messagesByThread: {}, // { [threadId]: Message[] }
    pendingByThread: {},  // { [threadId]: bool }
    loadingThreads: false,
    loadingMessages: false,

    /* tenants */
    tenants: [],
    loadingTenants: false,
    tenantTestInFlight: {}, // { [name]: true }

    /* agents */
    agents: [],
    loadingAgents: false,
    agentTriggerInFlight: {}, // { [name]: true }

    toasts: [],
    offlineSince: null,
  }),

  getters: {
    healthStatus(state) {
      if (state.health.sqlite && state.health.sqlite !== 'ok' && state.health.sqlite !== 'unknown') return 'err';
      if (state.health.api !== 'ok') return 'warn';
      // Any LLM unavailable -> amber
      const llm = state.health.llm || {};
      for (const v of Object.values(llm)) {
        if (v && v !== 'ok' && v !== 'unknown') return 'warn';
      }
      return 'ok';
    },
    queueDepth(state) {
      return state.health.queue_depth || 0;
    },
    activeThread(state) {
      return state.threads.find((t) => String(t.id) === String(state.activeThreadId)) || null;
    },
    chatHasPending(state) {
      return Object.values(state.pendingByThread).some(Boolean);
    },
    readyCount(state) {
      return (state.recsByState.ready || []).length;
    },
    writesBlocked(state) {
      const sq = state.health.sqlite;
      return sq && sq !== 'ok' && sq !== 'unknown';
    },
  },

  actions: {
    /* ---------- toast ---------- */
    pushToast({ message, type = 'info', timeout = 4000, action = null }) {
      const id = Math.random().toString(36).slice(2);
      this.toasts.push({ id, message, type, action });
      if (timeout) setTimeout(() => this.dismissToast(id), timeout);
      return id;
    },
    dismissToast(id) {
      this.toasts = this.toasts.filter((t) => t.id !== id);
    },

    /* ---------- health ---------- */
    async refreshHealth() {
      try {
        const h = await api.getHealth();
        this.health = { ...this.health, ...h };
        this.healthError = null;
      } catch (err) {
        this.healthError = err.message || 'health failed';
        this.health = { ...this.health, api: 'down' };
      }
    },
    startHealthPolling() {
      if (this.healthPollHandle) return;
      this.refreshHealth();
      this.healthPollHandle = setInterval(() => this.refreshHealth(), 15000);
    },
    stopHealthPolling() {
      if (this.healthPollHandle) clearInterval(this.healthPollHandle);
      this.healthPollHandle = null;
    },

    /* ---------- recommendations ---------- */
    async loadList(state = 'ready') {
      this.currentState = state;
      this.loadingList = true;
      this.listError = null;
      try {
        const params = state === 'all' ? {} : { state };
        const data = await api.listRecommendations(params);
        const list = Array.isArray(data) ? data : (data?.items || []);
        this.recommendations = list;
        this.recsByState[state] = list;
      } catch (err) {
        this.listError = err.message || 'failed to load';
        this.recommendations = [];
      } finally {
        this.loadingList = false;
      }
    },

    async loadDetail(id) {
      this.loadingDetail = true;
      this.detailError = null;
      this.detail = null;
      try {
        this.detail = await api.getRecommendation(id);
      } catch (err) {
        this.detailError = err.message || 'failed to load';
      } finally {
        this.loadingDetail = false;
      }
    },

    async actOnDetail(action, payload = {}) {
      if (!this.detail) return null;
      if (this.writesBlocked) {
        this.pushToast({ message: 'SQLite down — writes blocked.', type: 'err' });
        return null;
      }
      const id = this.detail.id;
      try {
        let res;
        if (action === 'apply') {
          res = await api.applyRecommendation(id, payload.tenant || null);
        } else if (action === 'approve') {
          res = await api.approveRecommendation(id, payload.reviewer_note || '');
        } else if (action === 'reject') {
          res = await api.rejectRecommendation(id, payload.reviewer_note || '');
        }
        if (res?.new_state) this.detail.state = res.new_state;
        if (res?.queued) {
          this.pushToast({ message: 'Queued — will sync when bridge is back', type: 'warn' });
          this.health.queue_depth = (this.health.queue_depth || 0) + 1;
        } else {
          this.pushToast({ message: `${action} succeeded`, type: 'ok' });
        }
        return res;
      } catch (err) {
        this.pushToast({ message: `${action} failed: ${err.message}`, type: 'err', timeout: 6000 });
        throw err;
      }
    },

    /* ---------- local queue ---------- */
    async loadLocalQueue() {
      this.loadingLocalQueue = true;
      try {
        const data = await api.getLocalQueue();
        this.localQueue = Array.isArray(data) ? data : (data?.items || []);
      } catch (err) {
        this.pushToast({ message: `queue load failed: ${err.message}`, type: 'err' });
      } finally {
        this.loadingLocalQueue = false;
      }
    },
    async flushLocalQueue() {
      try {
        await api.flushLocalQueue();
        this.pushToast({ message: 'Retry triggered', type: 'ok' });
        await this.loadLocalQueue();
        await this.refreshHealth();
      } catch (err) {
        this.pushToast({ message: `flush failed: ${err.message}`, type: 'err' });
      }
    },

    /* ---------- chat ---------- */
    async loadThreads() {
      this.loadingThreads = true;
      try {
        const data = await api.listChatThreads({ limit: 50 });
        this.threads = Array.isArray(data) ? data : (data?.items || []);
      } catch (err) {
        this.pushToast({ message: `threads load failed: ${err.message}`, type: 'err' });
      } finally {
        this.loadingThreads = false;
      }
    },

    async createThread(opts = {}) {
      try {
        const t = await api.createChatThread(opts);
        if (t?.id != null) {
          this.threads = [t, ...this.threads];
          this.activeThreadId = t.id;
          this.messagesByThread[t.id] = [];
        }
        return t;
      } catch (err) {
        this.pushToast({ message: `new thread failed: ${err.message}`, type: 'err' });
        throw err;
      }
    },

    setActiveThread(id) {
      this.activeThreadId = id;
    },

    async loadMessages(threadId) {
      if (!threadId) return;
      this.loadingMessages = true;
      try {
        const data = await api.getChatMessages(threadId);
        const list = Array.isArray(data) ? data : (data?.items || []);
        this.messagesByThread = { ...this.messagesByThread, [threadId]: list };
      } catch (err) {
        this.pushToast({ message: `messages load failed: ${err.message}`, type: 'err' });
      } finally {
        this.loadingMessages = false;
      }
    },

    async sendMessage(threadId, content, opts = {}) {
      if (!threadId || !content?.trim()) return null;
      // Optimistic user message.
      const localId = `tmp-${Date.now()}`;
      const userMsg = {
        id: localId, role: 'user', content,
        created_at: new Date().toISOString(),
        pending: true,
      };
      const existing = this.messagesByThread[threadId] || [];
      this.messagesByThread = { ...this.messagesByThread, [threadId]: [...existing, userMsg] };
      this.pendingByThread = { ...this.pendingByThread, [threadId]: true };
      try {
        const res = await api.postChatMessage(threadId, { content, ...opts });
        // Backend may return { user_message, assistant_message } or just assistant.
        const userOut = res?.user_message || { ...userMsg, id: res?.user_id || localId, pending: false };
        const assistant = res?.assistant_message || res?.message || res;
        const cleaned = (this.messagesByThread[threadId] || []).filter((m) => m.id !== localId);
        const next = [...cleaned, userOut];
        if (assistant && assistant.content != null) next.push(assistant);
        this.messagesByThread = { ...this.messagesByThread, [threadId]: next };
        // Bump thread preview.
        const idx = this.threads.findIndex((t) => String(t.id) === String(threadId));
        if (idx >= 0) {
          const t = { ...this.threads[idx], last_message: assistant?.content || content, updated_at: new Date().toISOString(), message_count: (this.threads[idx].message_count || 0) + 2 };
          const copy = [...this.threads]; copy[idx] = t; this.threads = copy;
        }
        return assistant;
      } catch (err) {
        // Mark optimistic message as failed.
        const list = (this.messagesByThread[threadId] || []).map((m) =>
          m.id === localId ? { ...m, pending: false, error: err.message } : m,
        );
        this.messagesByThread = { ...this.messagesByThread, [threadId]: list };
        this.pushToast({ message: `send failed: ${err.message}`, type: 'err', timeout: 6000 });
        throw err;
      } finally {
        this.pendingByThread = { ...this.pendingByThread, [threadId]: false };
      }
    },

    async queueAsRecommendation(threadId, msgId, opts = {}) {
      try {
        const res = await api.queueChatRecommendation(threadId, msgId, opts);
        const rid = res?.id || res?.recommendation_id;
        this.pushToast({
          message: rid ? `Queued as recommendation #${rid}` : 'Queued as recommendation',
          type: 'ok',
          action: rid ? { label: 'Open', to: { name: 'detail', params: { id: rid } } } : null,
        });
        return res;
      } catch (err) {
        this.pushToast({ message: `queue failed: ${err.message}`, type: 'err' });
        throw err;
      }
    },

    /* ---------- tenants ---------- */
    async loadTenants() {
      this.loadingTenants = true;
      try {
        const data = await api.listTenants();
        this.tenants = Array.isArray(data) ? data : (data?.items || []);
      } catch (err) {
        this.pushToast({ message: `tenants load failed: ${err.message}`, type: 'err' });
      } finally {
        this.loadingTenants = false;
      }
    },

    async testTenant(name) {
      this.tenantTestInFlight = { ...this.tenantTestInFlight, [name]: true };
      // Optimistic pending pill.
      const idx = this.tenants.findIndex((t) => t.name === name);
      if (idx >= 0) {
        const copy = [...this.tenants];
        copy[idx] = { ...copy[idx], last_test_status: 'testing' };
        this.tenants = copy;
      }
      try {
        const res = await api.testTenant(name);
        const status = res?.status || (res?.ok === false ? 'down' : 'ok');
        const j = this.tenants.findIndex((t) => t.name === name);
        if (j >= 0) {
          const copy = [...this.tenants];
          copy[j] = { ...copy[j], last_test_status: status, last_test_at: new Date().toISOString(), last_test_error: res?.error || '' };
          this.tenants = copy;
        }
        this.pushToast({ message: `${name}: ${status}`, type: status === 'ok' ? 'ok' : 'err' });
        return res;
      } catch (err) {
        const j = this.tenants.findIndex((t) => t.name === name);
        if (j >= 0) {
          const copy = [...this.tenants];
          copy[j] = { ...copy[j], last_test_status: 'down', last_test_at: new Date().toISOString(), last_test_error: err.message };
          this.tenants = copy;
        }
        this.pushToast({ message: `${name} test failed: ${err.message}`, type: 'err' });
        throw err;
      } finally {
        this.tenantTestInFlight = { ...this.tenantTestInFlight, [name]: false };
      }
    },

    /* ---------- agents ---------- */
    async loadAgents() {
      this.loadingAgents = true;
      try {
        const data = await api.listAgents();
        this.agents = Array.isArray(data) ? data : (data?.items || []);
      } catch (err) {
        this.pushToast({ message: `agents load failed: ${err.message}`, type: 'err' });
      } finally {
        this.loadingAgents = false;
      }
    },

    async triggerAgent(name) {
      this.agentTriggerInFlight = { ...this.agentTriggerInFlight, [name]: true };
      try {
        const res = await api.triggerAgent(name);
        const ids = res?.recommendation_ids || res?.created || [];
        if (ids.length) {
          this.pushToast({
            message: `${name} → ${ids.length} recommendation${ids.length === 1 ? '' : 's'}`,
            type: 'ok',
            timeout: 6000,
            action: { label: 'View queue', to: { name: 'queue' } },
          });
        } else {
          this.pushToast({ message: `${name} triggered (no new recs)`, type: 'info' });
        }
        await this.loadAgents();
        return res;
      } catch (err) {
        this.pushToast({ message: `${name} trigger failed: ${err.message}`, type: 'err' });
        throw err;
      } finally {
        this.agentTriggerInFlight = { ...this.agentTriggerInFlight, [name]: false };
      }
    },

    /* ---------- offline signal from SW ---------- */
    markOffline(cachedAt) {
      this.offlineSince = cachedAt || Date.now();
    },
    clearOffline() {
      this.offlineSince = null;
    },
  },
});
