<script setup>
import { computed, ref } from 'vue';
import { marked } from 'marked';

const props = defineProps({
  message: { type: Object, required: true },
  canQueue: { type: Boolean, default: true },
});
const emit = defineEmits(['queue']);

marked.setOptions({ gfm: true, breaks: true });

const roleLabel = computed(() => {
  const r = props.message.role;
  if (r === 'user') return 'You';
  if (r === 'assistant') return 'Hermes';
  if (r === 'system') return 'System';
  return r || 'msg';
});

const rendered = computed(() => {
  const c = props.message.content || '';
  if (props.message.role === 'user') {
    // user content as plain text (escape via textContent semantics)
    const escaped = String(c)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    return escaped.replace(/\n/g, '<br/>');
  }
  try { return marked.parse(String(c)); } catch { return String(c); }
});

const copied = ref(false);
async function copyText() {
  try {
    await navigator.clipboard.writeText(props.message.content || '');
    copied.value = true;
    setTimeout(() => { copied.value = false; }, 1500);
  } catch { /* ignore */ }
}

const tokenLabel = computed(() => {
  const tin = props.message.tokens_in ?? props.message.prompt_tokens;
  const tout = props.message.tokens_out ?? props.message.completion_tokens;
  if (tin == null && tout == null) return '';
  return `${tin ?? 0} in · ${tout ?? 0} out`;
});

const bubbleClass = computed(() => {
  if (props.message.role === 'user') return 'bg-brand/10 dark:bg-brand/20';
  if (props.message.role === 'system') return 'bg-amber-100 dark:bg-amber-900/30';
  return 'bg-slate-100 dark:bg-slate-800';
});
</script>

<template>
  <article class="rounded-lg p-3" :class="bubbleClass">
    <header class="flex items-center justify-between gap-2 mb-1">
      <div class="flex items-center gap-2">
        <span class="text-xs font-semibold uppercase tracking-wide">{{ roleLabel }}</span>
        <span v-if="message.provider" class="pill-info">{{ message.provider }}<span v-if="message.model">/{{ message.model }}</span></span>
        <span v-if="message.pending" class="pill-info animate-pulse">sending…</span>
        <span v-if="message.error" class="pill-err">{{ message.error }}</span>
      </div>
      <div class="flex items-center gap-1">
        <button class="btn-ghost text-xs px-1.5 py-0.5" @click="copyText" :aria-label="copied ? 'Copied' : 'Copy message'">
          {{ copied ? 'Copied' : 'Copy' }}
        </button>
        <button
          v-if="canQueue && message.role === 'assistant' && message.id"
          class="btn-ghost text-xs px-1.5 py-0.5"
          @click="emit('queue', message)"
        >Queue as recommendation</button>
      </div>
    </header>
    <div class="prose prose-sm dark:prose-invert max-w-none text-sm break-words" v-html="rendered" />
    <footer v-if="tokenLabel" class="mt-2 text-[10px] text-slate-500">{{ tokenLabel }}</footer>
  </article>
</template>

<style scoped>
:deep(pre) {
  background: rgba(0,0,0,0.06);
  padding: 0.5rem 0.75rem;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 0.75rem;
}
:deep(code) {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
:deep(a) { text-decoration: underline; }
:deep(ul), :deep(ol) { padding-left: 1.25rem; }
</style>
