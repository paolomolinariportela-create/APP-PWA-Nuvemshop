import os
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppConfig

router = APIRouter()

# --- CONFIGURAÇÕES ---
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")

@router.get("/loader.js", include_in_schema=False)
def get_loader(store_id: str, request: Request, db: Session = Depends(get_db)):
    final_backend_url = BACKEND_URL or str(request.base_url).rstrip("/")

    try: config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except: config = None
    color = config.theme_color if config else "#000000"

    # Configs Visuais
    fab_enabled = getattr(config, "fab_enabled", False)
    fab_text = getattr(config, "fab_text", "Baixar App")
    fab_position = getattr(config, "fab_position", "right")
    fab_icon = getattr(config, "fab_icon", "📲") or "📲"
    fab_delay = getattr(config, "fab_delay", 0)
    position_css = "right:20px;" if fab_position == "right" else "left:20px;"
    
    bottom_bar_bg = getattr(config, "bottom_bar_bg", "#FFFFFF") if config else "#FFFFFF"
    bottom_bar_icon_color = getattr(config, "bottom_bar_icon_color", "#6B7280") if config else "#6B7280"

    # Script FAB (Note as chaves duplas {{ }})
    fab_script = ""
    if fab_enabled:
        fab_script = f"""
            if (window.innerWidth < 900 && !isApp) {{
                setTimeout(function() {{
                    var fab = document.createElement('div');
                    fab.id = 'pwa-fab-btn';
                    fab.style.cssText = "position:fixed; bottom:20px; {position_css} background:{color}; color:white; padding:12px 24px; border-radius:50px; box-shadow:0 4px 15px rgba(0,0,0,0.3); z-index:999999; font-family:sans-serif; font-weight:bold; font-size:14px; display:flex; align-items:center; gap:8px; cursor:pointer;";
                    fab.innerHTML = "<span>{fab_icon}</span> <span>{fab_text}</span>";
                    fab.onclick = function() {{ window.deferredPrompt ? window.deferredPrompt.prompt() : alert('Instale pelo menu do navegador'); }};
                    document.body.appendChild(fab);
                }}, {fab_delay * 1000});
            }}
        """

    # Script Bottom Bar
    bottom_bar_script = f"""
        if (isApp) {{
            var bar = document.createElement('nav');
            bar.style.cssText = "position:fixed; bottom:0; left:0; right:0; height:70px; background:{bottom_bar_bg}; border-top:1px solid #e5e7eb; display:flex; justify-content:space-around; align-items:center; z-index:999999; padding-bottom:env(safe-area-inset-bottom,0);";
            bar.innerHTML = '<a href="/" style="text-decoration:none;color:{bottom_bar_icon_color};display:flex;flex-direction:column;align-items:center;font-size:10px;"> <span style="font-size:24px">🏠</span> Início</a>' +
                            '<a href="/search" style="text-decoration:none;color:{bottom_bar_icon_color};display:flex;flex-direction:column;align-items:center;font-size:10px;"> <span style="font-size:24px">🔍</span> Busca</a>' +
                            '<a href="/carrinho" style="text-decoration:none;color:{bottom_bar_icon_color};display:flex;flex-direction:column;align-items:center;font-size:10px;"> <span style="font-size:24px">🛍️</span> Sacola</a>';
            document.body.appendChild(bar);
            document.body.style.paddingBottom = "80px";
        }}
    """

    js = f"""
    (function() {{
        console.log("🚀 PWA Loader V10 - Final");
        var visitorId = localStorage.getItem('pwa_v_id') || 'v_'+Math.random().toString(36).substr(2,9);
        localStorage.setItem('pwa_v_id', visitorId);
        
        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

        // 1. Manifest
        var link = document.createElement('link'); link.rel = 'manifest'; link.href = '{final_backend_url}/manifest/{store_id}.json'; document.head.appendChild(link);
        var meta = document.createElement('meta'); meta.name = 'theme-color'; meta.content = '{color}'; document.head.appendChild(meta);

        // 2. Analytics
        fetch('{final_backend_url}/analytics/visita', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{store_id:'{store_id}', pagina:window.location.pathname, is_pwa:isApp, visitor_id:visitorId}}) }}).catch(e=>{{}});

        // 3. PUSH
        const publicVapidKey = "{VAPID_PUBLIC_KEY}";

        function urlBase64ToUint8Array(base64String) {{
            const padding = '='.repeat((4 - base64String.length % 4) % 4);
            const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            for (let i = 0; i < rawData.length; ++i) outputArray[i] = rawData.charCodeAt(i);
            return outputArray;
        }}

        async function initPush() {{
            if (!('serviceWorker' in navigator) || !publicVapidKey) return;
            try {{
                const reg = await navigator.serviceWorker.register('{final_backend_url}/service-worker.js', {{scope: '/'}});
                await navigator.serviceWorker.ready;
                
                const sub = await reg.pushManager.subscribe({{
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
                }});

                console.log("📡 Inscrevendo no Servidor...");
                await fetch('{final_backend_url}/push/subscribe', {{
                    method: 'POST',
                    body: JSON.stringify({{ subscription: sub, store_id: '{store_id}', visitor_id: visitorId }}),
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                console.log("✅ Inscrito com sucesso!");
            }} catch(e) {{ console.error("Erro Push", e); }}
        }}

        if (Notification.permission === 'granted') {{
            initPush();
        }} else if (Notification.permission !== 'denied') {{
            Notification.requestPermission().then(p => {{ if(p==='granted') initPush(); }});
        }}

        window.addEventListener('beforeinstallprompt', (e) => {{ e.preventDefault(); window.deferredPrompt = e; }});

        setTimeout(function(){{
            {fab_script}
            {bottom_bar_script}
        }}, 800);

    }})();
    """
    return Response(content=js, media_type="application/javascript")

# Funções vazias para compatibilidade
def inject_script_tag(a,b): pass
def create_landing_page_internal(a,b,c): pass
