import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- IMPORTS INTERNOS ---
from app.database import engine, Base
# Importamos as rotas (Modularizadas)
# Nota: stats_routes foi removido pois foi dividido em loader, push e analytics
from app.routes import (
    auth_routes, 
    admin_routes, 
    loader_routes, 
    push_routes, 
    analytics_routes, 
    pwa_routes
)

# Inicializa as tabelas do Banco de Dados
Base.metadata.create_all(bind=engine)

# Cria a aplicação FastAPI
app = FastAPI(
    title="App Builder Pro API",
    description="API Modular para criação de PWAs, Push Notifications e Analytics.",
    version="2.0.0"
)

# --- CONFIGURAÇÃO DE CORS ---
# Permite que o painel admin e as lojas acessem a API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, ideal restringir aos domínios dos clientes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REGISTRO DAS ROTAS (ROUTERS) ---

# 1. Autenticação e Admin
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)

# 2. Funcionalidades do App (Antigo stats_routes dividido)
# O Loader não tem prefixo pois o script é acessado como /loader.js
app.include_router(loader_routes.router, tags=["Loader"]) 

# Rotas de Push (/push/subscribe, /push/send, /push/history)
app.include_router(push_routes.router) 

# Rotas de Analytics (/analytics/dashboard, /analytics/visita, /analytics/venda)
app.include_router(analytics_routes.router)

# 3. Arquivos do PWA (Manifest, Service Worker)
# Prefixo /pwa ou raiz, dependendo de como definiu no pwa_routes. 
# Geralmente manifest e sw ficam na raiz ou em /pwa. Vamos manter sem prefixo se o arquivo pwa_routes já tiver os caminhos certos.
app.include_router(pwa_routes.router, tags=["PWA"])


# --- ROTA DE SAÚDE (HEALTH CHECK) ---
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "Online 🚀", "service": "App Builder Pro - Modular API"}


# --- SERVINDO O FRONTEND (Sempre por último) ---
# Tenta servir os arquivos estáticos do React se existirem
frontend_path = None
if os.path.exists("frontend/dist"):
    frontend_path = "frontend/dist"
elif os.path.exists("dist"):
    frontend_path = "dist"

if frontend_path:
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
    print(f"✅ Frontend servido de: {frontend_path}")
else:
    print("⚠️ Aviso: Pasta do Frontend não encontrada (API rodando em modo headless)")

# Fim do arquivo main.py
