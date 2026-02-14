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

# --- INICIALIZAÇÃO DO BANCO ---
Base.metadata.create_all(bind=engine)
app = FastAPI()

# --- VARIÁVEIS DE AMBIENTE ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Configuração de URL do Backend (HTTPS Obrigatório)
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

# Configuração de URL do Frontend (HTTPS Obrigatório)
FRONTEND_URL = os.getenv("FRONTEND_URL")
if FRONTEND_URL and not FRONTEND_URL.startswith("http"):
    FRONTEND_URL = f"https://{FRONTEND_URL}"

# --- CORS (Permite conexão com qualquer lugar) ---
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

# --- FUNÇÕES AUXILIARES ---

def inject_script_tag(store_id: str, access_token: str):
    """Insere o script loader.js no rodapé da loja automaticamente."""
    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/scripts"
        headers = {
            "Authentication": f"bearer {access_token}",
            "User-Agent": "App PWA Builder" 
        }
        
        script_url = f"{BACKEND_URL}/loader.js?store_id={store_id}"
        
        payload = {
            "name": "PWA Loader",
            "description": "Transforma a loja em App",
            "html": f"<script src='{script_url}' async></script>",
            "event": "onload", # Tenta onload, se a loja bloquear, vai onfirstinteraction manual
            "where": "store"
        }

        # Verifica se já existe para não duplicar
        check = requests.get(url, headers=headers)
        if check.status_code == 200:
            scripts = check.json()
            if isinstance(scripts, list):
                for script in scripts:
                    if "PWA Loader" in script.get("name", ""):
                        print(f"✅ Script já existe na loja {store_id}")
                        return

        # Cria o script
        requests.post(url, json=payload, headers=headers)
        print(f"✅ Script injetado com sucesso na loja {store_id}")
    except Exception as e:
        print(f"⚠️ Aviso na injeção de script: {e}")

def create_landing_page_internal(store_id, access_token, color="#000000"):
    """Cria a página /pages/app dentro da loja do cliente."""
    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/pages"
        headers = { "Authentication": f"bearer {access_token}", "User-Agent": "App PWA Builder" }
        
        # HTML Bonito da Landing Page (Responsivo)
        html_body = f"""
        <div style="text-align: center; padding: 40px 20px; font-family: sans-serif;">
            <div style="background: #f9f9f9; padding: 30px; border-radius: 20px; display: inline-block; max-width: 400px; width: 100%; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                <h1 style="margin: 0 0 10px 0; color: #333;">Baixe Nosso App 📲</h1>
                <p style="color: #666; margin-bottom: 25px;">Navegue mais rápido e receba ofertas exclusivas.</p>
                
                <button onclick="if(window.installPWA) {{ window.installPWA() }} else {{ alert('Abra esta página no celular para instalar!') }}" style="
                    background-color: {color}; 
                    color: white; 
                    border: none; 
                    padding: 15px 30px; 
                    font-size: 18px; 
                    border-radius: 50px; 
                    cursor: pointer; 
                    width: 100%; 
                    font-weight: bold;
                    box-shadow: 0 4px 10px rgba(0,0,0,0.2);
                    transition: transform 0.2s;
                ">
                    Instalar Agora ⬇️
                </button>
                
                <p style="font-size: 12px; color: #999; margin-top: 15px;">
                    Disponível para Android e iOS
                </p>
            </div>
        </div>
        """
        
        data = { 
            "title": "Baixe nosso App", 
            "body": html_body, 
            "published": True, 
            "handle": "app" # Tenta criar link /pages/app
        }
        
        res = requests.post(url, json=data, headers=headers)
        if res.status_code == 201:
            print(f"✅ Página /pages/app criada para loja {store_id}")
        else:
             print(f"⚠️ Página não criada (pode já existir): {res.status_code}")
             
    except Exception as e:
        print(f"❌ Erro ao criar página interna: {e}")

# --- ROTAS PRINCIPAIS ---

@app.get("/")
def home():
    return {"status": "Backend Online", "frontend": FRONTEND_URL}

