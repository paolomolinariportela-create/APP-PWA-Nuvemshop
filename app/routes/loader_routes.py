import os
from fastapi import APIRouter, Depends, Response, Request
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import AppConfig

router = APIRouter()

BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

# ✅ VAPID removido — push é 100% via OneSignal


@router.get("/loader.js", include_in_schema=False)
def get_loader(store_id: str, request: Request, db: Session = Depends(get_db)):
    final_backend_url = BACKEND_URL or str(request.base_url).rstrip("/")

    try:
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except Exception as e:
        print(f"Erro ao buscar config: {e}")
        config = None

    color = config.theme_color if config else "#000000"
    bottom_bar_bg = getattr(config, "bottom_bar_bg", "#FFFFFF") if config else "#FFFFFF"
    bottom_bar_icon_color = getattr(config, "bottom_bar_icon_color", "#6B7280") if config else "#6B7280"

    fab_enabled = bool(getattr(config, "fab_enabled", False)) if config else False
    fab_text = getattr(config, "fab_text", None) or "Baixar App"
    fab_position = getattr(config, "fab_position", "right") or "right"
    raw_icon = getattr(config, "fab_icon", None)
    fab_icon = raw_icon if (raw_icon and str(raw_icon).strip()) else "📲"
    fab_delay = getattr(config, "fab_delay", 0) or 0
    fab_color = getattr(config, "fab_color", "#2563EB") if config else "#2563EB"
    fab_size = getattr(config, "fab_size", "medium") if config else "medium"

    if fab_size == "xs":
        fab_width, fab_height = 54, 46
    elif fab_size == "small":
        fab_width, fab_height = 70, 50
    elif fab_size == "large":
        fab_width, fab_height = 120, 60
    elif fab_size == "xl":
        fab_width, fab_height = 140, 66
    else:
        fab_width, fab_height = 90, 54

    offset_px = 56
    position_css = f"right:{offset_px}px;" if fab_position == "right" else f"left:{offset_px}px;"

    topbar_enabled = bool(getattr(config, "topbar_enabled", False)) if config else False
    topbar_text = getattr(config, "topbar_text", None) or "Baixe nosso app"
    topbar_button_text = getattr(config, "topbar_button_text", None) or "Baixar"
    topbar_icon = getattr(config, "topbar_icon", None) or "📲"
    topbar_position = getattr(config, "topbar_position", None) or "bottom"
    topbar_color = getattr(config, "topbar_color", None) or "#111827"
    topbar_text_color = getattr(config, "topbar_text_color", None) or "#FFFFFF"
    topbar_button_bg_color = getattr(config, "topbar_button_bg_color", None) or "#FBBF24"
    topbar_button_text_color = getattr(config, "topbar_button_text_color", None) or "#111827"
    topbar_background_image_url = getattr(config, "topbar_background_image_url", "") or ""

    popup_enabled = bool(getattr(config, "popup_enabled", False)) if config else False
    popup_image_url = getattr(config, "popup_image_url", "") or ""

    onesignal_app_id = getattr(config, "onesignal_app_id", "") if config else ""

    fab_script = ""
    if fab_enabled:
        fab_script = f"""
        function initFab() {{
            if (isApp) return;
            if (window.innerWidth >= 900) return;
            setTimeout(function() {{
                var fab = document.createElement('div');
                fab.id = 'pwa-fab-btn';
                fab.style.cssText = "position:fixed;bottom:{offset_px}px;{position_css}background:{fab_color};color:white;width:{fab_width}px;height:{fab_height}px;border-radius:9999px;box-shadow:0 4px 15px rgba(0,0,0,0.3);z-index:2147483647;font-family:sans-serif;font-weight:bold;font-size:13px;display:flex;align-items:center;justify-content:center;gap:8px;cursor:pointer;padding:0 22px;";
                var iconSpan = document.createElement('span');
                iconSpan.style.fontSize = "20px";
                iconSpan.textContent = "{fab_icon}";
                var textSpan = document.createElement('span');
                textSpan.textContent = "{fab_text}";
                textSpan.style.whiteSpace = "nowrap";
                fab.appendChild(iconSpan);
                fab.appendChild(textSpan);
                fab.onclick = function() {{
                    if (window.deferredPrompt) {{
                        window.deferredPrompt.prompt();
                        window.deferredPrompt.userChoice.then(function(r) {{
                            if (r.outcome === 'accepted') {{
                                fab.style.display = 'none';
                                try {{ fetch('{final_backend_url}/analytics/install', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{store_id:'{store_id}',visitor_id:visitorId}}) }}); }} catch(e) {{}}
                            }}
                            window.deferredPrompt = null;
                        }});
                    }} else {{ showInstallHelpModal(); }}
                }};
                fab.animate([{{transform:'translateY(100px)',opacity:0}},{{transform:'translateY(0)',opacity:1}}],{{duration:500,easing:'ease-out'}});
                document.body.appendChild(fab);
                setInterval(function() {{ fab.animate([{{transform:'scale(1)'}},{{transform:'scale(1.05)'}},{{transform:'scale(1)'}}],{{duration:1000}}); }}, 5000);
            }}, {fab_delay * 1000});
        }}
        """

    topbar_script = ""
    if topbar_enabled:
        top_position_css = "top:0;" if topbar_position == "top" else "bottom:0;"
        safe_topbar_text = (topbar_text or "").replace('"', '\\\\"')
        safe_topbar_button_text = (topbar_button_text or "").replace('"', '\\\\"')
        background_style = (
            f"background-image:url('{topbar_background_image_url}');background-size:cover;background-position:center;"
            if topbar_background_image_url else f"background:{topbar_color};"
        )
        topbar_script = f"""
        function initTopbarWidget() {{
            try {{
                if (isApp) return;
                if (window.innerWidth >= 900) return;
                if (document.getElementById('pwa-topbar-widget')) return;
                var bar = document.createElement('div');
                bar.id = 'pwa-topbar-widget';
                bar.style.cssText = `position:fixed;{top_position_css}left:0;right:0;{background_style}color:{topbar_text_color};padding:10px 14px;display:flex;align-items:center;justify-content:space-between;font-family:sans-serif;font-size:13px;z-index:2147483647;box-shadow:0 2px 8px rgba(0,0,0,0.3);`;
                try {{
                    var barHeight = 44;
                    if ("{topbar_position}" === "top") {{
                        var ct = window.getComputedStyle(document.body).paddingTop || "0px";
                        document.body.style.paddingTop = (parseInt(ct,10)||0) + barHeight + "px";
                    }} else {{
                        var cb = window.getComputedStyle(document.body).paddingBottom || "0px";
                        document.body.style.paddingBottom = (parseInt(cb,10)||0) + barHeight + "px";
                    }}
                }} catch(e) {{}}
                var left = document.createElement('div');
                left.style.cssText = "display:flex;align-items:center;gap:8px;";
                var iconSpan = document.createElement('span');
                iconSpan.textContent = "{topbar_icon}";
                iconSpan.style.fontSize = "16px";
                var overlayText = document.createElement('span');
                overlayText.textContent = "{safe_topbar_text}";
                overlayText.style.flex = "1";
                left.appendChild(iconSpan);
                left.appendChild(overlayText);
                var btn = document.createElement('button');
                btn.textContent = "{safe_topbar_button_text}";
                btn.style.cssText = `background:{topbar_button_bg_color};color:{topbar_button_text_color};border:none;border-radius:999px;padding:6px 12px;font-size:12px;font-weight:600;cursor:pointer;`;
                btn.onclick = function() {{
                    if (window.deferredPrompt) {{
                        window.deferredPrompt.prompt();
                        window.deferredPrompt.userChoice.then(function(r) {{
                            if (r.outcome === 'accepted') {{
                                try {{ fetch('{final_backend_url}/analytics/install', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{store_id:'{store_id}',visitor_id:visitorId}}) }}); }} catch(e) {{}}
                            }}
                            window.deferredPrompt = null;
                        }});
                    }} else {{ showInstallHelpModal(); }}
                }};
                bar.appendChild(left);
                bar.appendChild(btn);
                document.body.appendChild(bar);
            }} catch(e) {{ console.log("Topbar widget error:", e); }}
        }}
        """

    popup_script = ""
    if popup_enabled and popup_image_url:
        popup_script = f"""
        function initInstallPopup() {{
            try {{
                if (isApp) return;
                if (window.innerWidth >= 900) return;
                if (!window.deferredPrompt) return;
                if (document.getElementById('pwa-install-popup')) return;
                var overlay = document.createElement('div');
                overlay.id = 'pwa-install-popup';
                overlay.style.cssText = `position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:2147483647;display:flex;align-items:center;justify-content:center;`;
                var box = document.createElement('div');
                box.style.cssText = `position:relative;width:90%;max-width:400px;border-radius:16px;overflow:hidden;box-shadow:0 10px 30px rgba(0,0,0,0.5);background:#000;`;
                var img = document.createElement('div');
                img.style.cssText = `width:100%;padding-top:177%;background-image:url('{popup_image_url}');background-size:cover;background-position:center;`;
                var btnArea = document.createElement('div');
                btnArea.style.cssText = `position:absolute;bottom:12px;left:0;right:0;display:flex;justify-content:center;gap:8px;`;
                var installBtn = document.createElement('button');
                installBtn.textContent = "Instalar app";
                installBtn.style.cssText = `background:#10B981;color:#fff;border:none;border-radius:999px;padding:10px 18px;font-size:14px;font-weight:600;cursor:pointer;`;
                installBtn.onclick = function() {{
                    if (!window.deferredPrompt) {{ overlay.remove(); return; }}
                    window.deferredPrompt.prompt();
                    window.deferredPrompt.userChoice.then(function(r) {{
                        if (r.outcome === 'accepted') {{
                            try {{ fetch('{final_backend_url}/analytics/install', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{store_id:'{store_id}',visitor_id:visitorId}}) }}); }} catch(e) {{}}
                        }}
                        window.deferredPrompt = null;
                        overlay.remove();
                    }});
                }};
                var closeBtn = document.createElement('button');
                closeBtn.textContent = "Fechar";
                closeBtn.style.cssText = `background:rgba(0,0,0,0.6);color:#fff;border:none;border-radius:999px;padding:8px 14px;font-size:12px;cursor:pointer;`;
                closeBtn.onclick = function() {{ overlay.remove(); }};
                btnArea.appendChild(installBtn);
                btnArea.appendChild(closeBtn);
                box.appendChild(img);
                box.appendChild(btnArea);
                overlay.appendChild(box);
                document.body.appendChild(overlay);
            }} catch(e) {{ console.log("Popup install error:", e); }}
        }}
        """

    bottom_bar_script = f"""
    function isPwaMode() {{
        try {{
            if (window.matchMedia) {{
                if (window.matchMedia('(display-mode: standalone)').matches) return true;
                if (window.matchMedia('(display-mode: fullscreen)').matches) return true;
                if (window.matchMedia('(display-mode: minimal-ui)').matches) return true;
            }}
            if (window.navigator.standalone === true) return true;
        }} catch(e) {{}}
        return false;
    }}

    function initBottomBar() {{
        try {{
            if (!isPwaMode()) return;
            if (window.innerWidth > 900) return;
            if (document.getElementById('pwa-bottom-nav')) return;
            var bar = document.createElement('nav');
            bar.id = 'pwa-bottom-nav';
            bar.style.cssText = `position:fixed;bottom:0;left:0;right:0;height:72px;background:{bottom_bar_bg};border-top:1px solid #e5e7eb;display:flex;justify-content:space-around;align-items:center;font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;z-index:2147483647;padding-bottom:env(safe-area-inset-bottom,0);`;
            try {{
                var cp = window.getComputedStyle(document.body).paddingBottom || "0px";
                document.body.style.paddingBottom = (parseInt(cp,10)||0) + 72 + "px";
            }} catch(e) {{}}
            function createItem(svgPath, label, href) {{
                var btn = document.createElement('button');
                btn.style.cssText = `background:none;border:none;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;color:{bottom_bar_icon_color};cursor:pointer;`;
                btn.onclick = function() {{ try {{ if (href) window.location.href = href; }} catch(e) {{}} }};
                var iw = document.createElement('div');
                iw.style.cssText = `width:28px;height:28px;display:flex;align-items:center;justify-content:center;`;
                var svg = document.createElementNS('http://www.w3.org/2000/svg','svg');
                svg.setAttribute('viewBox','0 0 24 24');
                svg.setAttribute('width','28');
                svg.setAttribute('height','28');
                svg.style.fill = 'currentColor';
                var path = document.createElementNS('http://www.w3.org/2000/svg','path');
                path.setAttribute('d', svgPath);
                svg.appendChild(path);
                iw.appendChild(svg);
                var text = document.createElement('span');
                text.textContent = label;
                text.style.cssText = 'font-size:9px;font-weight:600;text-transform:uppercase;letter-spacing:0.04em;';
                btn.appendChild(iw);
                btn.appendChild(text);
                return btn;
            }}
            bar.appendChild(createItem("M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z","Início","/"));
            bar.appendChild(createItem("M7 18c-1.1 0-2-.9-2-2V6h14v10c0 1.1-.9 2-2 2H7zm0-2h10V8H7v8zM9 4V2h6v2h5v2H4V4h5z","Loja","/produtos"));
            bar.appendChild(createItem("M12 22c1.1 0 2-.9 2-2h-4a2 2 0 0 0 2 2zm6-6V11c0-3.07-1.63-5.64-4.5-6.32V4a1.5 1.5 0 0 0-3 0v.68C7.63 5.36 6 7.92 6 11v5l-1.5 1.5v.5h15v-.5L18 16z","Alertas","/notificacoes"));
            bar.appendChild(createItem("M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-2.67 0-8 1.34-8 4v2h16v-2c0-2.66-5.33-4-8-4z","Conta","/minha-conta"));
            document.body.appendChild(bar);
        }} catch(e) {{ console.log('Bottom bar error:', e); }}
    }}
    """

    js = f"""
    (function() {{

        // ✅ Limpa TODOS os SWs antigos na primeira execução
        if ('serviceWorker' in navigator) {{
            navigator.serviceWorker.getRegistrations().then(function(regs) {{
                regs.forEach(function(r) {{ r.unregister(); }});
            }});
        }}

        var visitorId = localStorage.getItem('pwa_v_id');
        if (!visitorId) {{
            visitorId = 'v_' + Math.random().toString(36).substr(2,9) + Date.now().toString(36);
            localStorage.setItem('pwa_v_id', visitorId);
        }}

        var isApp = (
            (window.matchMedia && window.matchMedia('(display-mode: standalone)').matches) ||
            (window.matchMedia && window.matchMedia('(display-mode: fullscreen)').matches) ||
            (window.matchMedia && window.matchMedia('(display-mode: minimal-ui)').matches) ||
            window.navigator.standalone === true
        );

        // =============================================
        // ✅ LOGGER VISUAL — remove após confirmar funcionamento
        // =============================================
        var logBox = null;
        if (isApp) {{
            logBox = document.createElement('div');
            logBox.id = 'pwa-debug-log';
            logBox.style.cssText = `
                position:fixed;top:0;left:0;right:0;z-index:2147483647;
                background:rgba(0,0,0,0.88);color:#00FF00;
                font-family:monospace;font-size:11px;padding:8px 10px;
                max-height:220px;overflow-y:auto;
            `;
            var closeLog = document.createElement('button');
            closeLog.textContent = '✕ fechar log';
            closeLog.style.cssText = 'display:block;margin-bottom:6px;background:#333;color:#fff;border:none;padding:4px 8px;border-radius:4px;cursor:pointer;font-size:11px;';
            closeLog.onclick = function() {{ logBox.remove(); }};
            logBox.appendChild(closeLog);
            if (document.body) {{
                document.body.appendChild(logBox);
            }} else {{
                document.addEventListener('DOMContentLoaded', function() {{ document.body.appendChild(logBox); }});
            }}
        }}

        function pwaLog(msg) {{
            console.log('[PWA] ' + msg);
            if (!logBox) return;
            var line = document.createElement('div');
            line.textContent = new Date().toLocaleTimeString('pt-BR') + ' › ' + msg;
            logBox.appendChild(line);
            logBox.scrollTop = logBox.scrollHeight;
        }}

        pwaLog('🚀 Loader v8 — diagnóstico optIn');
        pwaLog('isApp: ' + isApp);
        pwaLog('permission: ' + (typeof Notification !== 'undefined' ? Notification.permission : 'indisponivel'));
        pwaLog('notif_asked: ' + localStorage.getItem('notif_asked'));
        pwaLog('onesignal_app_id: {onesignal_app_id or "NAO CONFIGURADO"}');
        // =============================================

        function initMeta() {{
            var link = document.createElement('link');
            link.rel = 'manifest';
            link.href = '/apps/app-builder/manifest/{store_id}.json';
            document.head.appendChild(link);
            var meta = document.createElement('meta');
            meta.name = 'theme-color';
            meta.content = '{color}';
            document.head.appendChild(meta);
        }}

        function buildVisitPayload() {{
            var payload = {{ store_id:'{store_id}', pagina:window.location.pathname, is_pwa:isApp, visitor_id:visitorId }};
            try {{ if (window.LS && LS.store) payload.store_ls_id = LS.store.id; }} catch(e) {{}}
            try {{ if (window.LS && LS.product) {{ payload.product_id = LS.product.id; if (LS.product.name) payload.product_name = LS.product.name; }} }} catch(e) {{}}
            try {{ if (window.LS && LS.cart) {{ if (typeof LS.cart.subtotal !== 'undefined') payload.cart_total = LS.cart.subtotal; if (Array.isArray(LS.cart.items)) payload.cart_items_count = LS.cart.items.length; }} }} catch(e) {{}}
            return payload;
        }}

        function trackVisit() {{
            try {{ fetch('{final_backend_url}/analytics/visita', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(buildVisitPayload()) }}); }} catch(e) {{}}
        }}

        function initAnalytics() {{
            trackVisit();
            try {{
                var oldHref = document.location.href;
                new MutationObserver(function() {{
                    if (oldHref !== document.location.href) {{ oldHref = document.location.href; trackVisit(); }}
                }}).observe(document.querySelector('body'), {{ childList:true, subtree:true }});
            }} catch(e) {{}}
        }}

        function initInstallCapture() {{
            window.deferredPrompt = null;
            window.addEventListener('beforeinstallprompt', function(e) {{
                e.preventDefault();
                window.deferredPrompt = e;
                if (typeof initInstallPopup === 'function') initInstallPopup();
            }});
        }}

        function checkSubStatus() {{
            try {{
                var subId = window.OneSignal.User.PushSubscription.id;
                var token = window.OneSignal.User.PushSubscription.token;
                var optedIn = window.OneSignal.User.PushSubscription.optedIn;
                pwaLog('--- STATUS SUBSCRIPTION ---');
                pwaLog('optedIn: ' + optedIn);
                pwaLog('id: ' + (subId || 'null'));
                pwaLog('token: ' + (token ? token.substring(0,30)+'...' : 'null'));
            }} catch(e) {{ pwaLog('Erro checkSubStatus: ' + e.message); }}
        }}

        function initNotificationBar() {{
            if (typeof Notification !== 'undefined' && Notification.permission === 'granted') {{
                pwaLog('⚠️ permission=granted — chamando optIn() direto');
                window.OneSignal.User.PushSubscription.optIn().then(function() {{
                    pwaLog('✅ optIn() direto concluído');
                    setTimeout(checkSubStatus, 3000);
                }}).catch(function(e) {{
                    pwaLog('❌ optIn() direto erro: ' + e.message);
                }});
                return;
            }}
            if (typeof Notification !== 'undefined' && Notification.permission === 'denied') {{
                pwaLog('❌ Barra bloqueada: permission=denied');
                return;
            }}
            if (localStorage.getItem('notif_asked')) {{
                pwaLog('❌ Barra bloqueada: notif_asked salvo');
                return;
            }}
            if (document.getElementById('pwa-notification-bar')) return;

            pwaLog('⏳ Barra será exibida em 3s...');
            setTimeout(function() {{
                if (document.getElementById('pwa-notification-bar')) return;
                var bar = document.createElement('div');
                bar.id = 'pwa-notification-bar';
                bar.style.cssText = `
                    position:fixed;bottom:80px;left:12px;right:12px;z-index:2147483647;
                    background:#111827;color:#F9FAFB;padding:12px 14px;
                    display:flex;align-items:center;justify-content:space-between;
                    font-family:sans-serif;font-size:13px;
                    box-shadow:0 4px 20px rgba(0,0,0,0.4);border-radius:12px;
                    animation:pwaBannerUp 0.4s ease-out;
                `;
                bar.innerHTML = `
                    <style>@keyframes pwaBannerUp{{from{{transform:translateY(30px);opacity:0}}to{{transform:translateY(0);opacity:1}}}}</style>
                    <div style="display:flex;align-items:center;gap:8px;flex:1;">
                      <span style="font-size:18px;">🔔</span>
                      <span style="line-height:1.3;">Ative notificações e receba cupons exclusivos!</span>
                    </div>
                    <div style="display:flex;gap:6px;margin-left:10px;">
                      <button id="pwa-notif-allow" style="padding:7px 12px;border-radius:8px;border:none;background:#22C55E;color:#fff;font-weight:bold;font-size:12px;cursor:pointer;white-space:nowrap;">Ativar</button>
                      <button id="pwa-notif-close" style="padding:7px 8px;border-radius:8px;border:none;background:transparent;color:#9CA3AF;font-size:18px;line-height:1;cursor:pointer;">✕</button>
                    </div>
                `;
                document.body.appendChild(bar);
                pwaLog('✅ Barra exibida!');

                document.getElementById('pwa-notif-allow').onclick = function() {{
                    localStorage.setItem('notif_asked', '1');
                    bar.remove();
                    pwaLog('🔔 Chamando optIn()...');
                    window.OneSignal.User.PushSubscription.optIn().then(function() {{
                        pwaLog('✅ optIn() concluído');
                        // ✅ Verifica subscription 3s após optIn
                        setTimeout(checkSubStatus, 3000);
                    }}).catch(function(e) {{
                        pwaLog('❌ optIn() erro: ' + e.message);
                    }});
                }};
                document.getElementById('pwa-notif-close').onclick = function() {{
                    localStorage.setItem('notif_asked', '1');
                    bar.remove();
                    pwaLog('Barra fechada pelo usuário');
                }};
            }}, 3000);
        }}

        function initOneSignalInApp() {{
            if (!isApp) {{
                pwaLog('OneSignal ignorado: não é PWA');
                return;
            }}

            var appId = '{onesignal_app_id}';
            if (!appId) {{
                pwaLog('❌ OneSignal: onesignal_app_id não configurado para esta loja');
                return;
            }}

            // ✅ Desregistra SW antigo (escopo /) antes de registrar novo (/apps/app-builder/)
            if ('serviceWorker' in navigator) {{
                navigator.serviceWorker.getRegistrations().then(function(registrations) {{
                    registrations.forEach(function(r) {{
                        if (r.scope.endsWith('/') && !r.scope.includes('/apps/')) {{
                            pwaLog('SW antigo: ' + r.scope + ' — desregistrando...');
                            r.unregister();
                        }}
                    }});
                }});
            }}

            // ✅ Registra SW manualmente via proxy Nuvemshop antes do OneSignal init
            if ("serviceWorker" in navigator) {{
                navigator.serviceWorker.register("/apps/app-builder/service-worker.js", {{ scope: "/apps/app-builder/" }})
                    .then(function(reg) {{
                        pwaLog("✅ SW registrado: " + reg.scope);
                    }})
                    .catch(function(err) {{
                        pwaLog("❌ SW erro: " + err.message);
                    }});
            }}

            window.OneSignalDeferred = window.OneSignalDeferred || [];
            window.OneSignalDeferred.push(async function(OneSignal) {{
                try {{
                    pwaLog('OneSignal callback disparado');
                    window.OneSignal = OneSignal;
                    await OneSignal.init({{
                        appId: appId,
                        serviceWorkerPath: '/apps/app-builder/service-worker.js',
                        serviceWorkerParam: {{ scope: '/apps/app-builder/' }},
                    }});
                    pwaLog('✅ OneSignal.init() concluído — appId: ' + appId.substring(0,8) + '...');

                    var nativePerm = typeof Notification !== 'undefined' ? Notification.permission : 'indisponivel';
                    pwaLog('Notification.permission: ' + nativePerm);
                    try {{
                        var optedIn = OneSignal.User.PushSubscription.optedIn;
                        var subId = OneSignal.User.PushSubscription.id;
                        pwaLog('optedIn: ' + optedIn);
                        pwaLog('subscription id: ' + (subId || 'null'));
                    }} catch(e) {{ pwaLog('Erro ao ler sub: ' + e.message); }}

                    initNotificationBar();
                }} catch(err) {{
                    pwaLog('❌ Erro no OneSignal.init(): ' + err.message);
                }}
            }});

            if (!document.querySelector('script[src*="OneSignalSDK.page.js"]')) {{
                var sdkScript = document.createElement('script');
                sdkScript.src = 'https://cdn.onesignal.com/sdks/web/v16/OneSignalSDK.page.js';
                sdkScript.onload = function() {{ pwaLog('✅ SDK carregado (onload)'); }};
                sdkScript.onerror = function() {{ pwaLog('❌ ERRO ao carregar SDK'); }};
                document.head.appendChild(sdkScript);
                pwaLog('SDK OneSignal injetado');
            }}
        }}

        function showInstallHelpModal() {{
            var existing = document.getElementById('pwa-install-modal');
            if (existing) existing.remove();
            var ua = navigator.userAgent || "";
            var isSamsung = ua.toLowerCase().indexOf('samsungbrowser') !== -1;
            var isSafari = ua.includes('Safari') && !ua.includes('Chrome');
            var steps = isSamsung
                ? "1. Toque no menu (⋮).\\n2. Escolha Adicionar à Tela inicial.\\n3. Confirme e toque em Adicionar."
                : isSafari
                ? "1. Toque no ícone de compartilhar.\\n2. Selecione Adicionar à Tela de Início.\\n3. Confirme e toque em Adicionar."
                : "1. Abra o menu do navegador.\\n2. Toque em Instalar app ou Adicionar à Tela inicial.\\n3. Confirme para instalar.";
            var modal = document.createElement('div');
            modal.id = 'pwa-install-modal';
            modal.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,0.55);z-index:2147483648;display:flex;align-items:center;justify-content:center;";
            var box = document.createElement('div');
            box.style.cssText = "background:#fff;max-width:90%;border-radius:12px;padding:20px;font-family:sans-serif;color:#222;box-shadow:0 8px 30px rgba(0,0,0,0.25);";
            box.innerHTML = "<div style='font-size:18px;font-weight:bold;margin-bottom:8px;'>Instalar aplicativo</div>" +
                            "<div style='font-size:14px;line-height:1.5;margin-bottom:12px;'>Siga os passos para instalar na tela inicial:</div>" +
                            "<pre style='white-space:pre-wrap;font-size:13px;background:#f5f5f5;padding:10px;border-radius:8px;'>" + steps + "</pre>" +
                            "<button id='pwa-install-modal-close' style='margin-top:14px;width:100%;padding:10px 0;border:none;border-radius:8px;background:{color};color:#fff;font-weight:bold;font-size:14px;cursor:pointer;'>Entendi</button>";
            modal.appendChild(box);
            document.body.appendChild(modal);
            document.getElementById('pwa-install-modal-close').onclick = function() {{ modal.remove(); }};
        }}

        function initVariantTracking() {{
            try {{
                if (window.LS && typeof LS.registerOnChangeVariant === 'function') {{
                    LS.registerOnChangeVariant(function(variant) {{
                        try {{
                            var productId = null, productName = null;
                            try {{ if (LS.product) {{ productId = LS.product.id||null; productName = LS.product.name||null; }} }} catch(e) {{}}
                            var payload = {{ store_id:'{store_id}', visitor_id:visitorId, product_id:productId?String(productId):'', variant_id:variant&&variant.id?String(variant.id):'', variant_name:variant&&variant.name?String(variant.name):productName||null, price:variant&&typeof variant.price!=='undefined'?String(variant.price):null, stock:variant&&typeof variant.stock!=='undefined'?variant.stock:null }};
                            if (!payload.variant_id) return;
                            fetch('{final_backend_url}/analytics/variant', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify(payload) }});
                        }} catch(err) {{}}
                    }});
                }}
            }} catch(e) {{}}
        }}

        function initSalesTracking() {{
            try {{
                if (window.location.href.includes('/checkout/success') || window.location.href.includes('/order-received')) {{
                    var val = '0.00';
                    if (window.dataLayer) {{
                        for (var i = 0; i < window.dataLayer.length; i++) {{
                            if (window.dataLayer[i].transactionTotal) {{ val = window.dataLayer[i].transactionTotal; break; }}
                            if (window.dataLayer[i].value) {{ val = window.dataLayer[i].value; break; }}
                        }}
                    }}
                    var oid = window.location.href.split('/').pop();
                    if (!localStorage.getItem('venda_' + oid) && parseFloat(val) > 0) {{
                        fetch('{final_backend_url}/analytics/venda', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{store_id:'{store_id}',valor:val.toString(),visitor_id:visitorId}}) }});
                        localStorage.setItem('venda_' + oid, 'true');
                    }}
                }}
            }} catch(e) {{}}
        }}

        try {{
            initMeta();
            initInstallCapture();
            initAnalytics();
            initOneSignalInApp();
        }} catch(e) {{
            pwaLog('❌ Erro crítico: ' + e.message);
        }}

        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', function() {{
                try {{ {bottom_bar_script} if (typeof initBottomBar === 'function') initBottomBar(); }} catch(e) {{}}
            }});
        }} else {{
            try {{ {bottom_bar_script} if (typeof initBottomBar === 'function') initBottomBar(); }} catch(e) {{}}
        }}

        setTimeout(function() {{
            try {{
                {fab_script}
                {topbar_script}
                {popup_script}
                if (typeof initFab === 'function') initFab();
                if (typeof initTopbarWidget === 'function') initTopbarWidget();
                if (typeof initInstallPopup === 'function') initInstallPopup();
                initVariantTracking();
                initSalesTracking();
            }} catch(e) {{}}
        }}, 800);

    }})();
    """

    return Response(content=js, media_type="application/javascript")
