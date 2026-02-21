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
    fab_size: Optional[float] = 1.0  # slider 0.7–1.5 no front

    # Barra / banner (top/bottom)
    topbar_enabled: Optional[bool] = False
    topbar_text: Optional[str] = "Baixe nosso app"
    topbar_button_text: Optional[str] = "Baixar"
    topbar_icon: Optional[str] = "📲"
    topbar_position: Optional[str] = "bottom"
    topbar_color: Optional[str] = "#111827"
    topbar_text_color: Optional[str] = "#FFFFFF"
    topbar_size: Optional[float] = 1.0  # slider 0.8–1.4 no front

    # Bottom bar
    bottom_bar_bg: Optional[str] = "#FFFFFF"
    bottom_bar_icon_color: Optional[str] = "#6B7280"


def _map_slider_to_size(value: float | None) -> str:
    """
    Converte o valor do slider (0.7–1.5) em small / medium / large.
    """
    if value is None:
        return "medium"
    if value <= 0.9:
        return "small"
    if value >= 1.3:
        return "large"
    return "medium"


@router.get("/config")
def get_config(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        # Retorna padrão se não existir
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
            "fab_size": 1.0,  # medium
            "topbar_enabled": False,
            "topbar_text": "Baixe nosso app",
            "topbar_button_text": "Baixar",
            "topbar_icon": "📲",
            "topbar_position": "bottom",
            "topbar_color": "#111827",
            "topbar_text_color": "#FFFFFF",
            "topbar_size": 1.0,  # medium
            "bottom_bar_bg": "#FFFFFF",
            "bottom_bar_icon_color": "#6B7280",
        }

    # Converte o small/medium/large salvo em slider numérico pro front
    def _size_to_slider(size: str | None) -> float:
        if size == "small":
            return 0.8
        if size == "large":
            return 1.3
        return 1.0  # medium / default

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
        "fab_size": _size_to_slider(getattr(config, "fab_size", "medium")),
        "topbar_enabled": getattr(config, "topbar_enabled", False),
        "topbar_text": getattr(config, "topbar_text", "Baixe nosso app") or "Baixe nosso app",
        "topbar_button_text": getattr(config, "topbar_button_text", "Baixar") or "Baixar",
        "topbar_icon": getattr(config, "topbar_icon", "📲") or "📲",
        "topbar_position": getattr(config, "topbar_position", "bottom") or "bottom",
        "topbar_color": getattr(config, "topbar_color", "#111827") or "#111827",
        "topbar_text_color": getattr(config, "topbar_text_color", "#FFFFFF") or "#FFFFFF",
        "topbar_size": _size_to_slider(getattr(config, "topbar_size", "medium")),
        "bottom_bar_bg": getattr(config, "bottom_bar_bg", "#FFFFFF") or "#FFFFFF",
        "bottom_bar_icon_color": getattr(
            config, "bottom_bar_icon_color", "#6B7280"
        ) or "#6B7280",
    }


@router.get("/store-info")
def get_store_info(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja:
        return {"url": "", "logo_url": ""}

    # se ainda não temos logo salva, tenta sincronizar uma vez com a Nuvemshop
    if not loja.logo_url:
        print("[STORE-INFO] logo_url vazia, buscando na Nuvemshop...")
        sync_store_logo_from_nuvemshop(db, loja)
        print("[STORE-INFO] Depois do sync, logo_url:", loja.logo_url)

    store_url = loja.url or ""
    logo_url = getattr(loja, "logo_url", None)

    return {
        "url": store_url,
        "logo_url": logo_url or "",
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

    # Widgets FAB
    config.fab_enabled = payload.fab_enabled
    config.fab_text = payload.fab_text
    config.fab_position = payload.fab_position
    config.fab_icon = payload.fab_icon
    config.fab_delay = payload.fab_delay
    config.fab_color = payload.fab_color
    config.fab_size = _map_slider_to_size(payload.fab_size)

    # Topbar / banner
    config.topbar_enabled = payload.topbar_enabled
    config.topbar_text = payload.topbar_text
    config.topbar_button_text = payload.topbar_button_text
    config.topbar_icon = payload.topbar_icon
    config.topbar_position = payload.topbar_position
    config.topbar_color = payload.topbar_color
    config.topbar_text_color = payload.topbar_text_color
    config.topbar_size = _map_slider_to_size(payload.topbar_size)

    # Bottom bar
    config.bottom_bar_bg = payload.bottom_bar_bg
    config.bottom_bar_icon_color = payload.bottom_bar_icon_color

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
