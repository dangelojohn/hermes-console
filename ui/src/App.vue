<script setup>
import { onMounted, onBeforeUnmount, ref, computed } from 'vue';
import { useRouter, RouterView, RouterLink } from 'vue-router';
import { useHermesStore } from './stores/hermes.js';
import StatusBanner from './components/StatusBanner.vue';
import Toast from './components/Toast.vue';

const store = useHermesStore();
const router = useRouter();
const navOpen = ref(false);

const readyCount = computed(() => store.readyCount);
const chatPending = computed(() => store.chatHasPending);
const queueDepth = computed(() => store.queueDepth);

function onSwMessage(ev) {
  if (ev.data?.type === 'hermes-offline') store.markOffline(ev.data.cachedAt);
}

function onKey(ev) {
  if (ev.key === 'Escape') {
    if (navOpen.value) { navOpen.value = false; return; }
    if (router.currentRoute.value.name === 'detail') {
      router.push({ name: 'queue' });
    }
  }
}

function closeNav() { navOpen.value = false; }

onMounted(() => {
  store.startHealthPolling();
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('message', onSwMessage);
  }
  window.addEventListener('keydown', onKey);
  window.addEventListener('online', () => store.clearOffline());
});

onBeforeUnmount(() => {
  store.stopHealthPolling();
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.removeEventListener('message', onSwMessage);
  }
  window.removeEventListener('keydown', onKey);
});
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <StatusBanner />

    <header class="sticky top-10 z-30 border-b border-slate-200 dark:border-slate-800 bg-white/80 dark:bg-slate-900/80 backdrop-blur">
      <div class="mx-auto max-w-6xl px-4 py-2 flex items-center justify-between gap-3">
        <div class="flex items-center gap-2 min-w-0">
          <img :src="store.health.tenant_icon || '/icons/icon-192.svg'" alt="" class="h-7 w-7 rounded" />
          <span class="font-semibold tracking-tight truncate">{{ store.health.tenant_label || 'Hermes' }}</span>
          <span class="text-xs text-slate-500 hidden sm:inline">/ Hermes Console</span>
        </div>

        <nav class="hidden sm:flex items-center gap-1 text-sm" aria-label="Primary">
          <RouterLink to="/" class="btn-ghost" active-class="bg-slate-200 dark:bg-slate-800">
            Queue
            <span v-if="readyCount > 0" class="pill-info ml-1">{{ readyCount }}</span>
          </RouterLink>
          <RouterLink to="/chat" class="btn-ghost" active-class="bg-slate-200 dark:bg-slate-800">
            Chat
            <span v-if="chatPending" class="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse ml-1" title="Pending reply" />
          </RouterLink>
          <RouterLink to="/queue" class="btn-ghost" active-class="bg-slate-200 dark:bg-slate-800">
            Pending
            <span v-if="queueDepth > 0" class="pill-info ml-1">{{ queueDepth }}</span>
          </RouterLink>
          <RouterLink to="/tenants" class="btn-ghost" active-class="bg-slate-200 dark:bg-slate-800">Tenants</RouterLink>
          <RouterLink to="/agents" class="btn-ghost" active-class="bg-slate-200 dark:bg-slate-800">Agents</RouterLink>
        </nav>

        <button class="sm:hidden btn-ghost" :aria-expanded="navOpen" aria-label="Toggle navigation"
                @click="navOpen = !navOpen">
          <span aria-hidden="true">{{ navOpen ? '✕' : '☰' }}</span>
        </button>
      </div>

      <nav v-if="navOpen" class="sm:hidden border-t border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900" aria-label="Mobile">
        <div class="px-4 py-2 grid grid-cols-1 gap-1 text-sm">
          <RouterLink @click="closeNav" to="/" class="btn-ghost justify-start" active-class="bg-slate-200 dark:bg-slate-800">
            Queue <span v-if="readyCount > 0" class="pill-info ml-2">{{ readyCount }}</span>
          </RouterLink>
          <RouterLink @click="closeNav" to="/chat" class="btn-ghost justify-start" active-class="bg-slate-200 dark:bg-slate-800">
            Chat <span v-if="chatPending" class="inline-block w-2 h-2 rounded-full bg-amber-500 animate-pulse ml-2" />
          </RouterLink>
          <RouterLink @click="closeNav" to="/queue" class="btn-ghost justify-start" active-class="bg-slate-200 dark:bg-slate-800">
            Pending <span v-if="queueDepth > 0" class="pill-info ml-2">{{ queueDepth }}</span>
          </RouterLink>
          <RouterLink @click="closeNav" to="/tenants" class="btn-ghost justify-start" active-class="bg-slate-200 dark:bg-slate-800">Tenants</RouterLink>
          <RouterLink @click="closeNav" to="/agents" class="btn-ghost justify-start" active-class="bg-slate-200 dark:bg-slate-800">Agents</RouterLink>
        </div>
      </nav>
    </header>

    <main class="flex-1 mx-auto max-w-6xl w-full px-4 py-4">
      <RouterView />
    </main>

    <footer class="text-center text-xs text-slate-500 py-4">
      Hermes Console
    </footer>

    <Toast />
  </div>
</template>
