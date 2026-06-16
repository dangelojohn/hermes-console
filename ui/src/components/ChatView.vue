<script setup>
import { ref, computed, onMounted, watch, nextTick, onBeforeUnmount } from 'vue';
import { useRouter } from 'vue-router';
import { useHermesStore } from '../stores/hermes.js';
import ChatThreadList from './ChatThreadList.vue';
import ChatMessage from './ChatMessage.vue';
import ModelPicker from './ModelPicker.vue';

const props = defineProps({ threadId: { type: [String, Number], default: null } });
const store = useHermesStore();
const router = useRouter();

const composer = ref('');
const modelChoice = ref({ provider: '', model: '' });
const scroller = ref(null);

const SAMPLE_PROMPTS = [
  'Look at the platform health and tell me what needs attention.',
  'Draft an email to my team about this week\'s blockers.',
  'Summarize the last 10 recommendations and rank by impact.',
  'What agent loops are most active right now?',
];

const activeId = computed(() => store.activeThreadId);
const activeThread = computed(() => store.activeThread);
const messages = computed(() => store.messagesByThread[activeId.value] || []);
const sending = computed(() => Boolean(store.pendingByThread[activeId.value]));

async function pick(id) {
  store.setActiveThread(id);
  router.replace({ name: 'chat-thread', params: { threadId: id } });
  if (!store.messagesByThread[id]) await store.loadMessages(id);
  scrollToBottom();
}

async function newThread() {
  if (store.writesBlocked) {
    store.pushToast({ message: 'SQLite down — cannot create thread.', type: 'err' });
    return;
  }
  const t = await store.createThread({
    provider: modelChoice.value.provider,
    model: modelChoice.value.model,
  });
  if (t?.id) router.replace({ name: 'chat-thread', params: { threadId: t.id } });
}

async function send() {
  const text = composer.value.trim();
  if (!text || sending.value) return;
  let tid = activeId.value;
  if (!tid) {
    const t = await store.createThread({
      provider: modelChoice.value.provider,
      model: modelChoice.value.model,
    });
    if (!t?.id) return;
    tid = t.id;
    router.replace({ name: 'chat-thread', params: { threadId: tid } });
  }
  composer.value = '';
  await store.sendMessage(tid, text, modelChoice.value);
  scrollToBottom();
}

function onComposerKey(ev) {
  if ((ev.metaKey || ev.ctrlKey) && ev.key === 'Enter') { ev.preventDefault(); send(); }
  else if (ev.key === 'Escape') { composer.value = ''; }
}

function applySample(p) {
  composer.value = p;
  nextTick(() => {
    const el = document.getElementById('chat-composer');
    if (el) el.focus();
  });
}

async function queueMessage(msg) {
  if (!activeId.value || !msg?.id) return;
  const title = (msg.content || '').slice(0, 80) || 'From chat';
  await store.queueAsRecommendation(activeId.value, msg.id, { title });
}

function scrollToBottom() {
  nextTick(() => {
    const el = scroller.value;
    if (el) el.scrollTop = el.scrollHeight;
  });
}

watch(() => props.threadId, async (val) => {
  if (val && String(val) !== String(activeId.value)) {
    store.setActiveThread(val);
    if (!store.messagesByThread[val]) await store.loadMessages(val);
    scrollToBottom();
  }
});

watch(activeThread, (t) => {
  if (t && (t.provider || t.model) && !modelChoice.value.provider) {
    modelChoice.value = { provider: t.provider || '', model: t.model || '' };
  }
});

watch(messages, () => scrollToBottom());

onMounted(async () => {
  await store.loadThreads();
  if (props.threadId) {
    store.setActiveThread(props.threadId);
    await store.loadMessages(props.threadId);
  }
  scrollToBottom();
});

onBeforeUnmount(() => { /* nothing */ });
</script>

<template>
  <section class="grid grid-cols-1 md:grid-cols-[260px_1fr] gap-3 h-[calc(100vh-12rem)] min-h-[480px]">
    <div class="card overflow-hidden md:flex hidden flex-col">
      <ChatThreadList :threads="store.threads" :active-id="activeId" @select="pick" @new-thread="newThread" />
    </div>

    <div class="card flex flex-col min-h-0 overflow-hidden">
      <header class="px-3 py-2 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-2">
        <div class="min-w-0 flex-1">
          <h2 class="font-semibold truncate text-sm">
            {{ activeThread?.title || (activeId ? `Thread #${activeId}` : 'New conversation') }}
          </h2>
        </div>
        <div class="flex items-center gap-2 shrink-0">
          <ModelPicker v-model="modelChoice" :disabled="sending" />
          <button class="btn-ghost text-xs md:hidden" @click="newThread">+ New</button>
        </div>
      </header>

      <div ref="scroller" class="flex-1 overflow-y-auto scrollbar-thin p-3 space-y-3">
        <div v-if="!activeId" class="text-center text-slate-500 py-8 space-y-4">
          <p class="text-sm">Start a new conversation or pick a sample below.</p>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 max-w-xl mx-auto">
            <button
              v-for="(p, i) in SAMPLE_PROMPTS" :key="i"
              class="card p-3 text-left text-sm hover:shadow-md transition"
              @click="applySample(p)"
            >{{ p }}</button>
          </div>
        </div>
        <template v-else>
          <div v-if="store.loadingMessages && messages.length === 0" class="text-slate-500 text-sm">Loading…</div>
          <div v-else-if="messages.length === 0" class="text-slate-500 text-sm">No messages yet. Say hi.</div>
          <ChatMessage
            v-for="m in messages" :key="m.id || m.created_at"
            :message="m" @queue="queueMessage"
          />
          <div v-if="sending" class="rounded-lg p-3 bg-slate-100 dark:bg-slate-800 text-sm text-slate-500 animate-pulse">
            Hermes is thinking…
          </div>
        </template>
      </div>

      <footer class="border-t border-slate-200 dark:border-slate-800 p-2">
        <div class="flex items-end gap-2">
          <textarea
            id="chat-composer"
            v-model="composer"
            rows="2"
            placeholder="Message Hermes…  (Cmd-Enter to send · Esc to clear)"
            class="flex-1 rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm p-2 resize-y min-h-[44px] max-h-48"
            :disabled="store.writesBlocked"
            @keydown="onComposerKey"
          />
          <button class="btn-primary" :disabled="sending || !composer.trim() || store.writesBlocked" @click="send">
            {{ sending ? 'Sending…' : 'Send' }}
          </button>
        </div>
      </footer>
    </div>
  </section>
</template>
