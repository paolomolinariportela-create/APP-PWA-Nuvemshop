import os
import json
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from pywebpush import webpush, WebPushException

# --- IMPORTS INTERNOS ---
from app.database import get_db
from app.models import VendaApp, VisitaApp, PushSubscription, AppConfig, PushHistory, Loja
from app.auth import get_current_store

router = APIRouter(prefix="/stats", tags=["Stats"])

# --- CONFIGURAÇÃO PUSH (VAPID) BLINDADA ---
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")

# Carregamento seguro do JSON
raw_claims = os.getenv("VAPID_CLAIMS", '{"sub": "mailto:admin@seuapp.com"}')
try:
    VAPID_CLAIMS = json.loads(raw_claims)
except:
    VAPID_CLAIMS = {"sub": "mailto:admin@seuapp.com"}

# URL Backend
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"

# --- MODELOS DE ENTRADA ---
class VendaPayload(BaseModel):
    store_id: str
    valor: str
    visitor_id: str

class VisitaPayload(BaseModel):
    store_id: str
    pagina: str
    is_pwa: bool
    visitor_id: str

class PushSubscribePayload(BaseModel):
    store_id: str
    subscription: Dict[str, Any]
    visitor_id: Optional[str] = None

class PushSendPayload(BaseModel):
    title: str
    message: str
    url: Optional[str] = "/"
    icon: Optional[str] = "/icon.png"

# --- FUNÇÕES AUXILIARES DE PUSH ---
def send_webpush(subscription_info, message_body):
    """Envia uma notificação unitária via pywebpush"""
    try:
        if not VAPID_PRIVATE_KEY: return False
        
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(message_body),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS
        )
        return True
    except WebPushException as ex:
        # 410 = Gone (Usuário cancelou ou desinstalou)
        if ex.response and ex.response.status_code == 410:
            return "DELETE"
        print(f"Erro Push: {ex}")
        return False

