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
    """Busca appId e apiKey do OneSignal para a loja."""
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
    """
    Envia push para todos os subscribers da loja via API REST do OneSignal.
    Docs: https://documentation.onesignal.com/reference/create-notification
    """
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
        raise HTTPException(
            status_code=400,
            detail="OneSignal não configurado para esta loja. Configure o App ID e API Key no painel.",
        )

    result = await send_onesignal_push(
        app_id=app_id,
        api_key=api_key,
        title=payload.title,
        message=payload.message,
        url=payload.url,
        icon=payload.icon,
    )

    # Salva histórico
    sent_count = result.get("recipients", 0)
    error = result.get("errors")

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

    if error:
        return {
            "status": "error",
            "detail": error,
            "onesignal_response": result,
        }

    return {
        "status": "success",
        "sent": sent_count,
        "notification_id": result.get("id"),
    }


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


@router.get("/subscribers/count")
async def get_subscribers_count(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Retorna contagem de subscribers ativos via API do OneSignal."""
    app_id, api_key = get_onesignal_credentials(store_id, db)

    if not app_id or not api_key:
        raise HTTPException(
            status_code=400,
            detail="OneSignal não configurado para esta loja.",
        )

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            f"https://onesignal.com/api/v1/apps/{app_id}",
            headers={"Authorization": f"Basic {api_key}"},
        )
        data = response.json()

    return {
        "subscribers": data.get("players", 0),
        "active_subscribers": data.get("messageable_players", 0),
        "app_id": app_id,
    }
