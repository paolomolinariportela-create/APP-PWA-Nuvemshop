from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..models import Loja, AppConfig
from ..auth import get_current_store
from ..services import create_landing_page_internal, sync_store_logo_from_nuvemshop

router = APIRouter(prefix="/admin", tags=["Config"])


class ConfigPayload(BaseModel):
    app_name: str
    theme_color: str
    logo_url: Optional[str] = None
    whatsapp: Optional[str] = None

    # Widgets FAB
    fab_enabled: Optional[bool] = False
    fab_text: Optional[str] = "Baixar App"
    fab_position: Optional[str] = "right"
    fab_icon: Optional[str] = "📲"
    fab_delay: Optional[int] = 0
    fab_color: Optional[str] = "#2563EB"
    fab_size: Optional[str] = "medium"
    fab_background_image_url: Optional[str] = None

    # Barra / banner (top/bottom)
    topbar_enabled: Optional[bool] = False
    topbar_text: Optional[str] = "Baixe nosso app"
    topbar_button_text: Optional[str] = "Baixar"
    topbar_icon: Optional[str] = "📲"
    topbar_position: Optional[str] = "bottom"
    topbar_color: Optional[str] = "#111827"
    topbar_text_color: Optional[str] = "#FFFFFF"
    topbar_size: Optional[str] = "medium"
    topbar_button_bg_color: Optional[str] = "#FBBF24"
    topbar_button_text_color: Optional[str] = "#111827"
    topbar_background_image_url: Optional[str] = None

    # Popup de instalação
    popup_enabled: Optional[bool] = False
    popup_image_url: Optional[str] = None

    # Bottom bar (app instalado)
    bottom_bar_bg: Optional[str] = "#FFFFFF"
    bottom_bar_icon_color: Optional[str] = "#6B7280"

    # ✅ OneSignal — multi-tenant
    onesignal_app_id: Optional[str] = None
    onesignal_api_key: Optional[str] = None


def _normalize_fab_size(size: str | None) -> str:
    allowed = {"xs", "small", "medium", "large", "xl"}
    if not size:
        return "medium"
    s = str(size).lower()
    return s if s in allowed else "medium"


def _normalize_topbar_size(size: str | None) -> str:
    allowed = {"xs", "small", "medium", "large", "xl"}
    if not size:
        return "medium"
    s = str(size).lower()
    return s if s in allowed else "medium"


