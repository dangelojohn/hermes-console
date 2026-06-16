<script setup>
import { onMounted, computed } from 'vue';
import { useHermesStore } from '../stores/hermes.js';

const store = useHermesStore();

const rows = computed(() => store.localQueue);

function fmt(ts) {
  if (!ts) return '—';
  try { return new Date(ts).toLocaleString(); } catch { return String(ts); }
}

onMounted(() => store.loadLocalQueue());
</script>

<template>
  <section>
    <div class="flex items-center justify-between mb-3">
      <h1 class="text-lg font-semibold">Pending offline actions</h1>
      <div class="flex gap-2">
        <button class="btn-ghost" :disabled="store.loadingLocalQueue" @click="store.loadLocalQueue()">Refresh</button>
        <button class="btn-primary" @click="store.flushLocalQueue()">Retry all</button>
      </div>
    </div>

    <div v-if="rows.length === 0" class="card p-6 text-center text-slate-500">
      Local queue is empty.
    </div>

    <div v-else class="card overflow-x-auto">
      <table class="min-w-full text-sm">
        <thead class="bg-slate-100 dark:bg-slate-800 text-left">
          <tr>
            <th class="px-3 py-2">Queued</th>
            <th class="px-3 py-2">Action</th>
            <th class="px-3 py-2">Target</th>
            <th class="px-3 py-2">Retries</th>
            <th class="px-3 py-2">Last error</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id || `${row.action}-${row.queued_at}`"
              class="border-t border-slate-200 dark:border-slate-800">
            <td class="px-3 py-2 whitespace-nowrap">{{ fmt(row.queued_at || row.created_at) }}</td>
            <td class="px-3 py-2"><span class="pill-info">{{ row.action || row.method || '—' }}</span></td>
            <td class="px-3 py-2 font-mono text-xs break-all">{{ row.target || row.path || row.recommendation_id || '—' }}</td>
            <td class="px-3 py-2 text-center">{{ row.retry_count ?? row.retries ?? 0 }}</td>
            <td class="px-3 py-2 text-red-700 dark:text-red-400 text-xs">{{ row.last_error || '' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
