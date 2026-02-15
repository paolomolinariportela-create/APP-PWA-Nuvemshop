import os
import json
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppConfig

router = APIRouter()

# --- CONFIGURAÇÕES DE AMBIENTE ---
# Detecta a URL do backend automaticamente (seja local ou Railway/Render)
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"): 
    BACKEND_URL = f"https://{BACKEND_URL}"

# Chave VAPID Pública para o Frontend (Necessária para Push Notifications)
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")

@router.get("/loader.js", include_in_schema=False)
def get_loader(store_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Gera o script loader.js personalizado para cada loja.
    Uso no frontend da loja: <script src="https://seu-api.com/loader.js?store_id=123"></script>
    """
    
    # 1. Garante que temos uma URL válida para o backend
    # Se a variável de ambiente falhar, tenta pegar do próprio request (fallback seguro)
    final_backend_url = BACKEND_URL or str(request.base_url).rstrip("/")

    # 2. Busca Configurações da Loja no Banco de Dados
    try: 
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except Exception as e:
        print(f"Erro ao buscar config: {e}")
        config = None
    
    # Define valores padrão caso a loja não tenha configurado ainda
    color = config.theme_color if config else "#000000"
    
    # Configurações do Widget (Botão Flutuante)
    fab_enabled = config.fab_enabled if config else False
    fab_text = config.fab_text if config else "Baixar App"
    fab_position = getattr(config, 'fab_position', 'right') # default: direita
    fab_icon = getattr(config, 'fab_icon', '📲')           # default: celular
    fab_delay = getattr(config, 'fab_delay', 0)            # default: 0 segundos

    # CSS Dinâmico da Posição do FAB
    position_css = "right:20px;" if fab_position == "right" else "left:20px;"

    # 3. Gera o Script do Botão Flutuante (FAB)
    fab_script = ""
    if fab_enabled:
        # O script abaixo cria o botão via JS puro, sem dependências externas
        fab_script = f"""
        if (window.innerWidth < 900 && !isApp) {{
            setTimeout(function() {{
                var fab = document.createElement('div');
                fab.id = 'pwa-fab-btn';
                // Estilos inline para garantir que nenhum CSS da loja quebre o botão
                fab.style.cssText = "position:fixed; bottom:20px; {position_css} background:{color}; color:white; padding:12px 24px; border-radius:50px; box-shadow:0 4px 15px rgba(0,0,0,0.3); z-index:2147483647; font-family:sans-serif; font-weight:bold; font-size:14px; display:flex; align-items:center; gap:8px; cursor:pointer; transition: all 0.3s ease;";
                fab.innerHTML = "<span style='font-size:18px'>{fab_icon}</span> <span>{fab_text}</span>";
                
                // Ação de Clique
                fab.onclick = function() {{ 
                    if(window.deferredPrompt) {{
                        window.deferredPrompt.prompt();
                        window.deferredPrompt.userChoice.then(function(choiceResult){{
                            if(choiceResult.outcome === 'accepted') fab.style.display = 'none';
                            window.deferredPrompt = null;
                        }});
                    }} else {{
                         alert("Para instalar:\\nAndroid: Menu > Adicionar à Tela\\niOS: Compartilhar > Adicionar à Tela");
                    }}
                }};
                
                // Animação de Entrada
                fab.animate([{{ transform: 'translateY(100px)', opacity: 0 }}, {{ transform: 'translateY(0)', opacity: 1 }}], {{ duration: 500, easing: 'ease-out' }});
                document.body.appendChild(fab);

                // Efeito 'Pulse' a cada 5 segundos para chamar atenção
                setInterval(() => {{
                    fab.animate([
                        {{ transform: 'scale(1)' }},
                        {{ transform: 'scale(1.05)' }},
                        {{ transform: 'scale(1)' }}
                    ], {{ duration: 1000 }});
                }}, 5000);

            }}, {fab_delay * 1000}); // Aplica o delay configurado
        }}
        """

    # 4. O Script Mágico Completo (Javascript Gerado)
    js = f"""
    (function() {{
        console.log("🚀 PWA Loader Pro v4 (Analytics + Push + Widget)");
        
        // --- A. IDENTIFICAÇÃO DO USUÁRIO ---
        var visitorId = localStorage.getItem('pwa_v_id');
        if(!visitorId) {{ 
            visitorId = 'v_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36); 
            localStorage.setItem('pwa_v_id', visitorId); 
        }}
        
        // Detecta se está rodando como APP ou no Navegador
        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        
        // --- B. INJEÇÃO DE METADADOS ---
        // Injeta o Manifest.json dinâmico
        var link = document.createElement('link'); 
        link.rel = 'manifest'; 
        link.href = '{final_backend_url}/manifest/{store_id}.json'; 
        document.head.appendChild(link);
        
        // Injeta a Cor do Tema no navegador
        var meta = document.createElement('meta'); 
        meta.name = 'theme-color'; 
        meta.content = '{color}'; 
        document.head.appendChild(meta);

        // --- C. ANALYTICS (Rastreio de Visitas) ---
        function trackVisit() {{
            try {{ 
                fetch('{final_backend_url}/analytics/visita', {{ 
                    method: 'POST', 
                    headers: {{'Content-Type': 'application/json'}}, 
                    body: JSON.stringify({{ 
                        store_id: '{store_id}', 
                        pagina: window.location.pathname, 
                        is_pwa: isApp, 
                        visitor_id: visitorId 
                    }}) 
                }}); 
            }} catch(e) {{ console.error("Erro Analytics:", e); }}
        }}
        
        // Rastreia a primeira visita
        trackVisit();
        
        // Rastreia mudanças de página (SPA - Single Page Applications)
        var oldHref = document.location.href;
        new MutationObserver(function() {{ 
            if (oldHref !== document.location.href) {{ 
                oldHref = document.location.href; 
                trackVisit(); 
            }} 
        }}).observe(document.querySelector("body"), {{ childList: true, subtree: true }});

        // --- D. INSTALAÇÃO (Captura o evento) ---
        window.deferredPrompt = null;
        window.addEventListener('beforeinstallprompt', (e) => {{ 
            e.preventDefault(); 
            window.deferredPrompt = e; 
        }});

        // --- E. PUSH NOTIFICATIONS ---
        const publicVapidKey = "{VAPID_PUBLIC_KEY}";

        function urlBase64ToUint8Array(base64String) {{
            const padding = '='.repeat((4 - base64String.length % 4) % 4);
            const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
            const rawData = window.atob(base64);
            const outputArray = new Uint8Array(rawData.length);
            for (let i = 0; i < rawData.length; ++i) {{ outputArray[i] = rawData.charCodeAt(i); }}
            return outputArray;
        }}

        async function subscribePush() {{
            if ('serviceWorker' in navigator && publicVapidKey) {{
                try {{
                    // Registra o Service Worker
                    const registration = await navigator.serviceWorker.register('{final_backend_url}/service-worker.js');
                    await navigator.serviceWorker.ready;
                    
                    // Tenta inscrever
                    const subscription = await registration.pushManager.subscribe({{
                        userVisibleOnly: true,
                        applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
                    }});
                    
                    // Envia inscrição para o Backend
                    await fetch('{final_backend_url}/push/subscribe', {{
                        method: 'POST',
                        body: JSON.stringify({{ 
                            subscription: subscription, 
                            store_id: '{store_id}', 
                            visitor_id: visitorId 
                        }}),
                        headers: {{ 'Content-Type': 'application/json' }}
                    }});
                    console.log("✅ Push Inscrito com Sucesso!");
                }} catch (err) {{ 
                    console.log("Info Push (Pode estar bloqueado ou não suportado):", err); 
                }}
            }}
        }}

        // Tenta inscrever no Push se for o APP instalado
        if (isApp) {{ subscribePush(); }}
        
        // Injeta o script do botão flutuante (se ativado)
        {fab_script}

        // --- F. RASTREIO DE VENDAS (Conversão) ---
        // Tenta detectar venda na página de "Obrigado/Success"
        if (window.location.href.includes('/checkout/success') || window.location.href.includes('/order-received')) {{
            var val = "0.00";
            
            // Tenta achar o valor no DataLayer (Google Analytics/GTM)
            if (window.dataLayer) {{ 
                for(var i=0; i<window.dataLayer.length; i++) {{ 
                    if(window.dataLayer[i].transactionTotal) {{ val = window.dataLayer[i].transactionTotal; break; }}
                    if(window.dataLayer[i].value) {{ val = window.dataLayer[i].value; break; }}
                }} 
            }}
            
            // Evita duplicidade de registro usando LocalStorage
            var oid = window.location.href.split('/').pop(); // Pega ID do pedido da URL
            if (!localStorage.getItem('venda_'+oid) && parseFloat(val) > 0) {{
                fetch('{final_backend_url}/analytics/venda', {{ 
                    method:'POST', 
                    headers:{{'Content-Type':'application/json'}}, 
                    body:JSON.stringify({{ 
                        store_id:'{store_id}', 
                        valor:val.toString(), 
                        visitor_id: visitorId 
                    }}) 
                }});
                localStorage.setItem('venda_'+oid, 'true');
            }}
        }}
    }})();
    """
    
    return Response(content=js, media_type="application/javascript")