@router.get("/config")
def get_config(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return {
            "app_name": "Minha Loja",
            "theme_color": "#000000",
            "logo_url": "",
            "whatsapp": "",
            "fab_enabled": False,
            "fab_text": "Baixar App",
            "fab_position": "right",
            "fab_icon": "📲",
            "fab_delay": 0,
            "fab_color": "#2563EB",
            "fab_size": "medium",
            "fab_background_image_url": "",
            "topbar_enabled": False,
            "topbar_text": "Baixe nosso app",
            "topbar_button_text": "Baixar",
            "topbar_icon": "📲",
            "topbar_position": "bottom",
            "topbar_color": "#111827",
            "topbar_text_color": "#FFFFFF",
            "topbar_size": "medium",
            "topbar_button_bg_color": "#FBBF24",
            "topbar_button_text_color": "#111827",
            "topbar_background_image_url": "",
            "popup_enabled": False,
            "popup_image_url": "",
            "bottom_bar_bg": "#FFFFFF",
            "bottom_bar_icon_color": "#6B7280",
            "onesignal_app_id": "",
            "onesignal_api_key": "",
        }

    return {
        "app_name": config.app_name or "Minha Loja",
        "theme_color": config.theme_color or "#000000",
        "logo_url": config.logo_url or "",
        "whatsapp": config.whatsapp_number or "",
        "fab_enabled": config.fab_enabled,
        "fab_text": config.fab_text or "Baixar App",
        "fab_position": config.fab_position or "right",
        "fab_icon": config.fab_icon or "📲",
        "fab_delay": config.fab_delay or 0,
        "fab_color": getattr(config, "fab_color", "#2563EB") or "#2563EB",
        "fab_size": getattr(config, "fab_size", "medium") or "medium",
        "fab_background_image_url": getattr(config, "fab_background_image_url", "") or "",
        "topbar_enabled": getattr(config, "topbar_enabled", False),
        "topbar_text": getattr(config, "topbar_text", "Baixe nosso app") or "Baixe nosso app",
        "topbar_button_text": getattr(config, "topbar_button_text", "Baixar") or "Baixar",
        "topbar_icon": getattr(config, "topbar_icon", "📲") or "📲",
        "topbar_position": getattr(config, "topbar_position", "bottom") or "bottom",
        "topbar_color": getattr(config, "topbar_color", "#111827") or "#111827",
        "topbar_text_color": getattr(config, "topbar_text_color", "#FFFFFF") or "#FFFFFF",
        "topbar_size": getattr(config, "topbar_size", "medium") or "medium",
        "topbar_button_bg_color": getattr(config, "topbar_button_bg_color", "#FBBF24") or "#FBBF24",
        "topbar_button_text_color": getattr(config, "topbar_button_text_color", "#111827") or "#111827",
        "topbar_background_image_url": getattr(config, "topbar_background_image_url", "") or "",
        "popup_enabled": getattr(config, "popup_enabled", False),
        "popup_image_url": getattr(config, "popup_image_url", "") or "",
        "bottom_bar_bg": getattr(config, "bottom_bar_bg", "#FFFFFF") or "#FFFFFF",
        "bottom_bar_icon_color": getattr(config, "bottom_bar_icon_color", "#6B7280") or "#6B7280",
        "onesignal_app_id": getattr(config, "onesignal_app_id", "") or "",
        "onesignal_api_key": getattr(config, "onesignal_api_key", "") or "",
    }


@router.get("/store-info")
def get_store_info(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja:
        return {"url": "", "logo_url": ""}

    if not loja.logo_url:
        print("[STORE-INFO] logo_url vazia, buscando na Nuvemshop...")
        sync_store_logo_from_nuvemshop(db, loja)
        print("[STORE-INFO] Depois do sync, logo_url:", loja.logo_url)

    return {
        "url": loja.url or "",
        "logo_url": getattr(loja, "logo_url", None) or "",
    }


@router.post("/config")
def save_config(
    payload: ConfigPayload,
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        config = AppConfig(store_id=store_id)
        db.add(config)

    config.app_name = payload.app_name
    config.theme_color = payload.theme_color
    config.logo_url = payload.logo_url
    config.whatsapp_number = payload.whatsapp

    # FAB
    config.fab_enabled = payload.fab_enabled
    config.fab_text = payload.fab_text
    config.fab_position = payload.fab_position
    config.fab_icon = payload.fab_icon
    config.fab_delay = payload.fab_delay
    config.fab_color = payload.fab_color
    config.fab_size = _normalize_fab_size(payload.fab_size)
    config.fab_background_image_url = payload.fab_background_image_url

    # Topbar
    config.topbar_enabled = payload.topbar_enabled
    config.topbar_text = payload.topbar_text
    config.topbar_button_text = payload.topbar_button_text
    config.topbar_icon = payload.topbar_icon
    config.topbar_position = payload.topbar_position
    config.topbar_color = payload.topbar_color
    config.topbar_text_color = payload.topbar_text_color
    config.topbar_size = _normalize_topbar_size(payload.topbar_size)
    config.topbar_button_bg_color = payload.topbar_button_bg_color
    config.topbar_button_text_color = payload.topbar_button_text_color
    config.topbar_background_image_url = payload.topbar_background_image_url

    # Popup
    config.popup_enabled = payload.popup_enabled
    config.popup_image_url = payload.popup_image_url

    # Bottom bar
    config.bottom_bar_bg = payload.bottom_bar_bg
    config.bottom_bar_icon_color = payload.bottom_bar_icon_color

    # ✅ OneSignal
    if payload.onesignal_app_id is not None:
        config.onesignal_app_id = payload.onesignal_app_id
    if payload.onesignal_api_key is not None:
        config.onesignal_api_key = payload.onesignal_api_key

    db.commit()
    return {"status": "success"}


@router.post("/create-page")
def manual_create_page(
    payload: ConfigPayload,
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja:
        return {"error": "Loja não encontrada"}
    create_landing_page_internal(store_id, loja.access_token, payload.theme_color)
    return {"status": "success"}


# ✅ ROTA TEMPORÁRIA — salva API Key do OneSignal direto no banco
# Remove após confirmar que o token está sendo gerado corretamente
@router.get("/fix-onesignal")
def fix_onesignal(
    store_id: str,
    app_id: str,
    api_key: str,
    db: Session = Depends(get_db),
):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return {"error": "Loja não encontrada"}
    config.onesignal_app_id = app_id
    config.onesignal_api_key = api_key
    db.commit()
    return {
        "status": "ok",
        "store_id": store_id,
        "app_id": app_id,
        "api_key_preview": api_key[:20] + "...",
    }
