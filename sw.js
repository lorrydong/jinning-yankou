// 晋宁焰口 · 离线缓存 Service Worker
const CACHE_STATIC = 'yankou-static-v2';
const CACHE_PAGES = 'yankou-pages-v2';

const STATIC_FILES = ['/', '/index.html', '/dianduban.html', '/annotations.json'];
const TOTAL_PAGES = 203;
const AUDIO_FILES = ['audio-a.mp3', 'audio-b.mp3'];

// ===== Install: pre-cache small static files =====
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_STATIC).then(cache => cache.addAll(STATIC_FILES))
    .then(() => self.skipWaiting())
  );
});

// ===== Activate: clean old caches =====
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k.startsWith('yankou-') && ![CACHE_STATIC, CACHE_PAGES].includes(k))
        .map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

// ===== Fetch: cache-first (handles ALL caching) =====
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  let targetCache;
  if (AUDIO_FILES.some(f => url.pathname.endsWith(f))) {
    // Audio: let browser handle natively (Range requests, streaming)
    return;
  }
  if (url.pathname.includes('/pages/page-')) {
    targetCache = CACHE_PAGES;
  } else {
    targetCache = CACHE_STATIC;
  }

  event.respondWith(
    caches.match(event.request).then(cached => {
      if (cached) return cached;
      return fetch(event.request).then(response => {
        if (!response || response.status !== 200) return response;
        const clone = response.clone();
        caches.open(targetCache).then(cache => cache.put(event.request, clone));
        return response;
      });
    })
  );
});

// ===== Message API =====
self.addEventListener('message', event => {
  const { action } = event.data || {};
  if (action === 'cacheStatus') reportCacheStatus(event.source);
  else if (action === 'precacheAll') precacheAllPages(event.source);
  else if (action === 'precacheAudio') precacheAudio(event.source);
});

function reportCacheStatus(client) {
  Promise.all([
    countInCache(CACHE_PAGES, 'page-'),
    countInCache(CACHE_STATIC, '.html')
  ]).then(([pages]) => {
    try {
      client.postMessage({
        action: 'cacheStatus',
        pages, totalPages: TOTAL_PAGES,
        audio: 'N/A', totalAudio: AUDIO_FILES.length
      });
    } catch(e) { /* client may be gone */ }
  });
}

function countInCache(cacheName, pattern) {
  return caches.open(cacheName).then(cache =>
    cache.keys().then(keys =>
      keys.filter(r => {
        const u = typeof r === 'string' ? r : r.url;
        return u.includes(pattern);
      }).length
    )
  );
}

// Just fetch each URL — the SW's fetch handler will cache them automatically.
// No manual cache.put needed, avoiding double-caching conflicts.
async function precacheAllPages(client) {
  for (let i = 1; i <= TOTAL_PAGES; i++) {
    const url = `pages/page-${String(i).padStart(3, '0')}.png`;
    try {
      const resp = await fetch(url);
      try {
        client.postMessage({
          action: 'cacheProgress', type: 'page',
          current: i, total: TOTAL_PAGES,
          ok: resp.ok
        });
      } catch(e) { /* client gone, stop */ return; }
    } catch (e) {
      try {
        client.postMessage({
          action: 'cacheProgress', type: 'page',
          current: i, total: TOTAL_PAGES,
          ok: false, error: e.message
        });
      } catch(e2) { return; }
    }
  }
  try { client.postMessage({ action: 'cacheComplete', type: 'pages' }); } catch(e) {}
}

async function precacheAudio(client) {
  for (let idx = 0; idx < AUDIO_FILES.length; idx++) {
    const file = AUDIO_FILES[idx];
    try {
      const resp = await fetch(file);
      try {
        client.postMessage({
          action: 'cacheProgress', type: 'audio',
          current: idx + 1, total: AUDIO_FILES.length,
          file, ok: resp.ok
        });
      } catch(e) { return; }
    } catch (e) {
      try {
        client.postMessage({
          action: 'cacheProgress', type: 'audio',
          current: idx + 1, total: AUDIO_FILES.length,
          file, ok: false, error: e.message
        });
      } catch(e2) { return; }
    }
  }
  try { client.postMessage({ action: 'cacheComplete', type: 'audio' }); } catch(e) {}
}
