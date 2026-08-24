// RevenueSeva Service Worker — Phase 9 PWA
// Strategies:
//   - Network-first for API calls
//   - Cache-first for static assets
//   - Offline fallback for navigation

const CACHE_NAME = 'revenue-seva-v1'
const API_BASE = 'http://localhost:8000/api'

// Assets to pre-cache on install
const PRECACHE_URLS = [
  '/',
  '/status',
  '/services',
  '/offline.html',
]

// ── Install ──────────────────────────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch(() => {
        // Non-fatal if some resources aren't available
      })
    })
  )
  self.skipWaiting()
})

// ── Activate ─────────────────────────────────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  )
  self.clients.claim()
})

// ── Fetch Strategy ───────────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event
  const url = new URL(request.url)

  // Skip non-GET requests
  if (request.method !== 'GET') return

  // Skip SSE streams — never cache
  if (url.pathname.includes('/stream/')) return

  // API: Network-first with short timeout, fallback to cache
  if (url.href.startsWith(API_BASE)) {
    event.respondWith(networkFirstWithCache(request))
    return
  }

  // Static assets: Cache-first
  if (
    url.pathname.match(/\.(js|css|woff2?|png|jpg|svg|ico)$/)
  ) {
    event.respondWith(cacheFirst(request))
    return
  }

  // Navigation: Network-first, offline fallback
  if (request.mode === 'navigate') {
    event.respondWith(navigationHandler(request))
    return
  }
})

// ── Strategy Implementations ──────────────────────────────────────────────

async function networkFirstWithCache(request) {
  const cache = await caches.open(CACHE_NAME)
  try {
    const response = await fetch(request.clone(), { signal: AbortSignal.timeout(5000) })
    if (response.ok) {
      cache.put(request, response.clone())
    }
    return response
  } catch {
    const cached = await cache.match(request)
    return cached || new Response(JSON.stringify({ error: 'offline', cached: false }), {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request)
  if (cached) return cached
  try {
    const response = await fetch(request)
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME)
      cache.put(request, response.clone())
    }
    return response
  } catch {
    return new Response('', { status: 408 })
  }
}

async function navigationHandler(request) {
  try {
    return await fetch(request)
  } catch {
    const cached = await caches.match('/')
    return cached || caches.match('/offline.html') || new Response('<h1>Offline</h1><p>No internet connection.</p>', {
      headers: { 'Content-Type': 'text/html' },
    })
  }
}

// ── Background Sync for offline form submissions ──────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'sync-pending-messages') {
    event.waitUntil(syncPendingMessages())
  }
})

async function syncPendingMessages() {
  // Read from IndexedDB and retry failed API calls
  // (Simplified — full implementation would use idb-keyval)
  const clients = await self.clients.matchAll()
  clients.forEach((client) => {
    client.postMessage({ type: 'SYNC_COMPLETE' })
  })
}
