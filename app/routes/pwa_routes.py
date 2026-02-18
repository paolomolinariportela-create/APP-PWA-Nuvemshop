from fastapi import APIRouter, Depends, Response, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppConfig 
# A validação de HMAC foi removida da rota do SW para permitir acesso público do navegador
# from app.security import validate_proxy_hmac 

router = APIRouter()

@router.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    """
    Gera o manifesto PWA dinamicamente.
    """
    try:
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except Exception as e:
        print(f"Erro no banco PWA: {e}")
        config = None

    # Fallbacks seguros
    app_name = config.app_name if config else "Minha Loja"
    theme_color = config.theme_color if (config and config.theme_color) else "#000000"
    background_color = theme_color  # usa a mesma cor do tema como fundo
    
    icon_src = (
        config.logo_url
        if (config and config.logo_url)
        else "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"
    )
    
    return JSONResponse({
        "name": app_name,
        "short_name": app_name[:12],
        "start_url": f"/?utm_source=pwa_app&store_id={store_id}",
        "display": "standalone",
        "background_color": background_color,
        "theme_color": theme_color,
        "orientation": "portrait",
        "icons": [
            {
                "src": icon_src,
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": icon_src,
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })

@router.get("/service-worker.js")
def get_service_worker():
    """
    Service Worker para Push Notifications e Cache básico.
    ACESSO PÚBLICO LIBERADO (Sem validação HMAC) para que o navegador consiga baixar.
    """
    js_content = """
    const CACHE_NAME = 'app-builder-cache-v1';
    const PRECACHE_URLS = [
        // Arquivos essenciais do PWA (ajuste caminhos se necessário)
        '/service-worker.js',
        '/favicon.ico'
        // Você pode adicionar aqui ícones locais, ex: '/icon-192.png', '/icon-512.png'
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

    // Estratégia de cache simples:
    // - Arquivos estáticos (js, css, imagens, manifest): stale-while-revalidate
    // - HTML / páginas da loja: rede primeiro (não cacheamos agressivo)
    self.addEventListener('fetch', (event) => {
        const req = event.request;

        // Só lidamos com GET
        if (req.method !== 'GET') {
            return;
        }

        const acceptHeader = req.headers.get('Accept') || '';

        // Se for navegação HTML (páginas da loja), deixamos seguir pela rede
        if (acceptHeader.includes('text/html')) {
            return;
        }

        // Para arquivos estáticos: aplicamos stale-while-revalidate
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
                            // Atualiza o cache em segundo plano
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

                    // Se tiver cache, retorna rápido, mas ainda busca rede
                    return cachedResponse || fetchPromise;
                })
            );
        }
        // Qualquer outra requisição (ex: APIs da loja) passa direto
    });
    
    // Push Notifications
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
    return Response(
        content=js_content,
        media_type="application/javascript",
        headers={
            "Service-Worker-Allowed": "/",
            "Cache-Control": "public, max-age=3600"
        }
    )
