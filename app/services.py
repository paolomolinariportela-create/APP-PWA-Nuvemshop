# app/services.py

import os
import json
import requests
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppConfig
from .auth import decrypt_token

router = APIRouter()

# --- CONFIGURAÇÕES DE AMBIENTE ---
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

# URL do seu site de vendas (para o backlink SEO)
SEU_SITE_VENDAS = "https://www.seusite.com.br"

# --- CONFIGURAÇÃO PUSH (BLINDADA) ---
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")


@router.get("/loader.js", include_in_schema=False)
def get_loader(store_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Gera o script loader.js personalizado para cada loja.
    """
    final_backend_url = BACKEND_URL or str(request.base_url).rstrip("/")

    try:
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except Exception as e:
        print(f"Erro ao buscar config: {e}")
        config = None

    color = config.theme_color if config else "#000000"
    
    # --- NOVAS CORES DA BOTTOM BAR ---
    bottom_bar_bg = getattr(config, "bottom_bar_bg", "#FFFFFF") if config else "#FFFFFF"
    bottom_bar_icon_color = getattr(config, "bottom_bar_icon_color", "#6B7280") if config else "#6B7280"

    # --- FAB CONFIG ---
    fab_enabled = getattr(config, "fab_enabled", False)
    fab_text = getattr(config, "fab_text", "Baixar App")
    fab_position = getattr(config, "fab_position", "right")
    fab_icon = getattr(config, "fab_icon", "📲") or "📲"
    fab_delay = getattr(config, "fab_delay", 0)
    
    position_css = "right:20px;" if fab_position == "right" else "left:20px;"

    # Script do FAB
    fab_script = ""
    if fab_enabled:
        fab_script = f"""
            function initFab() {{
                if (window.innerWidth >= 900 || isApp) return;
                setTimeout(function() {{
                    var fab = document.createElement('div');
                    fab.id = 'pwa-fab-btn';
                    fab.style.cssText = "position:fixed; bottom:20px; {position_css} background:{color}; color:white; padding:12px 24px; border-radius:50px; box-shadow:0 4px 15px rgba(0,0,0,0.3); z-index:2147483647; font-family:sans-serif; font-weight:bold; font-size:14px; display:flex; align-items:center; gap:8px; cursor:pointer; transition: all 0.3s ease;";
                    fab.innerHTML = "<span style='font-size:18px'>{fab_icon}</span> <span>{fab_text}</span>";
                    fab.onclick = function() {{
                        if (window.deferredPrompt) {{
                            window.deferredPrompt.prompt();
                        }} else {{
                            alert('Para instalar: Toque em Compartilhar/Menu e escolha \\\\"Adicionar à Tela de Início\\\\"');
                        }}
                    }};
                    document.body.appendChild(fab);
                }}, {fab_delay * 1000});
            }}
        """

    # Script da Bottom Bar
    bottom_bar_script = f"""
        function initBottomBar() {{
            try {{
                var isPwa = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
                if (!isPwa) return;
                
                var bar = document.createElement('nav');
                bar.style.cssText = `position:fixed; bottom:0; left:0; right:0; height:72px; background:{bottom_bar_bg}; border-top:1px solid #e5e7eb; display:flex; justify-content:space-around; align-items:center; z-index:2147483647; padding-bottom:env(safe-area-inset-bottom,0);`;
                
                function createItem(icon, label, href) {{
                    var btn = document.createElement('a');
                    btn.href = href;
                    btn.style.cssText = `text-decoration:none; display:flex; flex-direction:column; align-items:center; color:{bottom_bar_icon_color}; font-size:10px; font-family:sans-serif;`;
                    btn.innerHTML = `<span style="font-size:24px; margin-bottom:2px;">`+icon+`</span> <span>`+label+`</span>`;
                    return btn;
                }}
                
                bar.appendChild(createItem('🏠', 'Início', '/'));
                bar.appendChild(createItem('🛍️', 'Loja', '/produtos'));
                bar.appendChild(createItem('👤', 'Conta', '/minha-conta'));
                
                document.body.appendChild(bar);
                document.body.style.paddingBottom = "80px";
            }} catch(e) {{}}
        }}
    """

    js = f"""
    (function() {{
        console.log("🚀 PWA Loader Pro v5 - Push Force");

        var visitorId = localStorage.getItem('pwa_v_id');
        if (!visitorId) {{
            visitorId = 'v_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
            localStorage.setItem('pwa_v_id', visitorId);
        }}

        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

        // 1. Meta Tags
        var link = document.createElement('link'); link.rel = 'manifest'; link.href = '{final_backend_url}/manifest/{store_id}.json'; document.head.appendChild(link);
        var meta = document.createElement('meta'); meta.name = 'theme-color'; meta.content = '{color}'; document.head.appendChild(meta);

        // 2. Analytics
        function trackVisit() {{
            fetch('{final_backend_url}/analytics/visita', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ store_id: '{store_id}', pagina: window.location.pathname, is_pwa: isApp, visitor_id: visitorId }})
            }}).catch(e => console.log('Analytics fail', e));
        }}
        trackVisit();

        // 3. Push Notification Logic
        const publicVapidKey = "{VAPID_PUBLIC_KEY}";

        function urlBase64ToUint8Array(base64String) {{
            const padding = '='.repeat((4 - base64String.length % 4) % 4);
            const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            for (let i = 0; i < rawData.length; ++i) {{
                outputArray[i] = rawData.charCodeAt(i);
            }}
            return outputArray;
        }}

        async function subscribePush() {{
            if (!('serviceWorker' in navigator) || !publicVapidKey) {{
                console.log("PUSH: navegador sem SW ou VAPID PUBLIC KEY ausente");
                return;
            }}
            
            try {{
                console.log("PUSH: registrando Service Worker...");
                const registration = await navigator.serviceWorker.register('/service-worker.js', {{ scope: '/' }});
                await navigator.serviceWorker.ready;

                console.log("PUSH: chamando pushManager.subscribe...");
                const subscription = await registration.pushManager.subscribe({{
                    userVisibleOnly: true,
                    applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
                }});

                console.log("📡 Enviando inscrição Push para backend...");
                const res = await fetch('{final_backend_url}/push/subscribe', {{
                    method: 'POST',
                    body: JSON.stringify({{
                        subscription: subscription,
                        store_id: '{store_id}',
                        visitor_id: visitorId
                    }}),
                    headers: {{ 'Content-Type': 'application/json' }}
                }});
                
                const json = await res.json();
                console.log("✅ Push Resultado:", json);

            }} catch (err) {{
                console.error("❌ Erro Push:", err);
            }}
        }}

        // Fluxo de permissão + subscribe
        if (typeof Notification !== 'undefined') {{
            if (Notification.permission === 'granted') {{
                console.log("PUSH: permissão já concedida, inscrevendo...");
                subscribePush();
            }} else if (Notification.permission === 'default') {{
                console.log("PUSH: permissão default, pedindo agora...");
                Notification.requestPermission().then(permission => {{
                    console.log("PUSH: resultado do requestPermission =", permission);
                    if (permission === 'granted') {{
                        subscribePush();
                    }} else {{
                        console.log("PUSH: usuário negou ou fechou o prompt");
                    }}
                }});
            }} else {{
                console.log("PUSH: permissão negada anteriormente, não tenta de novo");
            }}
        }} else {{
            console.log("PUSH: Notification API não disponível neste navegador");
        }}

        // 4. Instalação PWA
        window.addEventListener('beforeinstallprompt', (e) => {{ e.preventDefault(); window.deferredPrompt = e; }});

        // 5. Injeta Scripts Visuais
        setTimeout(function() {{
            {fab_script}
            if (typeof initFab === 'function') initFab();
            
            {bottom_bar_script}
            if (typeof initBottomBar === 'function') initBottomBar();
        }}, 1000);

    }})();
    """

    return Response(content=js, media_type="application/javascript")


# --- FUNÇÕES AUXILIARES (MANTER IGUAL / COMPLETAR DEPOIS, SE USAR) ---
def inject_script_tag(store_id: str, encrypted_access_token: str):
    # (Mantenha ou implemente aqui se precisar usar essa função)
    pass


def create_landing_page_internal(store_id: str, encrypted_access_token: str, color: str):
    # (Mantenha ou implemente aqui se precisar usar essa função)
    pass
