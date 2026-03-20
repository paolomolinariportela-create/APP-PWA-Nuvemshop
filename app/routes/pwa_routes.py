from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppConfig, Loja

router = APIRouter()


@router.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    try:
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except Exception as e:
        print(f"Erro no banco PWA (config): {e}")
        config = None

    try:
        loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    except Exception as e:
        print(f"Erro no banco PWA (loja): {e}")
        loja = None

    app_name = config.app_name if config else "Minha Loja"
    theme_color = config.theme_color if (config and config.theme_color) else "#000000"
    background_color = theme_color
    icon_src = (
        config.logo_url
        if (config and config.logo_url)
        else "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"
    )

    # ✅ start_url absoluto com domínio real da loja
    store_url = loja.url if (loja and loja.url) else None
    if store_url:
        if not store_url.startswith("http"):
            store_url = f"https://{store_url}"
        store_url = store_url.rstrip("/")
        start_url = f"{store_url}/?utm_source=pwa_app&store_id={store_id}"
    else:
        start_url = f"/?utm_source=pwa_app&store_id={store_id}"

    return JSONResponse({
        "name": app_name,
        "short_name": app_name[:12],
        "start_url": start_url,
        "display": "standalone",
        "background_color": background_color,
        "theme_color": theme_color,
        "orientation": "portrait",
        "icons": [
            {"src": icon_src, "sizes": "192x192", "type": "image/png"},
            {"src": icon_src, "sizes": "512x512", "type": "image/png"}
        ]
    })


# Conteúdo do Service Worker — compartilhado por todas as rotas
SW_CONTENT = """
importScripts("https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.sw.js");

const CACHE_NAME = 'app-builder-cache-v1';
const PRECACHE_URLS = [
    '/service-worker.js',
    '/favicon.ico'
];

self.addEventListener('install', (event) => {
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
    event.waitUntil(
        caches.keys().then((keys) => {
            return Promise.all(
                keys.map((key) => {
                    if (key !== CACHE_NAME) {
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
    if (acceptHeader.includes('text/html')) return;
    if (
        req.url.includes('/manifest') ||
        req.url.endsWith('.js') ||
        req.url.endsWith('.css') ||
        req.url.endsWith('.png') ||
        req.url.endsWith('.jpg') ||
        req.url.endsWith('.jpeg') ||
        req.url.endsWith('.svg') ||
        req.url.endsWith('.ico') ||
        req.url.includes('/service-worker.js')
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
                        if (cachedResponse) return cachedResponse;
                        throw err;
                    });
                return cachedResponse || fetchPromise;
            })
        );
    }
});
"""

SW_HEADERS = {
    "Service-Worker-Allowed": "/",
    "Cache-Control": "no-cache, no-store, must-revalidate"
}


def sw_response():
    return Response(
        content=SW_CONTENT,
        media_type="application/javascript",
        headers=SW_HEADERS
    )


@router.get("/service-worker.js")
def get_service_worker():
    """Rota direta — usada internamente."""
    return sw_response()


@router.get("/sw.js")
def get_service_worker_root():
    """Fallback sem prefixo."""
    return sw_response()


@router.get("/app-builder/sw.js")
def get_service_worker_proxy_sw():
    """Proxy Nuvemshop — /app-builder/sw.js"""
    return sw_response()


@router.get("/app-builder/service-worker.js")
def get_service_worker_proxy():
    """
    ✅ Rota principal via proxy Nuvemshop.
    loja.com/apps/app-builder/service-worker.js
    → railway/app-builder/service-worker.js
    """
    return sw_response()
