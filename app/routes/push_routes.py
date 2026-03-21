import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import PushHistory, AppConfig
from app.auth import get_current_store

router = APIRouter(prefix="/push", tags=["Push"])


class PushSendPayload(BaseModel):
    title: str
    message: str
    url: Optional[str] = "/"
    icon: Optional[str] = None


def get_onesignal_credentials(store_id: str, db: Session):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return None, None
    return (
        getattr(config, "onesignal_app_id", None),
        getattr(config, "onesignal_api_key", None),
    )


async def send_onesignal_push(
    app_id: str,
    api_key: str,
    title: str,
    message: str,
    url: str,
    icon: Optional[str] = None,
) -> dict:
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "app_id": app_id,
        "included_segments": ["Total Subscriptions"],
        "headings": {"en": title, "pt": title},
        "contents": {"en": message, "pt": message},
        "url": url,
    }
    if icon:
        payload["chrome_web_icon"] = icon
        payload["firefox_icon"] = icon

    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            "https://onesignal.com/api/v1/notifications",
            headers=headers,
            json=payload,
        )
        return response.json()


@router.post("/send")
async def send_push_campaign(
    payload: PushSendPayload,
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    app_id, api_key = get_onesignal_credentials(store_id, db)
    if not app_id or not api_key:
        raise HTTPException(status_code=400, detail="OneSignal não configurado para esta loja.")

    result = await send_onesignal_push(
        app_id=app_id,
        api_key=api_key,
        title=payload.title,
        message=payload.message,
        url=payload.url,
        icon=payload.icon,
    )

    sent_count = result.get("recipients", 0)
    error = result.get("errors")

    db.add(PushHistory(
        store_id=store_id,
        title=payload.title,
        message=payload.message,
        url=payload.url,
        sent_count=sent_count,
        created_at=datetime.now().isoformat(),
    ))
    db.commit()

    if error:
        return {"status": "error", "detail": error, "onesignal_response": result}

    return {"status": "success", "sent": sent_count, "notification_id": result.get("id")}


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


@router.get("/stats")
async def get_push_stats(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Retorna stats completos do OneSignal para a loja:
    - Total de subscribers ativos
    - Histórico de notificações com taxa de abertura e clique
    """
    app_id, api_key = get_onesignal_credentials(store_id, db)
    if not app_id or not api_key:
        return {
            "subscribers": 0,
            "active_subscribers": 0,
            "notifications": [],
            "taxa_optin": 0,
        }

    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        # Dados do app (subscribers)
        app_resp = await client.get(
            f"https://onesignal.com/api/v1/apps/{app_id}",
            headers={"Authorization": f"Basic {api_key}"},
        )
        app_data = app_resp.json()

        # Histórico de notificações com métricas
        notif_resp = await client.get(
            f"https://onesignal.com/api/v1/notifications",
            headers=headers,
            params={"app_id": app_id, "limit": 20, "offset": 0},
        )
        notif_data = notif_resp.json()

    subscribers = app_data.get("players", 0)
    active_subscribers = app_data.get("messageable_players", 0)

    notifications = []
    for n in notif_data.get("notifications", []):
        successful = n.get("successful", 0) or 0
        opened = n.get("converted", 0) or 0
        clicked = n.get("clicked", 0) or 0
        taxa_abertura = round((opened / successful * 100), 1) if successful > 0 else 0

        # Pega o texto da notificação
        contents = n.get("contents", {})
        headings = n.get("headings", {})
        title = headings.get("pt") or headings.get("en") or ""
        message = contents.get("pt") or contents.get("en") or ""

        notifications.append({
            "id": n.get("id"),
            "title": title,
            "message": message,
            "url": n.get("url", "/"),
            "sent": successful,
            "opened": opened,
            "clicked": clicked,
            "taxa_abertura": taxa_abertura,
            "created_at": n.get("queued_at", 0),
        })

    # Taxa de opt-in = subscribers / instalações do banco
    from app.models import VisitaApp
    from sqlalchemy import func, distinct
    instalacoes = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.pagina == "install",
        )
        .scalar() or 0
    )
    taxa_optin = round((active_subscribers / instalacoes * 100), 1) if instalacoes > 0 else 0

    return {
        "subscribers": subscribers,
        "active_subscribers": active_subscribers,
        "instalacoes": instalacoes,
        "taxa_optin": taxa_optin,
        "notifications": notifications,
    }
