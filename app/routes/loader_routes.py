import os
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppConfig

router = APIRouter()

# --- CONFIGURAÇÕES DE AMBIENTE ---
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")


@router.get("/loader.js", include_in_schema=False)
def get_loader(store_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Gera o script loader.js personalizado para cada loja.
    Uso no frontend da loja: <script src="https://seu-api.com/loader.js?store_id=123"></script>
    """

    final_backend_url = BACKEND_URL or str(request.base_url).rstrip("/")

    try:
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except Exception as e:
        print(f"Erro ao buscar config: {e}")
        config = None

    color = config.theme_color if config else "#000000"

    # --- NOVAS CORES DA BOTTOM BAR (com defaults) ---
    bottom_bar_bg = getattr(config, "bottom_bar_bg", "#FFFFFF") if config else "#FFFFFF"
    bottom_bar_icon_color = getattr(config, "bottom_bar_icon_color", "#6B7280") if config else "#6B7280"

    fab_enabled = True  # FORÇAR LIGADO PARA TESTE
    fab_text = config.fab_text if (config and config.fab_text) else "Baixar App"
    fab_position = getattr(config, "fab_position", "right")

    raw_icon = getattr(config, "fab_icon", None)
    fab_icon = raw_icon if (raw_icon and str(raw_icon).strip()) else "📲"

    fab_delay = getattr(config, "fab_delay", 0)
    position_css = "right:20px;" if fab_position == "right" else "left:20px;"

    # Script do Botão Flutuante (FAB)
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

                    function showInstallHelpModal() {{
                        var existing = document.getElementById('pwa-install-modal');
                        if (existing) existing.remove();

                        var ua = navigator.userAgent || "";
                        var isSamsung = ua.toLowerCase().indexOf('samsungbrowser') !== -1;
                        var isSafari = ua.includes('Safari') && !ua.includes('Chrome');

                        var steps = "";
                        if (isSamsung) {{
                            steps = "1. Toque no menu (⋮) ou ícone de opções.\\n2. Escolha Adicionar página a, depois Tela inicial.\\n3. Confirme o nome do app e toque em Adicionar.";
                        }} else if (isSafari) {{
                            steps = "1. Toque no ícone de compartilhar (quadrado com seta).\\n2. Selecione Adicionar à Tela de Início.\\n3. Confirme o nome do app e toque em Adicionar.";
                        }} else {{
                            steps = "1. Abra o menu do navegador.\\n2. Procure a opção Instalar app ou Adicionar à Tela inicial.\\n3. Confirme para instalar o app no seu celular.";
                        }}

                        var modal = document.createElement('div');
                        modal.id = 'pwa-install-modal';
                        modal.style.cssText = "position:fixed; inset:0; background:rgba(0,0,0,0.55); z-index:2147483648; display:flex; align-items:center; justify-content:center;";

                        var box = document.createElement('div');
                        box.style.cssText = "background:#ffffff; max-width:90%; border-radius:12px; padding:20px; font-family:sans-serif; color:#222; box-shadow:0 8px 30px rgba(0,0,0,0.25);";

                        box.innerHTML = "<div style='font-size:18px; font-weight:bold; margin-bottom:8px;'>Instalar aplicativo</div>" +
                                        "<div style='font-size:14px; line-height:1.5; margin-bottom:12px;'>Siga os passos abaixo para instalar o app na tela inicial do seu celular:</div>" +
                                        "<pre style='white-space:pre-wrap; font-size:13px; background:#f5f5f5; padding:10px; border-radius:8px;'>" + steps + "</pre>" +
                                        "<button id='pwa-install-modal-close' style='margin-top:14px; width:100%; padding:10px 0; border:none; border-radius:8px; background:{color}; color:#fff; font-weight:bold; font-size:14px; cursor:pointer;'>Entendi</button>";

                        modal.appendChild(box);
                        document.body.appendChild(modal);

                        document.getElementById('pwa-install-modal-close').onclick = function() {{
                            modal.remove();
                        }};
                    }}

                    fab.onclick = function() {{
                        if (window.deferredPrompt) {{
                            window.deferredPrompt.prompt();
                            window.deferredPrompt.userChoice.then(function(choiceResult) {{
                                if (choiceResult.outcome === 'accepted') {{
                                    fab.style.display = 'none';
                                    try {{
                                        fetch('{final_backend_url}/analytics/install', {{
                                            method: 'POST',
                                            headers: {{ 'Content-Type': 'application/json' }},
                                            body: JSON.stringify({{
                                                store_id: '{store_id}',
                                                visitor_id: visitorId
                                            }})
                                        }});
                                    }} catch (e) {{}}
                                }}
                                window.deferredPrompt = null;
                            }});
                        }} else {{
                            showInstallHelpModal();
                        }}
                    }};

                    fab.animate(
                        [{{ transform: 'translateY(100px)', opacity: 0 }}, {{ transform: 'translateY(0)', opacity: 1 }}],
                        {{ duration: 500, easing: 'ease-out' }}
                    );
                    document.body.appendChild(fab);

                    setInterval(() => {{
                        fab.animate(
                            [
                                {{ transform: 'scale(1)' }},
                                {{ transform: 'scale(1.05)' }},
                                {{ transform: 'scale(1)' }}
                            ],
                            {{ duration: 1000 }}
                        );
                    }}, 5000);
                }}, {fab_delay * 1000});
            }}
        """

    # --- SCRIPT DA BOTTOM BAR DO APP (NAV INFERIOR DO PWA) ---
    bottom_bar_script = f"""
        function isPwaMode() {{
            try {{
                if (window.matchMedia) {{
                    if (window.matchMedia('(display-mode: standalone)').matches) return true;
                    if (window.matchMedia('(display-mode: fullscreen)').matches) return true;
                    if (window.matchMedia('(display-mode: minimal-ui)').matches) return true;
                }}
                if (window.navigator.standalone === true) return true; // iOS 
            }} catch (e) {{}}
            return false;
        }}

        function initBottomBar() {{
            try {{
                if (!isPwaMode()) return;
                if (window.innerWidth > 900) return;
                if (document.getElementById('pwa-bottom-nav')) return;

                var bar = document.createElement('nav');
                bar.id = 'pwa-bottom-nav';
                bar.style.cssText = `
                    position:fixed;
                    bottom:0;
                    left:0;
                    right:0;
                    height:72px;
                    background:{bottom_bar_bg};
                    border-top:1px solid #e5e7eb;
                    display:flex;
                    justify-content:space-around;
                    align-items:center;
                    font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;
                    z-index:2147483647;
                    padding-bottom: env(safe-area-inset-bottom, 0);
                `;

                try {{
                    var currentPadding = window.getComputedStyle(document.body).paddingBottom || "0px";
                    var base = parseInt(currentPadding, 10) || 0;
                    var extra = 72;
                    document.body.style.paddingBottom = (base + extra) + "px";
                }} catch (e) {{}}

                function createItem(svgPath, label, href) {{
                    var btn = document.createElement('button');
                    btn.style.cssText = `
                        background:none;
                        border:none;
                        display:flex;
                        flex-direction:column;
                        align-items:center;
                        justify-content:center;
                        gap:4px;
                        font-size:10px;
                        color:{bottom_bar_icon_color};
                        cursor:pointer;
                    `;
                    btn.onclick = function() {{
                        try {{
                            if (href) window.location.href = href;
                        }} catch (e) {{}}
                    }};

                    var iconWrapper = document.createElement('div');
                    iconWrapper.style.cssText = `
                        width:28px;
                        height:28px;
                        display:flex;
                        align-items:center;
                        justify-content:center;
                    `;

                    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
                    svg.setAttribute('viewBox', '0 0 24 24');
                    svg.setAttribute('width', '28');
                    svg.setAttribute('height', '28');
                    svg.style.fill = 'currentColor';

                    var path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
                    path.setAttribute('d', svgPath);
                    svg.appendChild(path);
                    iconWrapper.appendChild(svg);

                    var text = document.createElement('span');
                    text.textContent = label;
                    text.style.cssText = 'font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;';

                    btn.appendChild(iconWrapper);
                    btn.appendChild(text);
                    return btn;
                }}

                var homePath = "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z";
                var shopPath = "M7 18c-1.1 0-2-.9-2-2V6h14v10c0 1.1-.9 2-2 2H7zm0-2h10V8H7v8zM9 4V2h6v2h5v2H4V4h5z";
                var bellPath = "M12 22c1.1 0 2-.9 2-2h-4a2 2 0 0 0 2 2zm6-6V11c0-3.07-1.63-5.64-4.5-6.32V4a1.5 1.5 0 0 0-3 0v.68C7.63 5.36 6 7.92 6 11v5l-1.5 1.5v.5h15v-.5L18 16z";
                var userPath = "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z";

                bar.appendChild(createItem(homePath, "Início", "/"));
                bar.appendChild(createItem(shopPath, "Loja", "/produtos"));
                bar.appendChild(createItem(bellPath, "Alertas", "/notificacoes"));
                bar.appendChild(createItem(userPath, "Conta", "/minha-conta"));

                document.body.appendChild(bar);
            }} catch (e) {{
                console.log('Bottom bar error:', e);
            }}
        }}
    """

    # JS FINAL (v5, com push corrigido)
    js = f"""
    (function() {{
        console.log("🚀 PWA Loader Pro v5 - Push Force");

        // --- A. IDENTIFICAÇÃO DO USUÁRIO ---
        var visitorId = localStorage.getItem('pwa_v_id');
        if (!visitorId) {{
            visitorId = 'v_' + Math.random().toString(36).substr(2, 9) + Date.now().toString(36);
            localStorage.setItem('pwa_v_id', visitorId);
        }}

        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;

        // --- B. METADADOS ---
        function initMeta() {{
            var link = document.createElement('link');
            link.rel = 'manifest';
            link.href = '{final_backend_url}/manifest/{store_id}.json';
            document.head.appendChild(link);

            var meta = document.createElement('meta');
            meta.name = 'theme-color';
            meta.content = '{color}';
            document.head.appendChild(meta);
        }}

        // --- C. ANALYTICS ---
        function buildVisitPayload() {{
            var payload = {{
                store_id: '{store_id}',
                pagina: window.location.pathname,
                is_pwa: isApp,
                visitor_id: visitorId
            }};

            try {{
                if (window.LS && LS.store) {{
                    payload.store_ls_id = LS.store.id;
                }}
            }} catch (e) {{}}

            try {{
                if (window.LS && LS.product) {{
                    payload.product_id = LS.product.id;
                    if (LS.product.name) {{
                        payload.product_name = LS.product.name;
                    }}
                }}
            }} catch (e) {{}}

            try {{
                if (window.LS && LS.cart) {{
                    if (typeof LS.cart.subtotal !== 'undefined') {{
                        payload.cart_total = LS.cart.subtotal;
                    }}
                    if (Array.isArray(LS.cart.items)) {{
                        payload.cart_items_count = LS.cart.items.length;
                    }}
                }}
            }} catch (e) {{}}

            return payload;
        }}

        function trackVisit() {{
            try {{
                var body = buildVisitPayload();
                fetch('{final_backend_url}/analytics/visita', {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(body)
                }});
            }} catch (e) {{
                console.error('Erro Analytics:', e);
            }}
        }}

        function initAnalytics() {{
            trackVisit();

            try {{
                var oldHref = document.location.href;
                new MutationObserver(function() {{
                    if (oldHref !== document.location.href) {{
                        oldHref = document.location.href;
                        trackVisit();
                    }}
                }}).observe(document.querySelector('body'), {{ childList: true, subtree: true }});
            }} catch (e) {{}}
        }}

        // --- D. INSTALAÇÃO ---
        function initInstallCapture() {{
            window.deferredPrompt = null;
            window.addEventListener('beforeinstallprompt', function(e) {{
                e.preventDefault();
                window.deferredPrompt = e;
            }});
        }}

        // --- E. PUSH (v5, com permissão + subscribe + logs claros) ---
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

        function checkNotificationPermission() {{
            if (!('Notification' in window)) {{
                return 'unsupported';
            }}
            return Notification.permission;
        }}

        async function askNotificationAndSubscribe() {{
            if (!('Notification' in window)) return;

            const current = Notification.permission;

            console.log("PUSH: permissão atual =", current);

            if (current === 'granted') {{
                console.log("PUSH: permissão já concedida, inscrevendo...");
                subscribePush();
                return;
            }}

            if (current === 'denied') {{
                alert('As notificações estão bloqueadas neste dispositivo. Ative nas configurações do navegador para receber atualizações.');
                return;
            }}

            console.log("PUSH: permissão default, pedindo agora...");
            const result = await Notification.requestPermission();
            console.log("PUSH: resultado do requestPermission =", result);
            if (result === 'granted') {{
                subscribePush();
            }} else {{
                console.log('PUSH: usuário não concedeu a permissão:', result);
            }}
        }}

        function showNotificationTopBar() {{
            if (!('Notification' in window)) return;
            if (Notification.permission === 'granted') return;

            var existingBar = document.getElementById('pwa-notification-bar');
            if (existingBar) return;

            var bar = document.createElement('div');
            bar.id = 'pwa-notification-bar';
            bar.style.cssText = `
                position:fixed;
                top:0;
                left:0;
                right:0;
                z-index:2147483647;
                background:#111827;
                color:#F9FAFB;
                padding:10px 14px;
                display:flex;
                align-items:center;
                justify-content:space-between;
                font-family:sans-serif;
                font-size:13px;
                box-shadow:0 2px 8px rgba(0,0,0,0.35);
            `;

            bar.innerHTML = `
                <div style="display:flex; align-items:center; gap:8px;">
                  <span style="font-size:16px;">🔔</span>
                  <span>Ative as notificações para receber atualizações de pedidos, cupons e novidades.</span>
                </div>
                <div style="display:flex; gap:8px;">
                  <button id="pwa-notif-allow" style="padding:6px 10px; border-radius:6px; border:none; background:#22C55E; color:#fff; font-weight:bold; font-size:12px; cursor:pointer;">Ativar</button>
                  <button id="pwa-notif-close" style="padding:6px 8px; border-radius:6px; border:none; background:transparent; color:#9CA3AF; font-size:12px; cursor:pointer;">Agora não</button>
                </div>
            `;

            document.body.appendChild(bar);

            document.getElementById('pwa-notif-allow').onclick = function () {{
                askNotificationAndSubscribe();
                bar.remove();
            }};

            document.getElementById('pwa-notif-close').onclick = function () {{
                bar.remove();
            }};
        }}

        function initNotificationBar() {{
            if (isApp) {{
                showNotificationTopBar();
            }}
        }}

        // --- VARIANTES ---
        function initVariantTracking() {{
            try {{
                if (window.LS && typeof LS.registerOnChangeVariant === 'function') {{
                    LS.registerOnChangeVariant(function(variant) {{
                        try {{
                            var productId = null;
                            var productName = null;

                            try {{
                                if (LS.product) {{
                                    productId = LS.product.id || null;
                                    productName = LS.product.name || null;
                                }}
                            }} catch (e) {{}}

                            var payload = {{
                                store_id: '{store_id}',
                                visitor_id: visitorId,
                                product_id: productId ? String(productId) : '',
                                variant_id: variant && variant.id ? String(variant.id) : '',
                                variant_name: variant && variant.name ? String(variant.name) : productName || null,
                                price: variant && typeof variant.price !== 'undefined' ? String(variant.price) : null,
                                stock: variant && typeof variant.stock !== 'undefined' ? variant.stock : null
                            }};

                            if (!payload.variant_id) {{
                                return;
                            }}

                            fetch('{final_backend_url}/analytics/variant', {{
                                method: 'POST',
                                headers: {{ 'Content-Type': 'application/json' }},
                                body: JSON.stringify(payload)
                            }});
                        }} catch (err) {{
                            console.log('Variant event error:', err);
                        }}
                    }});
                }}
            }} catch (e) {{}}
        }}

        // --- VENDAS ---
        function initSalesTracking() {{
            try {{
                if (window.location.href.includes('/checkout/success') || window.location.href.includes('/order-received')) {{
                    var val = '0.00';

                    if (window.dataLayer) {{
                        for (var i = 0; i < window.dataLayer.length; i++) {{
                            if (window.dataLayer[i].transactionTotal) {{
                                val = window.dataLayer[i].transactionTotal;
                                break;
                            }}
                            if (window.dataLayer[i].value) {{
                                val = window.dataLayer[i].value;
                                break;
                            }}
                        }}
                    }}

                    var oid = window.location.href.split('/').pop();
                    if (!localStorage.getItem('venda_' + oid) && parseFloat(val) > 0) {{
                        fetch('{final_backend_url}/analytics/venda', {{
                            method: 'POST',
                            headers: {{ 'Content-Type': 'application/json' }},
                            body: JSON.stringify({{
                                store_id: '{store_id}',
                                valor: val.toString(),
                                visitor_id: visitorId
                            }})
                        }});
                        localStorage.setItem('venda_' + oid, 'true');
                    }}
                }}
            }} catch (e) {{
                console.log('Venda tracking error:', e);
            }}
        }}

        // --- INICIALIZAÇÃO ---
        try {
            initMeta();
            initInstallCapture();
            initAnalytics();

            // Mostrar barra de ativação de notificações também no navegador,
            // não só dentro do PWA, para facilitar o opt-in.
            initNotificationBar();
        } catch (e) {
            console.log('Critical block error:', e);
        }

        // Bloco diferido: FAB e tracking
        setTimeout(function () {{
            try {{
                {fab_script}
                if (typeof initFab === 'function') {{
                    initFab();
                }}
                initVariantTracking();
                initSalesTracking();
            }} catch (e) {{
                console.log('Deferred block error (FAB/Analytics):', e);
            }}
        }}, 800);

        // Bottom bar: inicializa assim que o DOM estiver pronto
        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', function() {{
                try {{
                    {bottom_bar_script}
                    if (typeof initBottomBar === 'function') {{
                        initBottomBar();
                    }}
                }} catch (e) {{
                    console.log('Bottom bar init error:', e);
                }}
            }});
        }} else {{
            try {{
                {bottom_bar_script}
                if (typeof initBottomBar === 'function') {{
                    initBottomBar();
                }}
            }} catch (e) {{
                console.log('Bottom bar init error:', e);
            }}
        }}
    }})();
    """

    return Response(content=js, media_type="application/javascript")
