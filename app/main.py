# main.py
import os
import requests
from datetime import datetime
from fastapi import FastAPI, Depends, Response, Query
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

# Importando nossos novos módulos organizados
from .database import engine, Base, get_db
from .models import Loja, AppConfig, VendaApp
from .auth import CLIENT_ID, CLIENT_SECRET, encrypt_token, create_jwt_token, get_current_store
from .services import inject_script_tag, create_landing_page_internal

# INICIALIZAÇÃO
Base.metadata.create_all(bind=engine)
app = FastAPI()

# URLs GLOBAIS
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"

FRONTEND_URL = os.getenv("FRONTEND_URL")
if FRONTEND_URL and not FRONTEND_URL.startswith("http"): FRONTEND_URL = f"https://{FRONTEND_URL}"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- MODELOS DE ENTRADA ---
class ConfigPayload(BaseModel):
    app_name: str
    theme_color: str
    logo_url: Optional[str] = None
    whatsapp: Optional[str] = None

class VendaPayload(BaseModel):
    store_id: str
    valor: str

# --- ROTAS DE AUTENTICAÇÃO (LOGIN) ---

@app.get("/install")
def install():
    # URL BRASIL para garantir cookie correto
    auth_url = f"https://www.nuvemshop.com.br/apps/authorize/?client_id={CLIENT_ID}&response_type=code&scope=read_products,write_scripts,write_content"
    return RedirectResponse(auth_url, status_code=303)

# Callback aceita POST e GET para evitar erro 405
@app.api_route("/callback", methods=["GET", "POST"])
def callback(code: str = Query(None), db: Session = Depends(get_db)):
    if not code: return RedirectResponse(FRONTEND_URL)
    
    try:
        # 1. Troca CODE por TOKEN
        res = requests.post("https://www.tiendanube.com/apps/authorize/token", json={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, 
            "grant_type": "authorization_code", "code": code
        })
        if res.status_code != 200:
            return JSONResponse(status_code=400, content={"error": "Falha Login Nuvemshop", "debug": res.text})

        data = res.json()
        store_id = str(data["user_id"])
        raw_token = data["access_token"]
        
        # 2. Salva no Banco (Encriptado)
        encrypted = encrypt_token(raw_token)
        loja = db.query(Loja).filter(Loja.store_id == store_id).first()
        
        # Tenta pegar a URL da loja pra salvar
        store_url = ""
        try:
            r = requests.get(f"https://api.tiendanube.com/v1/{store_id}/store", headers={"Authentication": f"bearer {raw_token}"})
            if r.status_code == 200: store_url = r.json().get("url", {}).get("http", "")
        except: pass

        if not loja: db.add(Loja(store_id=store_id, access_token=encrypted, url=store_url))
        else: loja.access_token = encrypted; loja.url = store_url
        db.commit()

        # 3. Executa Serviços (Injeção e Página)
        inject_script_tag(store_id, encrypted)
        create_landing_page_internal(store_id, encrypted, "#000000")

        # 4. Gera Token JWT e Redireciona
        jwt = create_jwt_token(store_id)
        return RedirectResponse(f"{FRONTEND_URL}/admin?token={jwt}", status_code=303)

    except Exception as e:
        print(f"Erro Crítico Callback: {e}")
        return JSONResponse(status_code=500, content={"error": "Erro Interno"})

# --- ROTAS DO PAINEL (PROTEGIDAS PELO JWT) ---

