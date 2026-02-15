import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- IMPORTS INTERNOS ---
from .database import engine, Base
# Importamos TODAS as rotas agora (as antigas e as novas)
from app.routes import auth_routes, admin_routes, loader_routes, push_routes, analytics_routes, pwa_routes


# Inicializa Banco
Base.metadata.create_all(bind=engine)

app = FastAPI()

# --- CONFIGURAÇÃO DE AMBIENTE ---
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUINDO AS ROTAS (Cada uma na sua função) ---
app.include_router(auth_routes.router)  
app.include_router(admin_routes.router) 
app.include_router(stats_routes.router) 
app.include_router(push_routes.router)      # NOVO
app.include_router(analytics_routes.router) # NOVO


# Novas Rotas Modulares (Observe o prefixo /pwa para ficar organizado)
app.include_router(pwa_routes.router, prefix="/pwa", tags=["PWA"]) 
app.include_router(loader_routes.router, tags=["Loader"]) 

# --- ROTA DE SAÚDE ---
@app.get("/health")
def health_check():
    return {"status": "Online 🚀", "service": "App Builder Pro - Modular"}

# --- SERVINDO O FRONTEND (Sempre por último) ---
frontend_path = None
if os.path.exists("frontend/dist"):
    frontend_path = "frontend/dist"
elif os.path.exists("dist"):
    frontend_path = "dist"

if frontend_path:
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print("Aviso: Frontend não encontrado (normal se for apenas API)")