# --- ROTA LOADER.JS (O CÉREBRO DO FRONTEND) ---
@router.get("/loader.js", include_in_schema=False)
def get_loader(store_id: str, db: Session = Depends(get_db)):
    # 1. Busca Configurações da Loja
    try: config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    except: config = None
    
    color = config.theme_color if config else "#000000"
    fab_enabled = config.fab_enabled if config else False
    fab_text = config.fab_text if config else "Baixar App"

    # 2. Prepara Script do Botão Flutuante (FAB)
    fab_script = ""
    if fab_enabled:
        fab_script = f"""
        if (window.innerWidth < 900 && !isApp) {{
            var fab = document.createElement('div');
            fab.id = 'pwa-fab-btn';
            fab.style.cssText = "position:fixed; bottom:20px; right:20px; background:{color}; color:white; padding:12px 24px; border-radius:50px; box-shadow:0 4px 15px rgba(0,0,0,0.3); z-index:999999; font-family:sans-serif; font-weight:bold; font-size:14px; display:flex; align-items:center; gap:8px; cursor:pointer; transition: transform 0.2s;";
            fab.innerHTML = "<span style='font-size:18px'>📲</span> <span>{fab_text}</span>";
            fab.onclick = function() {{ if(window.installPWA) window.installPWA(); }};
            fab.animate([{{ transform: 'translateY(100px)', opacity: 0 }}, {{ transform: 'translateY(0)', opacity: 1 }}], {{ duration: 500, easing: 'ease-out' }});
            document.body.appendChild(fab);
        }}
        """

    # 3. O Script Mágico Completo
    js = f"""
    (function() {{
        console.log("🚀 PWA Loader Pro v3 (Push Enabled)");
        
        var visitorId = localStorage.getItem('pwa_v_id');
        if(!visitorId) {{ visitorId = 'v_' + Math.random().toString(36).substr(2, 9); localStorage.setItem('pwa_v_id', visitorId); }}
        var isApp = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
        
        var link = document.createElement('link'); link.rel = 'manifest'; link.href = '{BACKEND_URL}/manifest/{store_id}.json'; document.head.appendChild(link);
        var meta = document.createElement('meta'); meta.name = 'theme-color'; meta.content = '{color}'; document.head.appendChild(meta);

        function trackVisit() {{
            try {{ fetch('{BACKEND_URL}/stats/visita', {{ method: 'POST', headers: {{'Content-Type': 'application/json'}}, body: JSON.stringify({{ store_id: '{store_id}', pagina: window.location.pathname, is_pwa: isApp, visitor_id: visitorId }}) }}); }} catch(e) {{}}
        }}
        trackVisit();
        
        var oldHref = document.location.href;
        new MutationObserver(function() {{ if (oldHref !== document.location.href) {{ oldHref = document.location.href; trackVisit(); }} }}).observe(document.querySelector("body"), {{ childList: true, subtree: true }});

        var deferredPrompt;
        window.addEventListener('beforeinstallprompt', (e) => {{ e.preventDefault(); deferredPrompt = e; }});
        window.installPWA = function() {{
            if (deferredPrompt) {{ deferredPrompt.prompt(); }} 
            else {{ alert("Para instalar:\\\\\\\\\\\\\\\\nAndroid: Menu > Adicionar à Tela\\\\\\\\\\\\\\\\niOS: Compartilhar > Adicionar à Tela"); }}
        }};

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
                    const registration = await navigator.serviceWorker.register('{BACKEND_URL}/service-worker.js');
                    await navigator.serviceWorker.ready;
                    const subscription = await registration.pushManager.subscribe({{
                        userVisibleOnly: true,
                        applicationServerKey: urlBase64ToUint8Array(publicVapidKey)
                    }});
                    await fetch('{BACKEND_URL}/stats/push/subscribe', {{
                        method: 'POST',
                        body: JSON.stringify({{ subscription: subscription, store_id: '{store_id}', visitor_id: visitorId }}),
                        headers: {{ 'Content-Type': 'application/json' }}
                    }});
                    console.log("✅ Push Inscrito!");
                }} catch (err) {{ console.log("Push info:", err); }}
            }}
        }}

        if (isApp) {{ subscribePush(); }}
        {fab_script}

        if (window.location.href.includes('/checkout/success') && isApp) {{
            var val = "0.00";
            if (window.dataLayer) {{ for(var i=0; i<window.dataLayer.length; i++) {{ if(window.dataLayer[i].transactionTotal) {{ val = window.dataLayer[i].transactionTotal; break; }} }} }}
            var oid = window.location.href.split('/').pop();
            if (!localStorage.getItem('venda_'+oid) && parseFloat(val) > 0) {{
                fetch('{BACKEND_URL}/stats/venda', {{ method:'POST', headers:{{'Content-Type':'application/json'}}, body:JSON.stringify({{ store_id:'{store_id}', valor:val.toString(), visitor_id: visitorId }}) }});
                localStorage.setItem('venda_'+oid, 'true');
            }}
        }}
    }})();
    """
    return Response(content=js, media_type="application/javascript")


# --- ROTAS DE REGISTRO (Analytics) ---

@router.post("/visita")
def registrar_visita(payload: VisitaPayload, db: Session = Depends(get_db)):
    db.add(VisitaApp(store_id=payload.store_id, pagina=payload.pagina, is_pwa=payload.is_pwa, visitor_id=payload.visitor_id, data=datetime.now().isoformat()))
    db.commit()
    return {"status": "ok"}

@router.post("/venda")
def registrar_venda(payload: VendaPayload, db: Session = Depends(get_db)):
    db.add(VendaApp(store_id=payload.store_id, valor=payload.valor, visitor_id=payload.visitor_id, data=datetime.now().isoformat()))
    db.commit()
    return {"status": "ok"}

# --- ROTAS DE PUSH (Subscribe & Send & History) ---

@router.post("/push/subscribe")
def subscribe_push(payload: PushSubscribePayload, db: Session = Depends(get_db)):
    try:
        sub_data = payload.subscription
        endpoint = sub_data.get("endpoint")
        keys = sub_data.get("keys", {})
        
        if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
            return {"status": "error", "message": "Dados inválidos"}

        exists = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
        if not exists:
            db.add(PushSubscription(
                store_id=payload.store_id,
                visitor_id=payload.visitor_id,
                endpoint=endpoint,
                p256dh=keys.get("p256dh"),
                auth=keys.get("auth"),
                created_at=datetime.now().isoformat()
            ))
            db.commit()
            return {"status": "subscribed"}
        
        return {"status": "already_subscribed"}
    except Exception as e:
        print(f"Erro Subscribe: {e}")
        return {"status": "error"}

