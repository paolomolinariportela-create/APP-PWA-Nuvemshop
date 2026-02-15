import os
from fastapi import FastAPI, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# Imports Internos
from .database import engine, Base, get_db
from .models import AppConfig

# Importando as Rotas (O Loader está dentro de stats_routes agora!)
from .routes import auth_routes, admin_routes, stats_routes

# Inicializa Banco
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Variáveis Globais
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"

# CORS (Permite que a Nuvemshop acesse tudo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUINDO AS ROTAS ---
app.include_router(auth_routes.router)
app.include_router(admin_routes.router) # Use admin_routes se renomeou config_routes
app.include_router(stats_routes.router) # O Loader V3 está AQUI dentro!

# --- ROTAS PÚBLICAS GLOBAIS ---

@app.get("/health")
def health_check():
    return {"status": "Online 🚀", "service": "App Builder Pro"}

@app.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    """Gera o manifesto PWA dinâmico para cada loja"""
    try:
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except:
        config = None

    name = config.app_name if config else "Loja App"
    color = config.theme_color if config else "#000000"
    # Ícone padrão seguro
    icon = config.logo_url if config and config.logo_url else "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"
    
    return JSONResponse({
        "name": name,
        "short_name": name[:12],
        "start_url": f"/?utm_source=pwa_app&store_id={store_id}",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": color,
        "orientation": "portrait",
        "icons": [
            {
                "src": icon,
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": icon,
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    })

@app.get("/service-worker.js")
def get_service_worker():
    """Script vital para Push Notifications"""
    js = """
    self.addEventListener('push', function(event) {
        if (!(self.Notification && self.Notification.permission === 'granted')) {
            return;
        }

        const data = event.data ? event.data.json() : {};
        const title = data.title || 'Nova Mensagem';
        const options = {
            body: data.body || 'Toque para ver mais.',
            icon: data.icon || '/icon.png',
            badge: '/badge.png',
            vibrate: [100, 50, 100],
            data: {
                url: data.url || '/'
            }
        };

        event.waitUntil(
            self.registration.showNotification(title, options)
        );
    });

    self.addEventListener('notificationclick', function(event) {
        event.notification.close();
        
        event.waitUntil(
            clients.matchAll({type: 'window'}).then(function(windowClients) {
                for (var i = 0; i < windowClients.length; i++) {
                    var client = windowClients[i];
                    if (client.url === event.notification.data.url && 'focus' in client) {
                        return client.focus();
                    }
                }
                if (clients.openWindow) {
                    return clients.openWindow(event.notification.data.url);
                }
            })
        );
    });
    """
    return Response(content=js, media_type="application/javascript")

# --- SERVINDO O FRONTEND (REACT) ---
# Se a pasta 'dist' existir (gerada pelo build do React), servimos ela na raiz.
if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")
elif os.path.exists("dist"):
    app.mount("/", StaticFiles(directory="dist", html=True), name="frontend")
