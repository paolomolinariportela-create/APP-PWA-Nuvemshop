import os
import requests
from datetime import datetime, timedelta
from fastapi import FastAPI, Depends, Response, Query, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from cryptography.fernet import Fernet
from jose import JWTError, jwt 

from .database import engine, Base, get_db
from .models import Loja, AppConfig, VendaApp

# --- INICIALIZAÇÃO DO BANCO ---
Base.metadata.create_all(bind=engine)
app = FastAPI()

# --- SEGURANÇA E AMBIENTE ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    print("⚠️ AVISO: Usando chave temporária (INSEGURO). Configure ENCRYPTION_KEY no Railway.")
    ENCRYPTION_KEY = Fernet.generate_key().decode()

cipher_suite = Fernet(ENCRYPTION_KEY)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# URLs
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"

FRONTEND_URL = os.getenv("FRONTEND_URL")
if FRONTEND_URL and not FRONTEND_URL.startswith("http"): FRONTEND_URL = f"https://{FRONTEND_URL}"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True, 
    allow_methods=["*"], 
    allow_headers=["*"],
)

# --- FUNÇÕES DE SEGURANÇA ---
def encrypt_token(token: str) -> str:
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> str:
    try: return cipher_suite.decrypt(encrypted_token.encode()).decode()
    except: return None

# --- JWT (O CRACHÁ) ---
def create_jwt_token(store_id: str):
    """Cria um crachá válido por 24 horas"""
    expiration = datetime.utcnow() + timedelta(hours=24)
    data = {"sub": store_id, "exp": expiration}
    return jwt.encode(data, CLIENT_SECRET, algorithm="HS256")

