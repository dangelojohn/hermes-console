<script setup>
import { computed } from 'vue';

const props = defineProps({
  threads: { type: Array, default: () => [] },
  activeId: { type: [String, Number], default: null },
});
const emit = defineEmits(['select', 'new-thread']);

function ago(ts) {
  if (!ts) return '';
  const d = typeof ts === 'string' ? new Date(ts) : ts;
  const diff = Date.now() - d.getTime();
  if (Number.isNaN(diff)) return '';
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  const days = Math.floor(h / 24);
  return `${days}d`;
}

function isActive(t) {
  return String(t.id) === String(props.activeId);
}

const sorted = computed(() => {
  const list = [...props.threads];
  list.sort((a, b) => {
    const av = new Date(a.updated_at || a.create_date || 0).getTime();
    const bv = new Date(b.updated_at || b.create_date || 0).getTime();
    return bv - av;
  });
  return list;
});
</script>

<template>
  <aside class="flex flex-col h-full min-h-0">
    <div class="p-2 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2">
      <span class="text-xs font-semibold uppercase tracking-wide text-slate-500">Threads</span>
      <button class="btn-primary text-xs px-2 py-1" @click="emit('new-thread')">+ New</button>
    </div>
    <div v-if="sorted.length === 0" class="p-4 text-xs text-slate-500 text-center">
      No threads yet.
    </div>
    <ul v-else class="flex-1 overflow-y-auto scrollbar-thin divide-y divide-slate-200 dark:divide-slate-800">
      <li v-for="t in sorted" :key="t.id">
        <button
          type="button"
          class="w-full text-left p-3 hover:bg-slate-100 dark:hover:bg-slate-800 transition focus:outline-none focus-visible:bg-slate-100 dark:focus-visible:bg-slate-800"
          :class="{ 'bg-slate-100 dark:bg-slate-800 ring-1 ring-brand': isActive(t) }"
          @click="emit('select', t.id)"
        >
          <div class="flex items-center justify-between gap-2">
            <span class="font-medium truncate text-sm">{{ t.title || `Thread #${t.id}` }}</span>
            <span class="text-xs text-slate-500 shrink-0">{{ ago(t.updated_at || t.create_date) }}</span>
          </div>
          <div class="text-xs text-slate-500 line-clamp-2 mt-0.5">
            {{ t.last_message || 'No messages yet.' }}
          </div>
          <div class="flex items-center gap-1.5 mt-1.5">
            <span v-if="t.message_count != null" class="pill-info">{{ t.message_count }} msg</span>
            <span v-if="t.provider" class="pill-info">{{ t.provider }}<span v-if="t.model">/{{ t.model }}</span></span>
          </div>
        </button>
      </li>
    </ul>
  </aside>
</template>
