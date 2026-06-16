<script setup>
import { computed, onMounted } from 'vue';
import { useHermesStore } from '../stores/hermes.js';

const store = useHermesStore();

const tenants = computed(() => store.tenants);

function pillClass(status) {
  if (status === 'ok') return 'pill-ok';
  if (status === 'testing') return 'pill-info animate-pulse';
  if (!status || status === 'unknown') return 'pill-info';
  return 'pill-err';
}

function fmt(ts) {
  if (!ts) return '—';
  try { return new Date(ts).toLocaleString(); } catch { return String(ts); }
}

function isSouthbrook(t) {
  return (t.name || '').toLowerCase().includes('southbrook');
}

onMounted(() => store.loadTenants());
</script>

<template>
  <section>
    <div class="flex items-center justify-between mb-3">
      <h1 class="text-lg font-semibold">Tenant bridges</h1>
      <button class="btn-ghost" :disabled="store.loadingTenants" @click="store.loadTenants()">Refresh</button>
    </div>

    <div v-if="store.loadingTenants && tenants.length === 0" class="card p-6 text-center text-slate-500">Loading…</div>
    <div v-else-if="tenants.length === 0" class="card p-6 text-center text-slate-500">
      No tenant bridges configured.
    </div>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 gap-3">
      <article v-for="t in tenants" :key="t.name" class="card p-4 space-y-2">
        <header class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <h2 class="font-semibold text-base truncate">{{ t.label || t.name }}</h2>
            <p class="text-xs text-slate-500 font-mono">{{ t.name }}</p>
          </div>
          <div class="flex items-center gap-1.5 shrink-0">
            <span class="pill-info">{{ t.kind || 'webhook' }}</span>
            <span :class="pillClass(t.last_test_status)">{{ t.last_test_status || 'untested' }}</span>
          </div>
        </header>

        <dl class="grid grid-cols-3 gap-2 text-xs">
          <dt class="text-slate-500">Last test</dt>
          <dd class="col-span-2 truncate">{{ fmt(t.last_test_at) }}</dd>
          <template v-if="t.enabled != null">
            <dt class="text-slate-500">Enabled</dt>
            <dd class="col-span-2">{{ t.enabled ? 'yes' : 'no' }}</dd>
          </template>
          <template v-if="isSouthbrook(t)">
            <dt class="text-slate-500">Target URL</dt>
            <dd class="col-span-2 font-mono break-all">{{ t.target_url || t.url || '—' }}</dd>
            <dt class="text-slate-500">Target DB</dt>
            <dd class="col-span-2 font-mono">{{ t.target_db || t.db || '—' }}</dd>
          </template>
        </dl>

        <div v-if="t.last_test_error" class="text-xs text-red-600 dark:text-red-400 break-words">
          {{ t.last_test_error }}
        </div>

        <div class="flex justify-end gap-2 pt-1">
          <button
            class="btn-primary text-xs"
            :disabled="store.tenantTestInFlight[t.name]"
            @click="store.testTenant(t.name)"
          >{{ store.tenantTestInFlight[t.name] ? 'Testing…' : 'Test' }}</button>
        </div>
      </article>
    </div>
  </section>
</template>
