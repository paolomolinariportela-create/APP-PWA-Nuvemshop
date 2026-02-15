from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
# CORREÇÃO 1: Importamos AppConfig, onde estão as cores e nomes
from app.models import AppConfig 

router = APIRouter()

@router.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    """
    Gera o manifesto PWA dinamicamente.
    """
    try:
        # CORREÇÃO 2: Buscamos na tabela certa (AppConfig)
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except Exception as e:
        print(f"Erro no banco PWA: {e}")
        config = None

    # Lógica de Fallback (Segurança se não tiver config)
    app_name = config.app_name if config else "Minha Loja"
    theme_color = config.theme_color if config else "#000000"
    background_color = "#ffffff"
    
    # Ícone seguro
    icon_src = config.logo_url if (config and config.logo_url) else "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"
    
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

# CORREÇÃO 3: Adicionamos a rota vital do Service Worker que faltava
@router.get("/service-worker.js")
def get_service_worker():
    """
    Script vital para Push Notifications e Cache Offline.
    O navegador exige que este arquivo exista para permitir a instalação.
    """
    js_content = """
    self.addEventListener('install', (event) => {
        console.log('Service Worker: Instalado');
        self.skipWaiting();
    });

    self.addEventListener('activate', (event) => {
        console.log('Service Worker: Ativo');
        return self.clients.claim();
    });
    
    // Lógica básica de Push (Preparo para o futuro)
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
    # Importante: Retorna como Javascript, não como JSON
    return Response(content=js_content, media_type="application/javascript")
