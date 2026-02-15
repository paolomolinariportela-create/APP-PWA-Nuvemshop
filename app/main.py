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
Base.metadata.drop_all(bind=engine)

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
    
    # Cores e Configurações Padrão
    color = config.theme_color if config else "#000000"
    fab_enabled = config.fab_enabled if config else False
    fab_text = config.fab_text if config else "Baixar App"

    # --- LÓGICA DO WIDGET BOTÃO FLUTUANTE (FAB) ---
    fab_script = ""
    if fab_enabled:
        fab_script = f"""
        // Criação do Botão Flutuante se for Mobile e Não for App
        if (window.innerWidth < 900 && !isApp) {{
            var fab = document.createElement('div');
            fab.id = 'pwa-fab-btn';
            // Estilo CSS Inline para garantir que nada da loja quebre o botão
            fab.style.cssText = "position:fixed; bottom:20px; right:20px; background:{color}; color:white; padding:12px 24px; border-radius:50px; box-shadow:0 4px 15px rgba(0,0,0,0.3); z-index:999999; font-family:sans-serif; font-weight:bold; font-size:14px; display:flex; align-items:center; gap:8px; cursor:pointer; transition: transform 0.2s;";
            
            // Ícone e Texto
            fab.innerHTML = "<span style='font-size:18px'>📲</span> <span>{fab_text}</span>";
            
            // Ação de Instalar
            fab.onclick = function() {{
                if(window.installPWA) window.installPWA();
            }};
            
            // Animação de Entrada
            fab.animate([
                {{ transform: 'translateY(100px)', opacity: 0 }},
                {{ transform: 'translateY(0)', opacity: 1 }}
            ], {{ duration: 500, easing: 'ease-out' }});

            document.body.appendChild(fab);
        }}
        """

    # --- O JAVASCRIPT ESPIÃO FINAL ---
    js = f"""
    (function() {{
        console.log("🚀 PWA Loader Pro v2");
        
        // 1. Identidade do Visitante
        var visitorId = localStorage.getItem('pwa_v_id');
        if(!visitorId) {{
            visitorId = 'v_' + Math.random().toString(36).substr(2, 9);
            localStorage.setItem('pwa_v_id', visitorId);
        }}

        // 2. Detecção de Ambiente
        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        
        // 3. Injeção de Meta Tags
        var link = document.createElement('link'); link.rel = 'manifest'; link.href = '{BACKEND_URL}/manifest/{store_id}.json'; document.head.appendChild(link);
        var meta = document.createElement('meta'); meta.name = 'theme-color'; meta.content = '{color}'; document.head.appendChild(meta);

        // 4. Analytics
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
        
        // Observer de URL (SPA)
        var oldHref = document.location.href;
        new MutationObserver(function() {{
            if (oldHref !== document.location.href) {{ oldHref = document.location.href; trackVisit(); }}
        }}).observe(document.querySelector("body"), {{ childList: true, subtree: true }});

        // 5. Instalação PWA
        var deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {{ e.preventDefault(); deferredPrompt = e; }});
        window.installPWA = function() {{
            if (deferredPrompt) {{ deferredPrompt.prompt(); }} 
            else {{ alert("Para instalar:\\\\nAndroid: Menu > Adicionar à Tela\\\\niOS: Compartilhar > Adicionar à Tela"); }}
        }};

        // --- WIDGETS ---
        {fab_script}

        // 6. Rastreamento de Vendas
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
