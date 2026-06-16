<script setup>
import { ref, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useHermesStore } from '../stores/hermes.js';

const props = defineProps({ id: { type: [String, Number], required: true } });
const store = useHermesStore();
const router = useRouter();

const reviewerNote = ref('');
const acting = ref(false);
const payloadOpen = ref(false);
const applyOpen = ref(false);
const selectedTenant = ref('');

const detail = computed(() => store.detail);

const canApprove = computed(() => detail.value?.state === 'ready' && !store.writesBlocked);
const canReject  = computed(() => detail.value?.state === 'ready' && !store.writesBlocked);
const canApply   = computed(() => detail.value?.state === 'approved' && !store.writesBlocked);

const blockedTip = computed(() => store.writesBlocked ? 'SQLite is down — writes are blocked.' : '');

const tenants = computed(() => store.tenants);

const payloadPretty = computed(() => {
  const p = detail.value?.payload_json ?? detail.value?.payload ?? null;
  if (!p) return '';
  try { return typeof p === 'string' ? JSON.stringify(JSON.parse(p), null, 2) : JSON.stringify(p, null, 2); }
  catch { return String(p); }
});

const sourceLink = computed(() => detail.value?.source_url || detail.value?.source_link || '');

async function doAction(action) {
  if (acting.value) return;
  acting.value = true;
  try {
    await store.actOnDetail(action, { reviewer_note: reviewerNote.value });
    reviewerNote.value = '';
  } finally { acting.value = false; }
}

async function openApply() {
  if (!canApply.value) return;
  if (!store.tenants.length) await store.loadTenants();
  selectedTenant.value = '';
  applyOpen.value = true;
}

async function confirmApply() {
  if (acting.value) return;
  acting.value = true;
  try {
    await store.actOnDetail('apply', { tenant: selectedTenant.value || null });
    applyOpen.value = false;
  } finally { acting.value = false; }
}

function onKey(ev) {
  const tag = (ev.target?.tagName || '').toLowerCase();
  if (['input', 'textarea', 'select'].includes(tag)) return;
  if (applyOpen.value) {
    if (ev.key === 'Escape') applyOpen.value = false;
    return;
  }
  if (ev.key === 'a' && canApprove.value) { ev.preventDefault(); doAction('approve'); }
  else if (ev.key === 'r' && canReject.value) { ev.preventDefault(); doAction('reject'); }
}

onMounted(() => {
  store.loadDetail(props.id);
  if (!store.tenants.length) store.loadTenants();
  window.addEventListener('keydown', onKey);
});
onBeforeUnmount(() => window.removeEventListener('keydown', onKey));
watch(() => props.id, (id) => store.loadDetail(id));
</script>

