import os
import json
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from pywebpush import webpush, WebPushException

from app.database import get_db
from app.models import PushSubscription, PushHistory, Loja
from app.auth import get_current_store
# from app.security import validate_proxy_hmac  # não usado aqui

router = APIRouter(prefix="/push", tags=["Push"])

# CONFIGURAÇÃO VAPID
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
raw_claims = os.getenv("VAPID_CLAIMS", '{"sub": "mailto:admin@seuapp.com"}')
try:
    VAPID_CLAIMS = json.loads(raw_claims)
except:
    VAPID_CLAIMS = {"sub": "mailto:admin@seuapp.com"}


class PushSubscribePayload(BaseModel):
    store_id: str
    subscription: Dict[str, Any]
    visitor_id: Optional[str] = None


class PushSendPayload(BaseModel):
    title: str
    message: str
    url: Optional[str] = "/"
    icon: Optional[str] = "/icon.png"


def send_webpush(subscription_info, message_body):
    try:
        if not VAPID_PRIVATE_KEY:
            return False
        webpush(
            subscription_info=subscription_info,
            data=json.dumps(message_body),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
        return True
    except WebPushException as ex:
        if ex.response and ex.response.status_code == 410:
            return "DELETE"
        return False


@router.post("/subscribe")
async def subscribe_push(
    payload: PushSubscribePayload,
    request: Request,
    db: Session = Depends(get_db),
):
    try:
        sub_data = payload.subscription
        endpoint = sub_data.get("endpoint")
        keys = sub_data.get("keys", {})
        if not endpoint or not keys.get("p256dh") or not keys.get("auth"):
            return {"status": "error"}

        exists = (
            db.query(PushSubscription)
            .filter(PushSubscription.endpoint == endpoint)
            .first()
        )
        if not exists:
            db.add(
                PushSubscription(
                    store_id=payload.store_id,
                    visitor_id=payload.visitor_id,
                    endpoint=endpoint,
                    p256dh=keys.get("p256dh"),
                    auth=keys.get("auth"),
                    created_at=datetime.now().isoformat(),
                )
            )
            db.commit()
            return {"status": "subscribed"}
        return {"status": "already_subscribed"}
    except Exception:
        return {"status": "error"}


@router.post("/send")
def send_push_campaign(
    payload: PushSendPayload,
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    subs = (
        db.query(PushSubscription)
        .filter(PushSubscription.store_id == store_id)
        .all()
    )
    message_body = {
        "title": payload.title,
        "body": payload.message,
        "url": payload.url,
        "icon": payload.icon,
    }
    sent_count = 0
    delete_ids = []

    if subs:
        for sub in subs:
            res = send_webpush(
                {
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                message_body,
            )
            if res is True:
                sent_count += 1
            elif res == "DELETE":
                delete_ids.append(sub.id)
        if delete_ids:
            db.query(PushSubscription).filter(
                PushSubscription.id.in_(delete_ids)
            ).delete(synchronize_session=False)
            db.commit()

    db.add(
        PushHistory(
            store_id=store_id,
            title=payload.title,
            message=payload.message,
            url=payload.url,
            sent_count=sent_count,
            created_at=datetime.now().isoformat(),
        )
    )
    db.commit()
    return {"status": "success", "sent": sent_count, "cleaned": len(delete_ids)}


@router.get("/history")
def get_push_history(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    return (
        db.query(PushHistory)
        .filter(PushHistory.store_id == store_id)
        .order_by(PushHistory.id.desc())
        .all()
    )
