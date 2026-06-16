<script setup>
import { computed } from 'vue';
import { useHermesStore } from '../stores/hermes.js';

const store = useHermesStore();

const bannerClass = computed(() => {
  if (store.offlineSince) return 'bg-slate-800 text-slate-100';
  switch (store.healthStatus) {
    case 'err':  return 'bg-red-600 text-white';
    case 'warn': return 'bg-amber-500 text-amber-950';
    default:     return 'bg-emerald-600 text-white';
  }
});

const bannerMessage = computed(() => {
  if (store.offlineSince) {
    const ts = new Date(store.offlineSince).toLocaleTimeString();
    return `Offline — showing cached state from ${ts}`;
  }
  if (store.writesBlocked) return 'SQLite down — writes blocked.';
  const llm = store.health.llm || {};
  // Only treat 'unavailable' as a warning. 'disabled' = intentionally
  // not configured (no key/url in .env), which is a normal state — not
  // worth flagging. 'unknown' / undefined also stays silent.
  const dead = Object.entries(llm).filter(([, v]) => v === 'unavailable').map(([k]) => k);
  if (dead.length) return `LLM provider(s) unavailable: ${dead.join(', ')}.`;
  return 'All systems operational.';
});

function pillClass(state) {
  if (state === 'ok') return 'pill-ok';
  if (state === 'unknown' || state === undefined || state === null) return 'pill-info';
  return 'pill-err';
}

const llmEntries = computed(() => Object.entries(store.health.llm || {}));
const bridgeEntries = computed(() =>
  Object.entries(store.health.bridges || {}).filter(([, v]) => v !== undefined && v !== null),
);
</script>

<template>
  <div :class="bannerClass" class="sticky top-0 z-40 text-xs">
    <div class="mx-auto max-w-6xl px-4 py-1.5 flex flex-wrap items-center justify-between gap-2">
      <div class="flex items-center gap-2 min-w-0">
        <span class="font-medium truncate">{{ bannerMessage }}</span>
      </div>
      <div class="flex items-center gap-1.5 flex-wrap">
        <span :class="pillClass(store.health.api)" title="API">API</span>
        <span :class="pillClass(store.health.sqlite)" title="SQLite">SQLite</span>
        <span v-for="[name, st] in llmEntries" :key="`llm-${name}`"
              :class="pillClass(st)" :title="`LLM provider ${name} — ${st}`">
          LLM·{{ name }}
        </span>
        <span v-for="[name, st] in bridgeEntries" :key="`br-${name}`"
              :class="pillClass(st)" :title="`Bridge ${name} — ${st}`">
          Bridge·{{ name }}
        </span>
        <span class="pill-info" title="Local queue depth">
          <span class="font-semibold">{{ store.queueDepth }}</span>
          <span class="opacity-75">queued</span>
        </span>
      </div>
    </div>
  </div>
</template>