@app.get("/admin/config")
def get_config(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config: return {"app_name": "Minha Loja", "theme_color": "#000000", "logo_url": "", "whatsapp": ""}
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
    if not loja: return {"error": "Loja não encontrada"}
    create_landing_page_internal(store_id, loja.access_token, payload.theme_color)
    return {"status": "success"}

@app.get("/stats/total-vendas")
def get_stats(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total = sum([float(v.valor) for v in vendas])
    return {"total": total, "quantidade": len(vendas)}

# --- NOVO ENDPOINT DO DASHBOARD COMPLETO ---
@app.get("/stats/dashboard")
def get_dashboard_stats(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    # 1. Dados Reais de Venda
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum([float(v.valor) for v in vendas])
    qtd_vendas = len(vendas)

    # 2. Dados Completos (Simulados para Visualização)
    stats = {
        # KPI Principais
        "receita": total_receita,
        "vendas": qtd_vendas,
        "instalacoes": 124, 
        "carrinhos_abandonados": { "valor": 4250.00, "qtd": 15 },
        "economia_ads": 200.00,
        
        # Card 1: Visualizações
        "visualizacoes": {
            "pageviews": 15430,
            "tempo_medio": "4m 12s",
            "top_paginas": ["Home", "Promoções", "Tênis Runner"]
        },

        # Card 2: Funil de Vendas
        "funil": {
            "visitas": 1000,
            "carrinho": 320,  # 32%
            "checkout": 110   # 11%
        },

        # Card 3: Recorrência
        "recorrencia": {
            "clientes_2x": 45,
            "taxa_recompra": 18.5
        },

        # Card 4: Ticket Médio (Comparativo)
        "ticket_medio": {
            "app": 189.90,
            "site": 142.50
        },

        # Card Antigo: Taxa de Conversão
        "taxa_conversao": { "app": 2.5, "site": 0.8 },
        "top_produtos": []
    }
    return stats

# --- ROTAS PÚBLICAS (SCRIPT E MANIFESTO) ---

@app.get("/")
def home(): return {"status": "Online 🚀"}

@app.get("/manifest/{store_id}.json")
def get_manifest(store_id: str, db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    name = config.app_name if config else "Loja"
    color = config.theme_color if config else "#000"
    icon = config.logo_url if config and config.logo_url else "https://via.placeholder.com/512"
    
    return JSONResponse({
        "name": name, "short_name": name, "start_url": "/", "display": "standalone",
        "background_color": "#ffffff", "theme_color": color, "orientation": "portrait",
        "icons": [{"src": icon, "sizes": "512x512", "type": "image/png"}]
    })

@app.post("/stats/venda")
def registrar_venda(payload: VendaPayload, db: Session = Depends(get_db)):
    db.add(VendaApp(store_id=payload.store_id, valor=payload.valor, data=datetime.now().isoformat()))
    db.commit()
    return {"status": "ok"}

@app.get("/loader.js")
def get_loader(store_id: str, db: Session = Depends(get_db)):
    try: config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except: config = None
    color = config.theme_color if config else "#000000"

    js = f"""
    (function() {{
        console.log("🚀 PWA Loader Ativo");
        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        
        // 1. Manifesto e Meta Tags
        var link = document.createElement('link'); link.rel = 'manifest'; link.href = '{BACKEND_URL}/manifest/{store_id}.json'; document.head.appendChild(link);
        var meta = document.createElement('meta'); meta.name = 'theme-color'; meta.content = '{color}'; document.head.appendChild(meta);

        // 2. Lógica de Instalação
        var deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {{ e.preventDefault(); deferredPrompt = e; }});
        window.installPWA = function() {{
            if (deferredPrompt) {{ deferredPrompt.prompt(); deferredPrompt.userChoice.then((res) => {{ deferredPrompt = null; }}); }} 
            else {{ alert("Para instalar:\\nAndroid: Toque em menu > Adicionar à Tela de Início\\niOS: Toque em Compartilhar > Adicionar à Tela de Início"); }}
        }};

        // 3. Banner Mobile (Só aparece se não for App)
        if (window.innerWidth < 900 && !isApp) {{
            if (!localStorage.getItem('pwa_banner_closed')) {{
                var b = document.createElement('div');
                b.style.cssText = "position:relative;width:100%;background:#f8f9fa;padding:12px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ddd;z-index:999999;box-shadow:0 2px 5px rgba(0,0,0,0.1);font-family:sans-serif;";
                b.innerHTML = `<div style='display:flex;align-items:center;gap:10px;'><span style='font-size:20px'>📲</span><div><div style='font-weight:bold;font-size:13px;color:#333'>Baixe nosso App Oficial</div><div style='font-size:11px;color:#666'>Promoções exclusivas</div></div></div><div style='display:flex;gap:10px;align-items:center'><button onclick='window.installPWA()' style='background:{color};color:white;border:none;padding:6px 14px;border-radius:20px;font-size:11px;font-weight:bold;cursor:pointer'>BAIXAR</button><div onclick='this.parentElement.parentElement.remove();localStorage.setItem("pwa_banner_closed","true")' style='font-size:18px;color:#999;padding:5px;cursor:pointer'>×</div></div>`;
                document.body.insertBefore(b, document.body.firstChild);
            }}
        }}

        // 4. Barra de Navegação Inferior (Só no Mobile)
        if (window.innerWidth < 900) {{
            document.body.style.paddingBottom = "70px";
            var nav = document.createElement('div');
            nav.style.cssText = "position:fixed;bottom:0;left:0;width:100%;height:60px;background:white;border-top:1px solid #eee;display:flex;justify-content:space-around;align-items:center;z-index:999999;box-shadow:0 -2px 10px rgba(0,0,0,0.05);font-family:sans-serif;";
            
            var btnInstall = !isApp ? `<div onclick="window.installPWA()" style="flex:1;text-align:center;cursor:pointer"><div style="font-size:20px;margin-bottom:2px">⬇️</div><div style="font-size:10px;color:#333">Baixar</div></div>` : '';
            
            nav.innerHTML = `
                <div onclick="window.location='/'" style="flex:1;text-align:center;cursor:pointer;color:{color}"><div style="font-size:22px;margin-bottom:2px">🏠</div><div style="font-size:10px;font-weight:bold">Início</div></div>
                <div onclick="window.location='/search'" style="flex:1;text-align:center;cursor:pointer;color:#666"><div style="font-size:22px;margin-bottom:2px">🔍</div><div style="font-size:10px">Buscar</div></div>
                <div onclick="window.location='/checkout'" style="flex:1;text-align:center;cursor:pointer;color:#666"><div style="font-size:22px;margin-bottom:2px">🛒</div><div style="font-size:10px">Carrinho</div></div>
                ${{btnInstall}}
            `;
            document.body.appendChild(nav);
        }}

        // 5. Rastreamento de Vendas
        if (window.location.href.includes('/checkout/success') && isApp) {{
            var val = "0.00";
            if (window.dataLayer) {{ 
                for(var i=0; i<window.dataLayer.length; i++) {{ 
                    if(window.dataLayer[i].transactionTotal) {{ val = window.dataLayer[i].transactionTotal; break; }} 
                }} 
            }}
            var oid = window.location.href.split('/').pop();
            if (!localStorage.getItem('venda_'+oid) && parseFloat(val) > 0) {{
                fetch('{BACKEND_URL}/stats/venda', {{ 
                    method:'POST', 
                    headers:{{'Content-Type':'application/json'}}, 
                    body:JSON.stringify({{store_id:'{store_id}', valor:val.toString()}}) 
                }});
                localStorage.setItem('venda_'+oid, 'true');
            }}
        }}

    }})();
    """
    return Response(content=js, media_type="application/javascript")
