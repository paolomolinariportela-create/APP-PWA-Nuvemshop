import os
import requests
from fastapi import FastAPI, Depends, HTTPException, Request, Query, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from .database import engine, Base, get_db
from .models import Loja, Produto, AppConfig
from .services import sync_full_store_data

# Inicializa Banco
Base.metadata.create_all(bind=engine)
app = FastAPI(title="Gerador de App PWA - Nuvemshop")

# Configurações
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL") # URL do seu novo projeto no Vercel/Railway

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DADOS (Pydantic) ---
class ConfigPayload(BaseModel):
    store_id: str
    app_name: str
    theme_color: str
    logo_url: Optional[str] = None
    whatsapp: Optional[str] = None

# --- ROTAS DE CONFIGURAÇÃO (O PAINEL DO CLIENTE) ---

@app.get("/admin/config/{store_id}")
def get_config(store_id: str, db: Session = Depends(get_db)):
    """Busca as cores e logo salvas para mostrar no painel"""
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        # Se não tiver, retorna padrão
        return {"app_name": "Minha Loja", "theme_color": "#000000", "logo_url": ""}
    return config

@app.post("/admin/config")
def save_config(payload: ConfigPayload, db: Session = Depends(get_db)):
    """Salva a personalização do App"""
    config = db.query(AppConfig).filter(AppConfig.store_id == payload.store_id).first()
    
    if not config:
        config = AppConfig(store_id=payload.store_id)
        db.add(config)
    
    config.app_name = payload.app_name
    config.theme_color = payload.theme_color
    config.logo_url = payload.logo_url
    config.whatsapp_number = payload.whatsapp
    
    db.commit()
    return {"status": "success", "message": "App personalizado com sucesso!"}

# --- A MÁGICA DO PWA (MANIFEST DINÂMICO) ---

@app.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    """Gera o arquivo de instalação para o celular do cliente"""
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    
    # Valores padrão se não tiver config
    name = config.app_name if config else "Minha Loja"
    color = config.theme_color if config else "#000000"
    # Ícone padrão transparente se não tiver logo
    icon = config.logo_url if config and config.logo_url else "https://via.placeholder.com/512"

    manifest = {
        "name": name,
        "short_name": name,
        "start_url": f"/?store_id={store_id}&mode=app",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": color,
        "icons": [
            {
                "src": icon,
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return JSONResponse(content=manifest)

# --- ROTAS DE PRODUTOS (PARA O APP LER) ---

@app.get("/products/{store_id}")
def list_products_app(store_id: str, page: int = 1, limit: int = 20, search: Optional[str] = None, db: Session = Depends(get_db)):
    query = db.query(Produto).filter(Produto.store_id == store_id)
    if search:
        query = query.filter(Produto.name.ilike(f"%{search}%"))
    return query.offset((page - 1) * limit).limit(limit).all()

# --- ROTAS DE INSTALAÇÃO (NUVEMSHOP) ---

@app.get("/install")
def install():
    return RedirectResponse(f"https://www.tiendanube.com/apps/authorize/?client_id={CLIENT_ID}&response_type=code&scope=read_products")

@app.get("/callback")
def callback(code: str = Query(...), db: Session = Depends(get_db)):
    # Troca o código pelo token (igual ao projeto anterior)
    url = "https://www.tiendanube.com/apps/authorize/token"
    res = requests.post(url, json={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, 
        "grant_type": "authorization_code", "code": code
    })
    data = res.json()
    store_id = str(data["user_id"])
    token = data["access_token"]
    
    # Salva/Atualiza Loja
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja: db.add(Loja(store_id=store_id, access_token=token))
    else: loja.access_token = token
    db.commit()
    
    return RedirectResponse(url=f"{FRONTEND_URL}/admin?store_id={store_id}")

@app.post("/sync")
async def sync_products(store_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    background_tasks.add_task(sync_full_store_data, store_id, db)
    return {"status": "processing"}

@app.get("/")
def home(): return {"msg": "Fábrica de PWA Online 🚀"}
