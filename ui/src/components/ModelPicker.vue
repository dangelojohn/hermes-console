<script setup>
import { computed } from 'vue';
import { useHermesStore } from '../stores/hermes.js';

const props = defineProps({
  modelValue: { type: Object, default: () => ({ provider: '', model: '' }) },
  disabled: { type: Boolean, default: false },
});
const emit = defineEmits(['update:modelValue']);

const store = useHermesStore();

// Discover providers + their models from /api/health.
// Expected shape (lenient): health.llm = { openai: 'ok'|'unavailable', ... }
// and optionally health.llm_models = { openai: ['gpt-4o', 'gpt-4o-mini'], hermes: [...] }
const providers = computed(() => {
  const llm = store.health.llm || {};
  const models = store.health.llm_models || {};
  return Object.keys(llm).map((p) => ({
    name: p,
    status: llm[p],
    models: Array.isArray(models[p]) && models[p].length
      ? models[p]
      : defaultModelsFor(p),
  }));
});

function defaultModelsFor(provider) {
  switch (provider) {
    case 'openai':  return ['gpt-4o', 'gpt-4o-mini', 'o1-preview'];
    case 'hermes':  return ['hermes-harness'];
    case 'anthropic': return ['claude-opus-4-7', 'claude-sonnet-4-7'];
    default: return ['default'];
  }
}

function prettyProvider(p) {
  if (p === 'openai') return 'OpenAI';
  if (p === 'hermes') return 'Hermes Harness';
  if (p === 'anthropic') return 'Anthropic';
  return p;
}

const currentKey = computed(() => {
  const v = props.modelValue || {};
  return v.provider && v.model ? `${v.provider}::${v.model}` : '';
});

function onChange(ev) {
  const v = ev.target.value;
  // "Default" → emit null/null so the API falls back to thread default
  // and ultimately to settings.hermes_primary_provider. Sending empty
  // strings would 422 against Pydantic's Literal["openai", "hermes_harness"].
  if (!v) { emit('update:modelValue', { provider: null, model: null }); return; }
  const [provider, model] = v.split('::');
  emit('update:modelValue', { provider, model });
}
</script>

<template>
  <label class="inline-flex items-center gap-1 text-xs">
    <span class="text-slate-500">Model</span>
    <select
      :value="currentKey"
      :disabled="disabled || providers.length === 0"
      class="rounded border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs py-1 px-1.5"
      @change="onChange"
    >
      <option value="">Default</option>
      <optgroup v-for="p in providers" :key="p.name" :label="`${prettyProvider(p.name)} (${p.status || 'unknown'})`">
        <option v-for="m in p.models" :key="`${p.name}::${m}`" :value="`${p.name}::${m}`">{{ m }}</option>
      </optgroup>
    </select>
  </label>
</template>
