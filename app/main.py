import os
import requests
from fastapi import FastAPI, Depends, Response, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from .database import engine, Base, get_db
from .models import Loja, AppConfig

# --- INICIALIZAÇÃO ---
Base.metadata.create_all(bind=engine)
app = FastAPI()

# --- VARIÁVEIS DE AMBIENTE ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
BACKEND_URL = os.getenv("PUBLIC_URL") 
FRONTEND_URL = os.getenv("FRONTEND_URL") 

# --- CORS ---
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

# --- FUNÇÃO MÁGICA: INJEÇÃO AUTOMÁTICA ---
def inject_script_tag(store_id: str, access_token: str):
    """
    Fala com a API da Nuvemshop e insere o script do PWA automaticamente.
    """
    url = f"https://api.tiendanube.com/v1/{store_id}/scripts"
    headers = {
        "Authentication": f"bearer {access_token}",
        "User-Agent": "App PWA Builder (suporte@seumail.com)" 
    }
    
    # O Script que vamos injetar
    script_url = f"{BACKEND_URL}/loader.js?store_id={store_id}"
    
    payload = {
        "name": "PWA Loader",
        "description": "Transforma a loja em App",
        "html": f"<script src='{script_url}' async></script>",
        "event": "onload",
        "where": "store"
    }

    # Verifica se já existe para não duplicar
    check = requests.get(url, headers=headers)
    if check.status_code == 200:
        scripts = check.json()
        for script in scripts:
            if "PWA Loader" in script.get("name", ""):
                # Já existe, então vamos atualizar (PUT) ou ignorar
                print(f"Script já existe na loja {store_id}")
                return

    # Se não existe, cria (POST)
    response = requests.post(url, json=payload, headers=headers)
    if response.status_code == 201:
        print(f"✅ Script injetado com sucesso na loja {store_id}")
    else:
        print(f"❌ Erro ao injetar script: {response.text}")

# --- ROTAS ---

@app.get("/admin/config/{store_id}")
def get_config(store_id: str, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return {"app_name": "Minha Loja", "theme_color": "#000000", "logo_url": "", "whatsapp": ""}
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

@app.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    name = config.app_name if config else "Minha Loja"
    color = config.theme_color if config else "#000000"
    icon = config.logo_url if config and config.logo_url else "https://via.placeholder.com/512"

    manifest = {
        "name": name,
        "short_name": name,
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": color,
        "orientation": "portrait",
        "icons": [{"src": icon, "sizes": "512x512", "type": "image/png"}]
    }
    return JSONResponse(content=manifest)

@app.get("/loader.js")
def get_loader_script(store_id: str, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    color = config.theme_color if config else "#000000"
    
    js_code = f"""
    (function() {{
        // Evita rodar dentro de iFrames (como o editor da Nuvemshop)
        if (window.self !== window.top) return;

        var link = document.createElement('link');
        link.rel = 'manifest';
        link.href = '{BACKEND_URL}/manifest/{store_id}.json';
        document.head.appendChild(link);
        
        var meta = document.createElement('meta');
        meta.name = 'theme-color';
        meta.content = '{color}';
        document.head.appendChild(meta);

        if (window.innerWidth < 768) {{
            document.body.style.paddingBottom = "70px";
            var nav = document.createElement('div');
            nav.style.cssText = "position:fixed; bottom:0; left:0; width:100%; height:60px; background:white; border-top:1px solid #eee; display:flex; justify-content:space-around; align-items:center; z-index:999999;";
            nav.innerHTML = `
                <div onclick="window.location='/'" style="flex:1;text-align:center;color:{color}">
                   <div style="font-size:20px;">🏠</div><span style="font-size:10px">Início</span>
                </div>
                <div onclick="window.location='/search'" style="flex:1;text-align:center;color:#999">
                   <div style="font-size:20px;">🔍</div><span style="font-size:10px">Buscar</span>
                </div>
                <div onclick="window.location='/checkout'" style="flex:1;text-align:center;color:#999">
                    <div style="font-size:20px;">🛒</div><span style="font-size:10px">Carrinho</span>
                </div>
            `;
            document.body.appendChild(nav);
        }}
    }})();
    """
    return Response(content=js_code, media_type="application/javascript")

# --- INSTALAÇÃO E OAUTH ---

@app.get("/install")
def install():
    # Adicionei o escopo 'write_scripts' que é OBRIGATÓRIO para injetar código
    return RedirectResponse(
        f"https://www.tiendanube.com/apps/authorize/?client_id={CLIENT_ID}&response_type=code&scope=read_products,write_scripts"
    )

@app.get("/callback")
def callback(code: str = Query(...), db: Session = Depends(get_db)):
    url = "https://www.tiendanube.com/apps/authorize/token"
    res = requests.post(url, json={
        "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, 
        "grant_type": "authorization_code", "code": code
    })
    
    if res.status_code != 200:
        return JSONResponse(status_code=400, content={"error": "Falha Login", "details": res.json()})

    data = res.json()
    store_id = str(data["user_id"])
    access_token = data["access_token"]
    
    # 1. Salva no Banco
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja: db.add(Loja(store_id=store_id, access_token=access_token))
    else: loja.access_token = access_token
    db.commit()

    # 2. INJEÇÃO AUTOMÁTICA (A Mágica acontece aqui)
    try:
        inject_script_tag(store_id, access_token)
    except Exception as e:
        print(f"Erro na injeção automática: {e}")
    
    # 3. Manda pro Painel
    return RedirectResponse(url=f"{FRONTEND_URL}/admin?store_id={store_id}")
