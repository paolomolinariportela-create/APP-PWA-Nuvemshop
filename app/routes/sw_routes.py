# app/routes/sw_routes.py
from fastapi import APIRouter, Response

sw_router = APIRouter()

@sw_router.get("/sw.js", include_in_schema=False)
def service_worker():
    sw_code = """
const CACHE_NAME = 'app-builder-cache-v1';
const PRECACHE_URLS = [
  '/sw.js',
  '/favicon.ico'
];

self.addEventListener('install', (event) => {
  console.log('Service Worker: Instalado');
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch((err) => {
        console.warn('SW: erro ao fazer precache', err);
      });
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  console.log('Service Worker: Ativo');
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((key) => {
          if (key !== CACHE_NAME) {
            console.log('SW: removendo cache antigo', key);
            return caches.delete(key);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const acceptHeader = req.headers.get('Accept') || '';

  if (acceptHeader.includes('text/html')) {
    return;
  }

  if (
    req.url.includes('/manifest') ||
    req.url.endsWith('.js') ||
    req.url.endsWith('.css') ||
    req.url.endsWith('.png') ||
    req.url.endsWith('.jpg') ||
    req.url.endsWith('.jpeg') ||
    req.url.endsWith('.svg') ||
    req.url.endsWith('.ico') ||
    req.url.includes('/sw.js')
  ) {
    event.respondWith(
      caches.match(req).then((cachedResponse) => {
        const fetchPromise = fetch(req)
          .then((networkResponse) => {
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(req, networkResponse.clone());
            });
            return networkResponse;
          })
          .catch((err) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            throw err;
          });

        return cachedResponse || fetchPromise;
      })
    );
  }
});

self.addEventListener('push', function(event) {
  if (!(self.Notification && self.Notification.permission === 'granted')) return;
  const data = event.data ? event.data.json() : {};
  event.waitUntil(
    self.registration.showNotification(data.title || 'Novidade na Loja', {
      body: data.body || 'Toque para conferir!',
      icon: data.icon || '/icon.png',
      data: { url: data.url || '/' }
    })
  );
});

self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  event.waitUntil(clients.openWindow(event.notification.data.url));
});
"""
    return Response(content=sw_code, media_type="application/javascript")