<template>
  <section>
    <button class="btn-ghost mb-3" @click="router.push({ name: 'queue' })">← Back to queue</button>

    <div v-if="store.loadingDetail" class="card p-6 text-center text-slate-500">Loading…</div>
    <div v-else-if="store.detailError" class="card p-4 text-red-700">{{ store.detailError }}</div>

    <article v-else-if="detail" class="space-y-4">
      <header class="card p-4">
        <div class="flex flex-wrap items-center gap-2 mb-2">
          <span class="pill" :class="{
            'priority-blocker': detail.priority === 'blocker',
            'priority-high':    detail.priority === 'high',
            'priority-normal':  !['blocker','high','low'].includes(detail.priority),
            'priority-low':     detail.priority === 'low',
          }">{{ detail.priority || 'normal' }}</span>
          <span v-if="detail.recommendation_type" class="pill-info">{{ detail.recommendation_type }}</span>
          <span class="pill-info">{{ detail.state }}</span>
          <span v-if="detail.model_provider" class="pill-info">
            {{ detail.model_provider }}<span v-if="detail.model_name">/{{ detail.model_name }}</span>
          </span>
        </div>
        <h1 class="text-xl font-bold">{{ detail.name || detail.title || `Recommendation #${detail.id}` }}</h1>
        <p v-if="detail.summary" class="mt-2 text-slate-700 dark:text-slate-300">{{ detail.summary }}</p>
        <a v-if="sourceLink" :href="sourceLink" target="_blank" rel="noopener"
           class="inline-block mt-2 text-sm text-brand hover:underline break-all">
          Source ↗
        </a>
      </header>

      <section v-if="detail.rationale" class="card p-4">
        <h2 class="text-sm font-semibold mb-2 uppercase tracking-wide text-slate-500">Rationale</h2>
        <p class="whitespace-pre-wrap text-sm">{{ detail.rationale }}</p>
      </section>

      <section v-if="detail.proposed_action" class="card p-4">
        <h2 class="text-sm font-semibold mb-2 uppercase tracking-wide text-slate-500">Proposed action</h2>
        <p class="whitespace-pre-wrap text-sm">{{ detail.proposed_action }}</p>
      </section>

      <section v-if="payloadPretty" class="card p-4">
        <button class="text-sm font-semibold uppercase tracking-wide text-slate-500 flex items-center gap-1"
                @click="payloadOpen = !payloadOpen">
          <span>{{ payloadOpen ? '▼' : '▶' }}</span> Payload
        </button>
        <pre v-if="payloadOpen" class="mt-2 text-xs font-mono bg-slate-100 dark:bg-slate-950 p-3 rounded overflow-auto max-h-96 scrollbar-thin">{{ payloadPretty }}</pre>
      </section>

      <section v-if="['ready','approved'].includes(detail.state)" class="card p-4">
        <label class="block text-sm font-medium mb-1" for="reviewer_note">Reviewer note (optional)</label>
        <textarea id="reviewer_note" v-model="reviewerNote" rows="2"
                  class="w-full rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm" />
        <div class="flex flex-wrap gap-2 mt-3">
          <button v-if="detail.state === 'ready'" class="btn-approve" :disabled="acting || !canApprove" :title="blockedTip" @click="doAction('approve')">Approve <kbd class="opacity-70">a</kbd></button>
          <button v-if="detail.state === 'ready'" class="btn-reject"  :disabled="acting || !canReject"  :title="blockedTip" @click="doAction('reject')">Reject <kbd class="opacity-70">r</kbd></button>
          <button v-if="detail.state === 'approved'" class="btn-apply" :disabled="acting || !canApply" :title="blockedTip" @click="openApply">Apply…</button>
        </div>
      </section>

      <footer class="text-xs text-slate-500 grid grid-cols-2 gap-y-1 sm:grid-cols-4">
        <span>Run: {{ detail.agent_run_id || '—' }}</span>
        <span>Created: {{ detail.create_date || detail.created_at || '—' }}</span>
        <span>Reviewed: {{ detail.reviewed_date || '—' }}</span>
        <span>Applied: {{ detail.applied_date || '—' }}</span>
      </footer>
    </article>

    <!-- Tenant picker modal -->
    <div v-if="applyOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40"
         role="dialog" aria-modal="true" @click.self="applyOpen = false">
      <div class="card w-full max-w-md p-4 space-y-3">
        <h3 class="font-semibold">Apply to which tenant?</h3>
        <p class="text-xs text-slate-500">Select a configured bridge, or apply locally (audit only).</p>
        <div class="space-y-1.5 max-h-72 overflow-y-auto scrollbar-thin">
          <label class="flex items-center gap-2 p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer">
            <input type="radio" v-model="selectedTenant" value="" />
            <span class="text-sm">(none — local audit only)</span>
          </label>
          <label v-for="t in tenants" :key="t.name"
                 class="flex items-center justify-between gap-2 p-2 rounded hover:bg-slate-100 dark:hover:bg-slate-800 cursor-pointer">
            <span class="flex items-center gap-2">
              <input type="radio" v-model="selectedTenant" :value="t.name" />
              <span class="text-sm">{{ t.label || t.name }}</span>
            </span>
            <span class="pill-info">{{ t.kind || 'webhook' }}</span>
          </label>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button class="btn-ghost" @click="applyOpen = false" :disabled="acting">Cancel</button>
          <button class="btn-apply" :disabled="acting" @click="confirmApply">
            {{ acting ? 'Applying…' : 'Apply' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>
