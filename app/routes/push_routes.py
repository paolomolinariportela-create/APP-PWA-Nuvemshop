import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from collections import Counter

from app.database import get_db
from app.models import PushHistory, AppConfig
from app.auth import get_current_store

router = APIRouter(prefix="/push", tags=["Push"])


class PushSendPayload(BaseModel):
    title: str
    message: str
    url: Optional[str] = "/"
    icon: Optional[str] = None
    # ✅ Segmentação
    segment: Optional[str] = "Total Subscriptions"  # segmento padrão
    filter_device: Optional[str] = None             # "Android", "iOS", "Chrome", etc
    filter_country: Optional[str] = None            # "BR", "US", etc
    send_after: Optional[str] = None                # ISO 8601: "2024-03-21T15:00:00Z"


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
    segment: str = "Total Subscriptions",
    filter_device: Optional[str] = None,
    filter_country: Optional[str] = None,
    send_after: Optional[str] = None,
) -> dict:
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "app_id": app_id,
        "headings": {"en": title, "pt": title},
        "contents": {"en": message, "pt": message},
        "url": url,
    }

    if icon:
        payload["chrome_web_icon"] = icon
        payload["firefox_icon"] = icon

    if send_after:
        payload["send_after"] = send_after

    # ✅ Segmentação por filtros
    filters = []

    if filter_device:
        device_map = {
            "Android": "5",
            "iOS": "0",
            "Chrome": "5",
            "Firefox": "8",
            "Safari": "7",
        }
        device_type = device_map.get(filter_device)
        if device_type:
            filters.append({"field": "device_type", "relation": "=", "value": device_type})

    if filter_country:
        if filters:
            filters.append({"operator": "AND"})
        filters.append({"field": "country", "relation": "=", "value": filter_country.upper()})

    if filters:
        payload["filters"] = filters
    else:
        payload["included_segments"] = [segment]

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
        segment=payload.segment or "Total Subscriptions",
        filter_device=payload.filter_device,
        filter_country=payload.filter_country,
        send_after=payload.send_after,
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

    return {
        "status": "success",
        "sent": sent_count,
        "notification_id": result.get("id"),
        "scheduled": payload.send_after is not None,
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


@router.get("/stats")
async def get_push_stats(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """
    Stats completos do OneSignal:
    - Subscribers ativos
    - Distribuição por país e dispositivo
    - Histórico de campanhas com métricas
    """
    app_id, api_key = get_onesignal_credentials(store_id, db)
    if not app_id or not api_key:
        return {
            "subscribers": 0,
            "active_subscribers": 0,
            "instalacoes": 0,
            "taxa_optin": 0,
            "por_pais": [],
            "por_dispositivo": [],
            "notifications": [],
        }

    headers = {"Authorization": f"Basic {api_key}"}

    async with httpx.AsyncClient(timeout=20.0) as client:
        # Dados gerais do app
        app_resp = await client.get(
            f"https://onesignal.com/api/v1/apps/{app_id}",
            headers=headers,
        )
        app_data = app_resp.json()

        # Histórico de campanhas
        notif_resp = await client.get(
            "https://onesignal.com/api/v1/notifications",
            headers={"Authorization": f"Basic {api_key}", "Content-Type": "application/json"},
            params={"app_id": app_id, "limit": 20, "offset": 0},
        )
        notif_data = notif_resp.json()

        # Subscribers com dados de país e dispositivo (primeiros 300)
        players_resp = await client.get(
            "https://onesignal.com/api/v1/players",
            headers={"Authorization": f"Basic {api_key}"},
            params={"app_id": app_id, "limit": 300},
        )
        players_data = players_resp.json()

    subscribers = app_data.get("players", 0)
    active_subscribers = app_data.get("messageable_players", 0)

    # ✅ Distribuição por país
    players = players_data.get("players", [])
    paises = Counter()
    dispositivos = Counter()
    device_type_map = {
        0: "iOS",
        1: "Android",
        2: "Amazon",
        3: "WindowsPhone",
        4: "Chrome Apps",
        5: "Chrome Web",
        6: "Windows",
        7: "Safari",
        8: "Firefox",
        9: "macOS",
        10: "Alexa",
        11: "Email",
        14: "SMS",
    }

    for p in players:
        country = p.get("country", "").upper()
        if country:
            paises[country] += 1
        device_type = p.get("device_type")
        device_name = device_type_map.get(device_type, "Outro")
        # Simplifica para Android/iOS/Web
        if device_name in ("iOS",):
            dispositivos["iOS"] += 1
        elif device_name in ("Android", "Amazon"):
            dispositivos["Android"] += 1
        else:
            dispositivos["Web"] += 1

    # Formata para o frontend
    total_players = len(players) or 1
    por_pais = [
        {"pais": k, "count": v, "pct": round(v / total_players * 100, 1)}
        for k, v in paises.most_common(5)
    ]
    por_dispositivo = [
        {"dispositivo": k, "count": v, "pct": round(v / total_players * 100, 1)}
        for k, v in dispositivos.most_common()
    ]

    # ✅ Histórico de campanhas com métricas completas
    notifications = []
    for n in notif_data.get("notifications", []):
        successful = n.get("successful", 0) or 0
        opened = n.get("converted", 0) or 0
        failed = n.get("failed", 0) or 0
        errored = n.get("errored", 0) or 0
        taxa_abertura = round((opened / successful * 100), 1) if successful > 0 else 0

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
            "failed": failed + errored,
            "taxa_abertura": taxa_abertura,
            "created_at": n.get("queued_at", 0),
        })

    # Taxa de opt-in
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
        "por_pais": por_pais,
        "por_dispositivo": por_dispositivo,
        "notifications": notifications,
    }
