import os
from fastapi import FastAPI, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# --- IMPORTS INTERNOS (Corrigidos para evitar duplicidade) ---
from .database import engine, Base, get_db
from .models import AppConfig # Usando o modelo correto do seu arquivo models.py

# --- IMPORTANDO AS ROTAS ---
# Removemos 'pwa_routes' daqui porque a lógica está abaixo neste mesmo arquivo
from .routes import auth_routes, admin_routes, stats_routes 

# Inicializa as tabelas do Banco de Dados
Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- CONFIGURAÇÃO DE AMBIENTE ---
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

# --- CORS (Permite acesso global da Nuvemshop e Lojas) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUINDO AS ROTAS PRINCIPAIS ---
app.include_router(auth_routes.router)
app.include_router(admin_routes.router) # Painel Admin
app.include_router(stats_routes.router) # Estatísticas e Loader Script

# --- ROTA DE SAÚDE (HEALTH CHECK) ---
@app.get("/health")
def health_check():
    return {"status": "Online 🚀", "service": "App Builder Pro"}

# --- ROTAS DO PWA (MANIFESTO E SERVICE WORKER) ---

@app.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    """
    Gera o manifesto PWA dinamicamente para cada loja.
    O Google usa isso para saber como instalar o app.
    """
    try:
        # Busca a configuração específica da loja
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except Exception as e:
        # Log de erro silencioso para não quebrar a requisição
        print(f"Erro ao buscar config PWA: {e}")
        config = None

    # Valores Padrão (Fallback)
    name = config.app_name if config else "Loja App"
    color = config.theme_color if config else "#000000"
    
    # Ícone: Usa o configurado ou um genérico seguro
    icon = config.logo_url if (config and config.logo_url) else "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"
    
    # Retorna o JSON exato que o Android/iOS exige
    return JSONResponse({
        "name": name,
        "short_name": name[:12], # Nome curto para a tela inicial
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
    """
    Script vital para Push Notifications e Cache Offline.
    """
    js_content = """
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
    return Response(content=js_content, media_type="application/javascript")

# --- SERVINDO O FRONTEND (REACT) ---
# Isso deve ser SEMPRE a última coisa do arquivo para não bloquear as rotas de API
frontend_path = None
if os.path.exists("frontend/dist"):
    frontend_path = "frontend/dist"
elif os.path.exists("dist"):
    frontend_path = "dist"

if frontend_path:
    # Serve os arquivos estáticos (JS, CSS, Imagens)
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print("Aviso: Pasta 'dist' não encontrada. O Frontend não será servido na raiz.")