# ROTA NOVA: LISTAR HISTÓRICO DE CAMPANHAS
@router.get("/admin/push-history")
def get_push_history(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    """Retorna o histórico de campanhas enviadas"""
    history = db.query(PushHistory).filter(PushHistory.store_id == store_id).order_by(PushHistory.id.desc()).all()
    return history

@router.post("/admin/send-push")
def send_push_campaign(payload: PushSendPayload, store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    """Envia notificação para todos e salva no histórico"""
    subs = db.query(PushSubscription).filter(PushSubscription.store_id == store_id).all()
    
    # Prepara a mensagem
    message_body = { "title": payload.title, "body": payload.message, "url": payload.url, "icon": payload.icon }
    sent_count = 0; delete_ids = []

    # Envia para cada inscrito
    if subs:
        for sub in subs:
            res = send_webpush({"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}}, message_body)
            if res == True: sent_count += 1
            elif res == "DELETE": delete_ids.append(sub.id)

        if delete_ids:
            db.query(PushSubscription).filter(PushSubscription.id.in_(delete_ids)).delete(synchronize_session=False)
            db.commit()

    # --- SALVA NO HISTÓRICO (NOVO!) ---
    history_item = PushHistory(
        store_id=store_id,
        title=payload.title,
        message=payload.message,
        url=payload.url,
        sent_count=sent_count, # Salva quantos receberam de verdade
        created_at=datetime.now().isoformat()
    )
    db.add(history_item)
    db.commit()

    return {"status": "success", "sent": sent_count, "cleaned": len(delete_ids)}

# --- O DASHBOARD INTELIGENTE ---
@router.get("/dashboard")
def get_dashboard_stats(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum([float(v.valor) for v in vendas])
    qtd_vendas = len(vendas)
    visitantes_unicos = db.query(func.count(distinct(VisitaApp.visitor_id))).filter(VisitaApp.store_id == store_id).scalar() or 0
    qtd_checkout = db.query(func.count(distinct(VisitaApp.visitor_id))).filter(VisitaApp.store_id == store_id, (VisitaApp.pagina.contains("checkout") | VisitaApp.pagina.contains("carrinho"))).scalar() or 0
    abandonos = max(0, qtd_checkout - qtd_vendas)
    ticket_medio = total_receita / max(1, qtd_vendas) if qtd_vendas > 0 else 0
    subquery = db.query(VendaApp.visitor_id).filter(VendaApp.store_id == store_id).group_by(VendaApp.visitor_id).having(func.count(VendaApp.id) > 1).subquery()
    recorrentes = db.query(func.count(subquery.c.visitor_id)).scalar() or 0
    pageviews = db.query(VisitaApp).filter(VisitaApp.store_id == store_id).count()
    top_paginas = [p[0] for p in db.query(VisitaApp.pagina, func.count(VisitaApp.pagina).label('total')).filter(VisitaApp.store_id == store_id).group_by(VisitaApp.pagina).order_by(desc('total')).limit(5).all()]

    return {
        "receita": total_receita,
        "vendas": qtd_vendas,
        "instalacoes": visitantes_unicos,
        "carrinhos_abandonados": { "valor": abandonos * ticket_medio, "qtd": abandonos },
        "visualizacoes": { "pageviews": pageviews, "tempo_medio": "--", "top_paginas": top_paginas },
        "funil": { "visitas": visitantes_unicos, "carrinho": qtd_checkout, "checkout": qtd_vendas },
        "recorrencia": { "clientes_2x": recorrentes, "taxa_recompra": round((recorrentes / max(1, qtd_vendas) * 100), 1) },
        "ticket_medio": { "app": round(ticket_medio, 2), "site": 0.0 },
        "taxa_conversao": { "app": round((qtd_vendas / max(1, visitantes_unicos) * 100), 1), "site": 0.0 },
        "economia_ads": visitantes_unicos * 0.50
    }