def get_current_store(token: str = Depends(oauth2_scheme)):
    """O Porteiro: Verifica se o crachá é válido"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, CLIENT_SECRET, algorithms=["HS256"])
        store_id: str = payload.get("sub")
        if store_id is None:
            raise credentials_exception
        return store_id
    except JWTError:
        raise credentials_exception

# --- MODELOS DE DADOS ---
class ConfigPayload(BaseModel):
    app_name: str
    theme_color: str
    logo_url: Optional[str] = None
    whatsapp: Optional[str] = None

class VendaPayload(BaseModel):
    store_id: str
    valor: str

# --- LÓGICA DO APP (INJEÇÃO E PÁGINA) ---

def inject_script_tag(store_id: str, encrypted_access_token: str):
    access_token = decrypt_token(encrypted_access_token)
    if not access_token: return

    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/scripts"
        headers = { "Authentication": f"bearer {access_token}", "User-Agent": "App PWA Builder" }
        script_url = f"{BACKEND_URL}/loader.js?store_id={store_id}"
        
        payload = { 
            "name": "PWA Loader Pro", 
            "description": "Transforma a loja em App (Seguro)",
            "html": f"<script src='{script_url}' async></script>", 
            "event": "onload", 
            "where": "store" 
        }

        check = requests.get(url, headers=headers)
        if check.status_code == 200:
            scripts = check.json()
            if isinstance(scripts, list):
                for script in scripts:
                    if "PWA Loader" in script.get("name", ""):
                        return

        requests.post(url, json=payload, headers=headers)
    except Exception as e:
        print(f"Erro Script: {e}")

def create_landing_page_internal(store_id, encrypted_access_token, color):
    access_token = decrypt_token(encrypted_access_token)
    if not access_token: return

    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/pages"
        headers = { "Authentication": f"bearer {access_token}", "User-Agent": "App PWA Builder" }
        
        html_body = f"""
        <div style="text-align: center; padding: 40px 20px; font-family: sans-serif;">
            <div style="background: #f9f9f9; padding: 30px; border-radius: 20px; display: inline-block; max-width: 400px; width: 100%; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                <h1 style="margin: 0 0 10px 0; color: #333;">Baixe Nosso App 📲</h1>
                <p style="color: #666; margin-bottom: 25px;">Navegue mais rápido e receba ofertas exclusivas.</p>
                <button onclick="if(window.installPWA) {{ window.installPWA() }} else {{ alert('Abra esta página no celular para instalar!') }}" style="background-color: {color}; color: white; border: none; padding: 15px 30px; font-size: 18px; border-radius: 50px; cursor: pointer; width: 100%; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">Instalar Agora ⬇️</button>
                <p style="font-size: 12px; color: #999; margin-top: 15px;">Disponível para Android e iOS</p>
            </div>
        </div>
        """
        
        requests.post(url, json={"title":"Baixe o App", "body":html_body, "published":True, "handle":"app"}, headers=headers)
    except Exception as e:
        print(f"Erro Page: {e}")

# --- ROTAS PRINCIPAIS ---

@app.get("/")
def home():
    return {"status": "Secure Backend Online 🔒", "frontend": FRONTEND_URL}

# --- ROTAS PROTEGIDAS (AREA VIP - Requer Token JWT) ---

@app.get("/admin/config")
def get_config(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return {"app_name": "Minha Loja", "theme_color": "#000000", "logo_url": "", "whatsapp": ""}
    return config

@app.get("/admin/store-info")
def get_store_info(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    return {"url": loja.url if loja else ""}

@app.post("/admin/config")
def save_config(payload: ConfigPayload, store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        config = AppConfig(store_id=store_id)
        db.add(config)
    config.app_name = payload.app_name
    config.theme_color = payload.theme_color
    config.logo_url = payload.logo_url
    config.whatsapp_number = payload.whatsapp
    db.commit()
    return {"status": "success"}

@app.post("/admin/create-page")
def manual_create_page(payload: ConfigPayload, store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja: return JSONResponse(status_code=400, content={"error": "Loja não encontrada"})
    create_landing_page_internal(store_id, loja.access_token, payload.theme_color)
    return {"status": "success"}

@app.get("/stats/total-vendas")
def get_total_vendas(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total = sum([float(v.valor) for v in vendas])
    return {"total": total, "quantidade": len(vendas)}

# --- ROTAS PÚBLICAS (Loader e Manifesto) ---

@app.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    name = config.app_name if config else "Minha Loja"
    color = config.theme_color if config else "#000000"
    icon = config.logo_url if config and config.logo_url else "https://via.placeholder.com/512"

    manifest = {
        "name": name, "short_name": name, "start_url": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": color, "orientation": "portrait",
        "icons": [{"src": icon, "sizes": "512x512", "type": "image/png"}]
    }
    return JSONResponse(content=manifest)

@app.post("/stats/venda")
def registrar_venda(payload: VendaPayload, db: Session = Depends(get_db)):
    db.add(VendaApp(store_id=payload.store_id, valor=payload.valor, data=datetime.now().isoformat()))
    db.commit()
    return {"status": "registrado"}

@app.get("/loader.js")
def get_loader_script(store_id: str, db: Session = Depends(get_db)):
    try:
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
        color = config.theme_color if config else "#000000"
    except:
        color = "#000000"
    
    js_code = f"""
    (function() {{
        console.log("🚀 App Builder: Iniciando...");
        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        var link = document.createElement('link'); link.rel = 'manifest'; link.href = '{BACKEND_URL}/manifest/{store_id}.json'; document.head.appendChild(link);
        var meta = document.createElement('meta'); meta.name = 'theme-color'; meta.content = '{color}'; document.head.appendChild(meta);

        var deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {{ e.preventDefault(); deferredPrompt = e; }});
        window.installPWA = function() {{
            if (deferredPrompt) {{ deferredPrompt.prompt(); deferredPrompt.userChoice.then((res) => {{ deferredPrompt = null; }}); }} 
            else {{ alert("Para instalar:\\n1. Toque em Compartilhar/Menu\\n2. Adicionar à Tela de Início ➕"); }}
        }};

        if (window.innerWidth < 900) {{
            var hasClosed = localStorage.getItem('pwa_banner_closed');
            if (!isApp && !hasClosed) {{
                var b = document.createElement('div');
                b.style.cssText = "position:relative;width:100%;background:#f0f0f0;padding:10px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ccc;z-index:99999;";
                b.innerHTML = `<div style='display:flex;align-items:center;gap:10px;'><span style='font-size:24px'>📲</span><div><div style='font-weight:bold;font-size:12px;color:#333'>Baixe o App</div><div style='font-size:10px;color:#666'>Mais rápido</div></div></div><div style='display:flex;gap:10px'><button onclick='window.installPWA()' style='background:{color};color:white;border:none;padding:5px 12px;border-radius:20px;font-size:11px;font-weight:bold'>BAIXAR</button><div onclick='this.parentElement.parentElement.remove();localStorage.setItem("pwa_banner_closed","true")' style='padding:5px;color:#999'>✕</div></div>`;
                document.body.insertBefore(b, document.body.firstChild);
            }}

            document.body.style.paddingBottom = "80px";
            var nav = document.createElement('div');
            nav.style.cssText = "position:fixed;bottom:0;left:0;width:100%;height:65px;background:white;border-top:1px solid #eee;display:flex;justify-content:space-around;align-items:center;z-index:999999;box-shadow:0 -2px 10px rgba(0,0,0,0.05);";
            var installBtn = !isApp ? `<div onclick="window.installPWA()" style="flex:1;text-align:center;color:{color};background:#f5f5f5;border-radius:8px;margin:4px;padding:4px"><div style="font-size:20px">⬇️</div><div style="font-size:9px;font-weight:bold">Baixar</div></div>` : '';
            nav.innerHTML = `<div onclick="window.location='/'" style="flex:1;text-align:center;color:{color}"><div style="font-size:22px">🏠</div><div style="font-size:10px">Início</div></div><div onclick="window.location='/search'" style="flex:1;text-align:center;color:#666"><div style="font-size:22px">🔍</div><div style="font-size:10px">Buscar</div></div><div onclick="window.location='/checkout'" style="flex:1;text-align:center;color:#666"><div style="font-size:22px">🛒</div><div style="font-size:10px">Carrinho</div></div>${{installBtn}}`;
            document.body.appendChild(nav);
        }}

        if (window.location.href.includes('/checkout/success') && isApp) {{
            var val = "0.00";
            if (window.dataLayer) {{ for(var i=0;i<window.dataLayer.length;i++){{ if(window.dataLayer[i].transactionTotal){{ val=window.dataLayer[i].transactionTotal; break; }} }} }}
            var oid = window.location.href.split('/').pop();
            if (!localStorage.getItem('venda_'+oid) && parseFloat(val)>0) {{
                fetch('{BACKEND_URL}/stats/venda', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{store_id:'{store_id}', valor:val.toString()}}) }});
                localStorage.setItem('venda_'+oid, 'true');
            }}
        }}
    }})();
    """
    return Response(content=js_code, media_type="application/javascript")

# --- AUTH & CALLBACK (CORRIGIDO 303) ---

@app.get("/install")
def install():
    # 303 força o navegador a ir para a próxima página limpo
    return RedirectResponse(
        f"https://www.nuvemshop.com.br/apps/authorize/?client_id={CLIENT_ID}&response_type=code&scope=read_products,write_scripts,write_content",
        status_code=303
    )

@app.get("/callback")
def callback(code: str = Query(...), db: Session = Depends(get_db)):
    try:
        # 1. Troca code por Token
        res = requests.post("https://www.tiendanube.com/apps/authorize/token", json={
            "client_id": CLIENT_ID, 
            "client_secret": CLIENT_SECRET, 
            "grant_type": "authorization_code", 
            "code": code
        })
        
        if res.status_code != 200:
            return JSONResponse(status_code=400, content={"error": "Falha Login", "details": res.json()})

        data = res.json()
        store_id = str(data["user_id"])
        access_token = data["access_token"]
        
        # 2. Salva Encriptado
        encrypted_token = encrypt_token(access_token)
        loja = db.query(Loja).filter(Loja.store_id == store_id).first()
        
        # Tenta pegar URL
        try: store_url = requests.get(f"https://api.tiendanube.com/v1/{store_id}/store", headers={"Authentication":f"bearer {access_token}"}).json().get("url",{}).get("http","")
        except: store_url = ""

        if not loja: db.add(Loja(store_id=store_id, access_token=encrypted_token, url=store_url))
        else: loja.access_token = encrypted_token; loja.url = store_url
        db.commit()

        # 3. Executa Automações
        inject_script_tag(store_id, encrypted_token)
        create_landing_page_internal(store_id, encrypted_token, "#000000")

        # 4. GERA O TOKEN JWT (O CRACHÁ)
        jwt_token = create_jwt_token(store_id)

        # 5. MANDA O TOKEN PARA O FRONTEND
        # status_code=303 é OBRIGATÓRIO aqui para evitar o erro 405 Method Not Allowed
        return RedirectResponse(url=f"{FRONTEND_URL}/admin?token={jwt_token}", status_code=303)
        
    except Exception as e:
        print(f"Erro Callback: {e}")
        return JSONResponse(status_code=500, content={"error": "Erro interno"})
