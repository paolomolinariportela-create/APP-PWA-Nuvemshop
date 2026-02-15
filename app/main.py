import os
from fastapi import FastAPI, Depends, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

# --- IMPORTS INTERNOS (Garantindo que os caminhos estão certos) ---
from .database import engine, Base, get_db
# Nota: Usamos 'Store' pois é onde adicionamos os campos app_name, theme_color, etc.
from .models import Store 

# --- IMPORTANDO AS ROTAS ---
from .routes import auth_routes, admin_routes, stats_routes
# Não importamos pwa_routes aqui para manter a lógica centralizada neste arquivo por segurança

# Inicializa as tabelas do Banco de Dados
Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- CONFIGURAÇÃO DE AMBIENTE ---
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

# --- CORS (Permite que a Nuvemshop e o Frontend acessem) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUINDO AS ROTAS PRINCIPAIS ---
app.include_router(auth_routes.router)  # Autenticação
app.include_router(admin_routes.router) # Painel Admin (antigo config_routes)
app.include_router(stats_routes.router) # Estatísticas e Loader Script

# --- ROTA DE SAÚDE (HEALTH CHECK) ---
@app.get("/")
def health_check():
    return {"status": "Online 🚀", "service": "App Builder Pro - Backend"}

# --- ROTAS DO PWA (MANIFESTO E SERVICE WORKER) ---

@app.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    """
    Gera o manifesto PWA dinamicamente para cada loja.
    O Google usa isso para saber como instalar o app.
    """
    try:
        # Busca na tabela Store (onde estão os dados da loja)
        store = db.query(Store).filter(Store.store_id == store_id).first()
    except Exception as e:
        print(f"Erro ao buscar loja: {e}")
        store = None

    # Valores Padrão (Fallback) caso a loja não tenha configurado
    # Importante: Verifique se sua tabela Store tem os campos app_name, theme_color, etc.
    app_name = store.app_name if (store and getattr(store, "app_name", None)) else "Minha Loja"
    theme_color = store.theme_color if (store and getattr(store, "theme_color", None)) else "#000000"
    background_color = store.background_color if (store and getattr(store, "background_color", None)) else "#ffffff"
    
    # Ícone: Usa o da loja ou um genérico
    icon_src = store.app_icon_url if (store and getattr(store, "app_icon_url", None)) else "https://cdn-icons-png.flaticon.com/512/3081/3081559.png"
    
    # Retorna o JSON exato que o Android/iOS exige
    return JSONResponse({
        "name": app_name,
        "short_name": app_name[:12], # Nome curto para a tela inicial
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

@app.get("/service-worker.js")
def get_service_worker():
    """
    Script vital para o funcionamento do PWA e Push Notifications.
    Este arquivo deve ser servido com cabeçalho Javascript.
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

    self.addEventListener('push', function(event) {
        if (!(self.Notification && self.Notification.permission === 'granted')) {
            return;
        }

        const data = event.data ? event.data.json() : {};
        const title = data.title || 'Nova Mensagem';
        const options = {
            body: data.body || 'Toque para ver mais.',
            icon: data.icon || '/icon.png',
            vibrate: [100, 50, 100],
            data: { url: data.url || '/' }
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
# Isso deve ser SEMPRE a última coisa do arquivo
# Verifica se existe a pasta de build do React para servir os arquivos estáticos
frontend_path = None
if os.path.exists("frontend/dist"):
    frontend_path = "frontend/dist"
elif os.path.exists("dist"):
    frontend_path = "dist"

if frontend_path:
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    # Se não tiver frontend buildado, avisa na raiz (útil para debug)
    print("Aviso: Pasta 'dist' não encontrada. O Frontend não será servido.")
