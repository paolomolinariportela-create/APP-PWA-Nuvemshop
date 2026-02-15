import os
from fastapi import FastAPI, Depends, Response
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

# Imports Internos
from .database import engine, Base, get_db
from .models import AppConfig

# Importando as Rotas Novas
from .routes import auth_routes, config_routes, stats_routes

# Inicializa Banco
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Variáveis Globais
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)

# --- INCLUINDO AS ROTAS ---
app.include_router(auth_routes.router)
app.include_router(config_routes.router)
app.include_router(stats_routes.router)

# --- ROTAS PÚBLICAS GLOBAIS (Manifest e Loader ficam aqui ou num router separado) ---

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

@app.get("/loader.js")
def get_loader(store_id: str, db: Session = Depends(get_db)):
    try: config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except: config = None
    color = config.theme_color if config else "#000000"

    # --- O JAVASCRIPT ESPIÃO (Mantido aqui para facilitar acesso a var globais) ---
    js = f"""
    (function() {{
        console.log("🚀 PWA Loader Ativo");
        var visitorId = localStorage.getItem('pwa_v_id');
        if(!visitorId) {{
            visitorId = 'v_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('pwa_v_id', visitorId);
        }}

        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        
        var link = document.createElement('link'); link.rel = 'manifest'; link.href = '{BACKEND_URL}/manifest/{store_id}.json'; document.head.appendChild(link);
        var meta = document.createElement('meta'); meta.name = 'theme-color'; meta.content = '{color}'; document.head.appendChild(meta);

        function trackVisit() {{
            try {{
                fetch('{BACKEND_URL}/stats/visita', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{ store_id: '{store_id}', pagina: window.location.pathname, is_pwa: isApp, visitor_id: visitorId }})
                }});
            }} catch(e) {{}}
        }}
        trackVisit();
        
        var oldHref = document.location.href;
        new MutationObserver(function() {{
            if (oldHref !== document.location.href) {{ oldHref = document.location.href; trackVisit(); }}
        }}).observe(document.querySelector("body"), {{ childList: true, subtree: true }});

        var deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {{ e.preventDefault(); deferredPrompt = e; }});
        window.installPWA = function() {{
            if (deferredPrompt) {{ deferredPrompt.prompt(); }} 
            else {{ alert("Para instalar:\\\\nAndroid: Menu > Adicionar à Tela\\\\niOS: Compartilhar > Adicionar à Tela"); }}
        }};

        if (window.innerWidth < 900 && !isApp) {{
            if (!localStorage.getItem('pwa_banner_closed')) {{
                var b = document.createElement('div');
                b.style.cssText = "position:relative;width:100%;background:#f8f9fa;padding:12px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ddd;z-index:999999;";
                b.innerHTML = `<div style='display:flex;gap:10px;'><span>📲</span><div><b>Baixe o App</b></div></div><button onclick='window.installPWA()' style='background:{color};color:white;border:none;padding:5px 15px;border-radius:20px;'>BAIXAR</button>`;
                document.body.insertBefore(b, document.body.firstChild);
            }}
        }}

        if (window.location.href.includes('/checkout/success') && isApp) {{
            var val = "0.00";
            if (window.dataLayer) {{ for(var i=0; i<window.dataLayer.length; i++) {{ if(window.dataLayer[i].transactionTotal) {{ val = window.dataLayer[i].transactionTotal; break; }} }} }}
            var oid = window.location.href.split('/').pop();
            if (!localStorage.getItem('venda_'+oid) && parseFloat(val) > 0) {{
                fetch('{BACKEND_URL}/stats/venda', {{ 
                    method:'POST', headers:{{'Content-Type':'application/json'}}, 
                    body:JSON.stringify({{ store_id:'{store_id}', valor:val.toString(), visitor_id: visitorId }}) 
                }});
                localStorage.setItem('venda_'+oid, 'true');
            }}
        }}
    }})();
    """
    return Response(content=js, media_type="application/javascript")