@app.get("/admin/config/{store_id}")
def get_config(store_id: str, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return {"app_name": "Minha Loja", "theme_color": "#000000", "logo_url": "", "whatsapp": ""}
    return config

@app.get("/admin/store-info/{store_id}")
def get_store_info(store_id: str, db: Session = Depends(get_db)):
    """Retorna a URL pública da loja para o Dashboard mostrar"""
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja: return {"url": ""}
    return {"url": loja.url}

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

@app.post("/admin/create-page")
def manual_create_page(payload: ConfigPayload, db: Session = Depends(get_db)):
    """Rota para criar a página manualmente pelo botão do Dashboard"""
    loja = db.query(Loja).filter(Loja.store_id == payload.store_id).first()
    if not loja: return JSONResponse(status_code=400, content={"error": "Loja não encontrada"})
    
    create_landing_page_internal(payload.store_id, loja.access_token, payload.theme_color)
    return {"status": "success", "url": f"{loja.url}/pages/app" if loja.url else "Verifique na loja"}

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
    # Recupera configuração ou usa padrão
    try:
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
        color = config.theme_color if config else "#000000"
    except:
        color = "#000000"
    
    # --- O SCRIPT MÁGICO (Javascript Gerado) ---
    js_code = f"""
    (function() {{
        console.log("🚀 App Builder: Iniciando...");

        // 1. Detecta se já é App
        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

        // 2. Injeta Meta Tags (Manifesto e Cor)
        var link = document.createElement('link');
        link.rel = 'manifest';
        link.href = '{BACKEND_URL}/manifest/{store_id}.json';
        document.head.appendChild(link);
        
        var meta = document.createElement('meta');
        meta.name = 'theme-color';
        meta.content = '{color}';
        document.head.appendChild(meta);

        // 3. Função Global de Instalação (Pode ser chamada por botões da loja)
        var deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {{
            e.preventDefault();
            deferredPrompt = e;
            console.log("📱 Android pronto para instalar");
        }});

        window.installPWA = function() {{
            if (deferredPrompt) {{
                // Android
                deferredPrompt.prompt();
                deferredPrompt.userChoice.then((choiceResult) => {{
                    deferredPrompt = null;
                }});
            }} else {{
                // iOS / Outros
                alert("Para instalar:\\n1. Toque no botão de Compartilhar (quadrado com seta)\\n2. Selecione 'Adicionar à Tela de Início' ➕");
            }}
        }};

        // 4. Lógica Visual (Só para celulares)
        if (window.innerWidth < 900) {{
            
            // A) Smart Banner no Topo (Se não for app e não tiver fechado antes)
            var hasClosedBanner = localStorage.getItem('pwa_banner_closed');
            if (!isApp && !hasClosedBanner) {{
                var banner = document.createElement('div');
                banner.style.cssText = "position: relative; width: 100%; background: #f0f0f0; padding: 10px; box-sizing: border-box; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #ccc; font-family: sans-serif; z-index: 99999;";
                banner.innerHTML = `
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="font-size:24px;">📲</span>
                        <div>
                            <div style="font-weight:bold; font-size:12px; color:#333;">Baixe nosso App Oficial</div>
                            <div style="font-size:10px; color:#666;">Mais rápido e seguro</div>
                        </div>
                    </div>
                    <div style="display:flex; align-items:center; gap:10px;">
                        <button onclick="window.installPWA()" style="background:{color}; color:white; border:none; padding:5px 12px; border-radius:20px; font-size:11px; font-weight:bold; cursor:pointer;">BAIXAR</button>
                        <div onclick="this.parentElement.parentElement.remove(); localStorage.setItem('pwa_banner_closed', 'true');" style="font-size:16px; color:#999; padding:5px; cursor:pointer;">✕</div>
                    </div>
                `;
                document.body.insertBefore(banner, document.body.firstChild);
            }}

            // B) Barra Inferior Fixa
            document.body.style.paddingBottom = "80px";
            var nav = document.createElement('div');
            nav.id = "app-pwa-bar";
            nav.style.cssText = "position:fixed; bottom:0; left:0; width:100%; height:65px; background:white; border-top:1px solid #eee; display:flex; justify-content:space-around; align-items:center; z-index:2147483647; box-shadow: 0 -2px 10px rgba(0,0,0,0.05);";
            
            // Botão de Instalar (Só aparece se NÃO for app)
            var installBtnHtml = '';
            if (!isApp) {{
                installBtnHtml = `
                <div onclick="window.installPWA()" style="flex:1;text-align:center;color:{color};cursor:pointer;background:#f5f5f5;border-radius:8px;margin:4px;padding:4px;">
                    <div style="font-size:20px;">⬇️</div>
                    <div style="font-size:9px;font-weight:bold;">Baixar</div>
                </div>`;
            }}

            nav.innerHTML = `
                <div onclick="window.location='/'" style="flex:1;text-align:center;color:{color};cursor:pointer;">
                   <div style="font-size:22px;">🏠</div>
                   <div style="font-size:10px;">Início</div>
                </div>
                <div onclick="window.location='/search'" style="flex:1;text-align:center;color:#666;cursor:pointer;">
                   <div style="font-size:22px;">🔍</div>
                   <div style="font-size:10px;">Buscar</div>
                </div>
                <div onclick="window.location='/checkout'" style="flex:1;text-align:center;color:#666;cursor:pointer;">
                    <div style="font-size:22px;">🛒</div>
                    <div style="font-size:10px;">Carrinho</div>
                </div>
                ${{installBtnHtml}}
            `;
            document.body.appendChild(nav);
        }}
    }})();
    """
    return Response(content=js_code, media_type="application/javascript")

# --- INSTALAÇÃO E AUTH ---

@app.get("/install")
def install():
    return RedirectResponse(
        f"https://www.tiendanube.com/apps/authorize/?client_id={CLIENT_ID}&response_type=code&scope=read_products,write_scripts,write_content"
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

    # 1. Pega URL da Loja para salvar
    try:
        headers = { "Authentication": f"bearer {access_token}", "User-Agent": "App PWA Builder" }
        store_info = requests.get(f"https://api.tiendanube.com/v1/{store_id}/store", headers=headers).json()
        store_url = store_info.get("url", {}).get("http", "")
    except:
        store_url = ""
    
    # 2. Salva no Banco (Com URL)
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja: 
        # Certifique-se que o models.py tem o campo 'url'
        loja = Loja(store_id=store_id, access_token=access_token, url=store_url)
        db.add(loja)
    else: 
        loja.access_token = access_token
        loja.url = store_url
    db.commit()

    # 3. Automação: Injeta Script e Cria Página
    inject_script_tag(store_id, access_token)
    create_landing_page_internal(store_id, access_token)
    
    # 4. Vai pro Painel
    return RedirectResponse(url=f"{FRONTEND_URL}/admin?store_id={store_id}")
