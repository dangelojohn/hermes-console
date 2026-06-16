/* Hermes Console service worker.
 * - precaches the app shell on install
 * - stale-while-revalidate for /api/health, /api/recommendations, and /api/chat/threads* (10 min freshness)
 * - falls back to last cached response when offline
 * The Offline banner in StatusBanner.vue listens for the 'hermes-offline' message we post here.
 */
const SHELL_CACHE = 'hermes-shell-v2';
const API_CACHE = 'hermes-api-v2';
const FRESH_MS = 10 * 60 * 1000;
const SHELL_URLS = ['/', '/index.html', '/manifest.webmanifest', '/icons/icon-192.svg', '/icons/icon-512.svg'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(SHELL_CACHE).then((c) => c.addAll(SHELL_URLS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => ![SHELL_CACHE, API_CACHE].includes(k)).map((k) => caches.delete(k))),
    ).then(() => self.clients.claim()),
  );
});

function isCachableApi(url) {
  if (url.pathname === '/api/health') return true;
  if (url.pathname.startsWith('/api/recommendations')) return true;
  // /api/chat/threads and /api/chat/threads/{id}/messages — but NOT POSTs (we filter on method below)
  if (url.pathname === '/api/chat/threads') return true;
  if (/^\/api\/chat\/threads\/[^/]+\/messages\/?$/.test(url.pathname)) return true;
  return false;
}

async function broadcast(msg) {
  const clients = await self.clients.matchAll({ includeUncontrolled: true });
  clients.forEach((c) => c.postMessage(msg));
}

async function swrFetch(request) {
  const cache = await caches.open(API_CACHE);
  const cached = await cache.match(request);
  const networkPromise = fetch(request).then((resp) => {
    if (resp && resp.ok) {
      const cloned = resp.clone();
      const stamped = new Response(cloned.body, {
        status: cloned.status,
        statusText: cloned.statusText,
        headers: new Headers(cloned.headers),
      });
      stamped.headers.set('x-hermes-cached-at', String(Date.now()));
      cache.put(request, stamped);
    }
    return resp;
  }).catch(() => null);

  if (cached) {
    const stamp = Number(cached.headers.get('x-hermes-cached-at') || 0);
    if (Date.now() - stamp < FRESH_MS) return cached;
    const fresh = await networkPromise;
    if (fresh) return fresh;
    broadcast({ type: 'hermes-offline', cachedAt: stamp });
    return cached;
  }
  const fresh = await networkPromise;
  if (fresh) return fresh;
  return new Response(JSON.stringify({ error: 'offline' }), {
    status: 503,
    headers: { 'content-type': 'application/json' },
  });
}

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (event.request.method === 'GET' && isCachableApi(url)) {
    event.respondWith(swrFetch(event.request));
    return;
  }
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/index.html')),
    );
  }
});
