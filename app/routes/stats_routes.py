import os
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from pywebpush import webpush, WebPushException

# Importando do nível superior
from ..database import get_db
from ..models import VendaApp, VisitaApp, PushSubscription
from ..auth import get_current_store

router = APIRouter(prefix="/stats", tags=["Stats"])

# --- CONFIGURAÇÃO PUSH (VAPID) ---
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY")
# Se não tiver claims no env, usa um padrão seguro
VAPID_CLAIMS = os.getenv("VAPID_CLAIMS")
if isinstance(VAPID_CLAIMS, str):
    try:
        VAPID_CLAIMS = json.loads(VAPID_CLAIMS)
    except:
        VAPID_CLAIMS = {"sub": "mailto:admin@seuapp.com"}
else:
    VAPID_CLAIMS = {"sub": "mailto:admin@seuapp.com"}

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

# Modelo para Inscrição no Push
class PushSubscribePayload(BaseModel):
    store_id: str
    subscription: Dict[str, Any] # Objeto JSON que o navegador manda
    visitor_id: Optional[str] = None

# Modelo para Envio de Push (Admin)
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

# --- ROTAS DE REGISTRO (Ouvidos do Sistema) ---

@router.post("/visita")
def registrar_visita(payload: VisitaPayload, db: Session = Depends(get_db)):
    db.add(VisitaApp(
        store_id=payload.store_id, 
        pagina=payload.pagina, 
        is_pwa=payload.is_pwa,
        visitor_id=payload.visitor_id,
        data=datetime.now().isoformat()
    ))
    db.commit()
    return {"status": "ok"}

@router.post("/venda")
def registrar_venda(payload: VendaPayload, db: Session = Depends(get_db)):
    db.add(VendaApp(
        store_id=payload.store_id, 
        valor=payload.valor, 
        visitor_id=payload.visitor_id,
        data=datetime.now().isoformat()
    ))
    db.commit()
    return {"status": "ok"}

# --- ROTAS DE PUSH NOTIFICATIONS ---

@router.post("/push/subscribe")
def subscribe_push(payload: PushSubscribePayload, db: Session = Depends(get_db)):
    """Salva o token do usuário para receber notificações"""
    try:
        sub_data = payload.subscription
        endpoint = sub_data.get("endpoint")
        keys = sub_data.get("keys", {})
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")

        if not endpoint or not p256dh or not auth:
            return {"status": "error", "message": "Dados inválidos"}

        # Verifica se já existe
        exists = db.query(PushSubscription).filter(PushSubscription.endpoint == endpoint).first()
        if not exists:
            new_sub = PushSubscription(
                store_id=payload.store_id,
                visitor_id=payload.visitor_id,
                endpoint=endpoint,
                p256dh=p256dh,
                auth=auth,
                created_at=datetime.now().isoformat()
            )
            db.add(new_sub)
            db.commit()
            return {"status": "subscribed"}
        
        return {"status": "already_subscribed"}
    except Exception as e:
        print(f"Erro Subscribe: {e}")
        return {"status": "error"}

@router.post("/admin/send-push")
def send_push_campaign(payload: PushSendPayload, store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    """Rota protegida para o Lojista enviar notificações"""
    
    # Busca todos os inscritos desta loja
    subs = db.query(PushSubscription).filter(PushSubscription.store_id == store_id).all()
    
    if not subs:
        return {"status": "success", "sent": 0, "message": "Nenhum inscrito ainda."}

    message_body = {
        "title": payload.title,
        "body": payload.message,
        "url": payload.url,
        "icon": payload.icon
    }

    sent_count = 0
    delete_ids = []

    for sub in subs:
        subscription_info = {
            "endpoint": sub.endpoint,
            "keys": {
                "p256dh": sub.p256dh,
                "auth": sub.auth
            }
        }
        
        result = send_webpush(subscription_info, message_body)
        
        if result == True:
            sent_count += 1
        elif result == "DELETE":
            delete_ids.append(sub.id)

    # Limpeza de inscritos inativos
    if delete_ids:
        db.query(PushSubscription).filter(PushSubscription.id.in_(delete_ids)).delete(synchronize_session=False)
        db.commit()

    return {"status": "success", "sent": sent_count, "cleaned": len(delete_ids)}


# --- O DASHBOARD INTELIGENTE (Mantido Igual) ---
@router.get("/dashboard")
def get_dashboard_stats(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    # 1. Vendas e Receita
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum([float(v.valor) for v in vendas])
    qtd_vendas = len(vendas)

    # 2. Visitantes Únicos (Base para cálculos)
    visitantes_unicos = db.query(func.count(distinct(VisitaApp.visitor_id))).filter(VisitaApp.store_id == store_id).scalar() or 0
    
    # 3. Funil (Quem chegou no checkout/carrinho)
    qtd_checkout = db.query(func.count(distinct(VisitaApp.visitor_id))).filter(
        VisitaApp.store_id == store_id, 
        (VisitaApp.pagina.contains("checkout") | VisitaApp.pagina.contains("carrinho") | VisitaApp.pagina.contains("cart"))
    ).scalar() or 0

    # 4. Carrinhos Abandonados
    abandonos = max(0, qtd_checkout - qtd_vendas)
    ticket_medio_app = total_receita / max(1, qtd_vendas) if qtd_vendas > 0 else 0
    valor_perdido = abandonos * ticket_medio_app

    # 5. Recorrência
    subquery = db.query(VendaApp.visitor_id).filter(VendaApp.store_id == store_id)\
                 .group_by(VendaApp.visitor_id).having(func.count(VendaApp.id) > 1).subquery()
    recorrentes = db.query(func.count(subquery.c.visitor_id)).scalar() or 0

    # 6. Pageviews Totais
    pageviews = db.query(VisitaApp).filter(VisitaApp.store_id == store_id).count()

    # 7. Top Páginas
    top_paginas_query = db.query(VisitaApp.pagina, func.count(VisitaApp.pagina).label('total'))\
        .filter(VisitaApp.store_id == store_id)\
        .group_by(VisitaApp.pagina)\
        .order_by(desc('total'))\
        .limit(5).all()
    
    top_paginas_list = [p[0] for p in top_paginas_query]

    # 8. Taxas Calculadas
    taxa_conversao_app = round((qtd_vendas / max(1, visitantes_unicos) * 100), 1)
    taxa_recompra = round((recorrentes / max(1, qtd_vendas) * 100), 1)

    return {
        "receita": total_receita,
        "vendas": qtd_vendas,
        "instalacoes": visitantes_unicos,
        "carrinhos_abandonados": { "valor": valor_perdido, "qtd": abandonos },
        "visualizacoes": { 
            "pageviews": pageviews, 
            "tempo_medio": "Calculando...", 
            "top_paginas": top_paginas_list 
        },
        "funil": { 
            "visitas": visitantes_unicos, 
            "carrinho": qtd_checkout, 
            "checkout": qtd_vendas 
        },
        "recorrencia": { 
            "clientes_2x": recorrentes, 
            "taxa_recompra": taxa_recompra 
        },
        "ticket_medio": { 
            "app": round(ticket_medio_app, 2), 
            "site": 0.0 
        },
        "taxa_conversao": { 
            "app": taxa_conversao_app, 
            "site": 0.0 
        },
        "economia_ads": visitantes_unicos * 0.50
    }
