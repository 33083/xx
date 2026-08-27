/* 轻量 Service Worker：生产构建静态资源缓存 + 离线回退 */
const CACHE = 'campus-assistant-v1'

self.addEventListener('install', (e) => {
  self.skipWaiting()
})

self.addEventListener('activate', (e) => {
  e.waitUntil(self.clients.claim())
})

self.addEventListener('fetch', (e) => {
  const req = e.request
  if (req.method !== 'GET') return
  const url = new URL(req.url)
  // 接口与上传资源不缓存
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/uploads/')) return

  e.respondWith(
    caches.open(CACHE).then(async (cache) => {
      try {
        const fresh = await fetch(req)
        if (fresh && fresh.ok && url.origin === self.location.origin) {
          cache.put(req, fresh.clone())
        }
        return fresh
      } catch (_) {
        const cached = await cache.match(req)
        if (cached) return cached
        if (req.mode === 'navigate') {
          const idx = await cache.match('/index.html')
          if (idx) return idx
        }
        return new Response('', { status: 408 })
      }
    }),
  )
})
