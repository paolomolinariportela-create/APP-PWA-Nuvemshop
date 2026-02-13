import os
import requests
from fastapi import FastAPI, Depends, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from .database import engine, Base, get_db
from .models import Loja, AppConfig

# Recria as tabelas limpas
Base.metadata.create_all(bind=engine)
app = FastAPI() Query

# Configurações
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
# IMPORTANTE: Esse é o link do seu Backend no Railway (ex: https://pwa-backend.up.railway.app)
BACKEND_URL = os.getenv("PUBLIC_URL") 
FRONTEND_URL = os.getenv("FRONTEND_URL") # Painel Admin

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConfigPayload(BaseModel):
    store_id: str
    app_name: str
    theme_color: str
    logo_url: Optional[str] = None
    whatsapp: Optional[str] = None

# --- 1. CONFIGURAÇÃO (PAINEL ADMIN) ---

@app.get("/admin/config/{store_id}")
def get_config(store_id: str, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return {"app_name": "Minha Loja", "theme_color": "#000000", "logo_url": ""}
    return config

@app.post("/admin/config")
def save_config(payload: ConfigPayload, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == payload.store_id).first()
    if not config:
        config = AppConfig(store_id=payload.store_id)
        db.add(config)
    
    config.app_name = payload.app_name
    config.theme_color = payload.theme_color
    config.logo_url = payload.logo_url
    config.whatsapp_number = payload.whatsapp
    db.commit()
    return {"status": "success"}

# --- 2. MANIFESTO (PARA INSTALAR O APP) ---

@app.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    
    name = config.app_name if config else "Minha Loja"
    color = config.theme_color if config else "#000000"
    icon = config.logo_url if config and config.logo_url else "https://via.placeholder.com/512"

    manifest = {
        "name": name,
        "short_name": name,
        "start_url": "/", # Abre a home da loja
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": color,
        "icons": [{"src": icon, "sizes": "512x512", "type": "image/png"}]
    }
    return JSONResponse(content=manifest)

# --- 3. O SCRIPT MÁGICO (O QUE VAI NA LOJA) ---

@app.get("/loader.js")
def get_loader_script(store_id: str, db: Session = Depends(get_db)):
    """Gera o Javascript que transforma o site em App"""
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    
    color = config.theme_color if config else "#000000"
    
    # Este é o código Javascript que será injetado na loja do cliente
    js_code = f"""
    (function() {{
        console.log("PWA Injector Iniciado 🚀");
        
        // 1. Injetar o Manifesto
        var link = document.createElement('link');
        link.rel = 'manifest';
        link.href = '{BACKEND_URL}/manifest/{store_id}.json';
        document.head.appendChild(link);
        
        // 2. Configurar cor do navegador
        var meta = document.createElement('meta');
        meta.name = 'theme-color';
        meta.content = '{color}';
        document.head.appendChild(meta);

        // 3. Criar a Barra de Navegação (Menu Fundo) se estiver no celular
        if (window.innerWidth < 768) {{
            var nav = document.createElement('div');
            nav.style.cssText = "position:fixed; bottom:0; width:100%; background:white; border-top:1px solid #eee; display:flex; justify-content:space-around; padding:10px 0; z-index:9999;";
            nav.innerHTML = `
                <div onclick="window.location='/'" style="text-align:center; color:{color}">
                    <div style="font-size:20px">🏠</div>
                    <span style="font-size:10px">Início</span>
                </div>
                <div onclick="window.location='/search'" style="text-align:center; color:#999">
                    <div style="font-size:20px">🔍</div>
                    <span style="font-size:10px">Buscar</span>
                </div>
                <div onclick="window.location='/checkout'" style="text-align:center; color:#999">
                    <div style="font-size:20px">🛒</div>
                    <span style="font-size:10px">Carrinho</span>
                </div>
            `;
            document.body.appendChild(nav);
            document.body.style.paddingBottom = "60px"; // Espaço para não cobrir o rodapé
        }}
    }})();
    """
    
    return Response(content=js_code, media_type="application/javascript")

# --- 4. INSTALAÇÃO ---
@app.get("/install")
def install():
    return RedirectResponse(f"https://www.tiendanube.com/apps/authorize/?client_id={CLIENT_ID}&response_type=code&scope=read_products")

@app.get("/callback")
def callback(code: str = Query(...), db: Session = Depends(get_db)):
    url = "https://www.tiendanube.com/apps/authorize/token"
    res = requests.post(url, json={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, 
        "grant_type": "authorization_code", "code": code
    })
    data = res.json()
    store_id = str(data["user_id"])
    
    # Salva Loja
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja: db.add(Loja(store_id=store_id, access_token=data["access_token"]))
    else: loja.access_token = data["access_token"]
    db.commit()
    
    return RedirectResponse(url=f"{FRONTEND_URL}/admin?store_id={store_id}")
