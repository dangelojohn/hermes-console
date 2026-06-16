<script setup>
import { ref, onMounted, onBeforeUnmount, computed } from 'vue';
import { useRouter } from 'vue-router';
import { useHermesStore } from '../stores/hermes.js';
import RecommendationCard from './RecommendationCard.vue';

const store = useHermesStore();
const router = useRouter();

const TABS = ['ready', 'approved', 'applied', 'rejected', 'all'];
const active = ref('ready');
const cursor = ref(0);

const items = computed(() => store.recommendations);

async function selectTab(state) {
  active.value = state;
  cursor.value = 0;
  await store.loadList(state);
}

function openCurrent() {
  const rec = items.value[cursor.value];
  if (rec) router.push({ name: 'detail', params: { id: rec.id } });
}

function moveCursor(delta) {
  if (!items.value.length) return;
  cursor.value = Math.max(0, Math.min(items.value.length - 1, cursor.value + delta));
  const el = document.getElementById(`rec-${items.value[cursor.value]?.id}`);
  if (el) el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
}

function onKey(ev) {
  const tag = (ev.target?.tagName || '').toLowerCase();
  if (['input', 'textarea', 'select'].includes(tag)) return;
  if (ev.key === 'j') { moveCursor(1); ev.preventDefault(); }
  else if (ev.key === 'k') { moveCursor(-1); ev.preventDefault(); }
  else if (ev.key === 'Enter') { openCurrent(); ev.preventDefault(); }
}

onMounted(async () => {
  await store.loadList(active.value);
  window.addEventListener('keydown', onKey);
});
onBeforeUnmount(() => window.removeEventListener('keydown', onKey));
</script>

<template>
  <section>
    <div class="flex items-center justify-between mb-3 flex-wrap gap-2">
      <div role="tablist" class="flex flex-wrap gap-1">
        <button
          v-for="t in TABS" :key="t"
          role="tab"
          :aria-selected="active === t"
          class="btn"
          :class="active === t ? 'btn-primary' : 'btn-ghost'"
          @click="selectTab(t)"
        >
          {{ t }}
        </button>
      </div>
      <button class="btn-ghost" @click="store.loadList(active)" :disabled="store.loadingList">
        <span>{{ store.loadingList ? 'Loading…' : 'Refresh' }}</span>
      </button>
    </div>

    <div v-if="store.listError" class="card p-4 border-red-300 text-red-700">
      {{ store.listError }}
    </div>

    <div v-else-if="items.length === 0 && !store.loadingList" class="card p-6 text-center text-slate-500">
      No recommendations in <span class="font-medium">{{ active }}</span>.
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="(r, i) in items"
        :key="r.id"
        :id="`rec-${r.id}`"
        @click="$router.push({ name: 'detail', params: { id: r.id } })"
      >
        <RecommendationCard :rec="r" :active="i === cursor" />
      </div>
    </div>

    <p class="text-xs text-slate-500 mt-3">
      Shortcuts: <kbd class="px-1 border rounded">j</kbd>/<kbd class="px-1 border rounded">k</kbd> navigate,
      <kbd class="px-1 border rounded">Enter</kbd> open
    </p>
  </section>
</template>
