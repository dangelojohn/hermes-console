<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import { useHermesStore } from '../stores/hermes.js';

const store = useHermesStore();
const router = useRouter();
const toasts = computed(() => store.toasts);

function cls(type) {
  switch (type) {
    case 'ok':   return 'bg-emerald-600 text-white';
    case 'warn': return 'bg-amber-500 text-amber-950';
    case 'err':  return 'bg-red-600 text-white';
    default:     return 'bg-slate-800 text-white';
  }
}

function onAction(t) {
  if (t.action?.to) router.push(t.action.to);
  store.dismissToast(t.id);
}
</script>

<template>
  <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 max-w-sm pointer-events-none">
    <transition-group name="toast">
      <div
        v-for="t in toasts" :key="t.id"
        :class="cls(t.type)"
        class="rounded-md shadow-lg px-3 py-2 text-sm pointer-events-auto flex items-center gap-3"
        role="status"
      >
        <span class="cursor-pointer flex-1" @click="store.dismissToast(t.id)">{{ t.message }}</span>
        <button
          v-if="t.action?.label"
          class="underline font-semibold whitespace-nowrap"
          @click="onAction(t)"
        >{{ t.action.label }}</button>
      </div>
    </transition-group>
  </div>
</template>

<style scoped>
.toast-enter-from { opacity: 0; transform: translateY(8px); }
.toast-enter-active, .toast-leave-active { transition: all 180ms ease; }
.toast-leave-to { opacity: 0; transform: translateY(8px); }
</style>
