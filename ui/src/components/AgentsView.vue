<script setup>
import { computed, onMounted } from 'vue';
import { useHermesStore } from '../stores/hermes.js';

const store = useHermesStore();

const agents = computed(() => store.agents);

function pillClass(status) {
  if (status === 'ok' || status === 'success') return 'pill-ok';
  if (!status || status === 'unknown' || status === 'idle') return 'pill-info';
  if (status === 'running') return 'pill-info animate-pulse';
  return 'pill-err';
}

function fmt(ts) {
  if (!ts) return '—';
  try { return new Date(ts).toLocaleString(); } catch { return String(ts); }
}

function humanInterval(secs) {
  if (secs == null) return '—';
  const s = Number(secs);
  if (!Number.isFinite(s) || s <= 0) return '—';
  if (s < 60) return `every ${s}s`;
  const m = Math.round(s / 60);
  if (m < 60) return `every ${m} min`;
  const h = Math.round(m / 60);
  if (h < 24) return `every ${h} h`;
  const d = Math.round(h / 24);
  return `every ${d} d`;
}

function ago(ts) {
  if (!ts) return '';
  const d = new Date(ts).getTime();
  if (Number.isNaN(d)) return '';
  const diff = Date.now() - d;
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

onMounted(() => store.loadAgents());
</script>

<template>
  <section>
    <div class="flex items-center justify-between mb-3">
      <h1 class="text-lg font-semibold">Agent loops</h1>
      <button class="btn-ghost" :disabled="store.loadingAgents" @click="store.loadAgents()">Refresh</button>
    </div>

    <div v-if="store.loadingAgents && agents.length === 0" class="card p-6 text-center text-slate-500">Loading…</div>
    <div v-else-if="agents.length === 0" class="card p-6 text-center text-slate-500">
      No agents registered.
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <article v-for="a in agents" :key="a.name" class="card p-4 space-y-2">
        <header class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <h2 class="font-semibold text-base truncate">{{ a.label || a.name }}</h2>
            <p class="text-xs text-slate-500 font-mono">{{ a.name }}</p>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <span :class="pillClass(a.last_run_status)">{{ a.last_run_status || 'idle' }}</span>
            <span v-if="a.enabled === false" class="pill-err">disabled</span>
          </div>
        </header>

        <p v-if="a.description" class="text-sm text-slate-600 dark:text-slate-400">{{ a.description }}</p>

        <dl class="grid grid-cols-3 gap-x-2 gap-y-1 text-xs">
          <dt class="text-slate-500">Interval</dt>
          <dd class="col-span-2">{{ humanInterval(a.interval_seconds ?? a.interval) }}</dd>
          <dt class="text-slate-500">Last run</dt>
          <dd class="col-span-2">{{ ago(a.last_run_at) || fmt(a.last_run_at) }}</dd>
          <dt class="text-slate-500">Recs created</dt>
          <dd class="col-span-2">
            <span class="pill-info">{{ a.recommendations_created_count ?? 0 }}</span>
          </dd>
        </dl>

        <div v-if="a.last_run_error" class="text-xs text-red-600 dark:text-red-400 break-words">
          {{ a.last_run_error }}
        </div>

        <div class="flex justify-end gap-2 pt-1">
          <button
            class="btn-primary text-xs"
            :disabled="store.agentTriggerInFlight[a.name] || a.enabled === false"
            @click="store.triggerAgent(a.name)"
          >{{ store.agentTriggerInFlight[a.name] ? 'Triggering…' : 'Trigger now' }}</button>
        </div>
      </article>
    </div>
  </section>
</template>
