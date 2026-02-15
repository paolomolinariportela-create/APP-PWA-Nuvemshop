from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from ..database import get_db
from ..models import Loja, AppConfig
from ..auth import get_current_store
from ..services import create_landing_page_internal

router = APIRouter(prefix="/admin", tags=["Config"])

class ConfigPayload(BaseModel):
    app_name: str
    theme_color: str
    logo_url: Optional[str] = None
    whatsapp: Optional[str] = None
    # Novos campos opcionais para widgets
    fab_enabled: Optional[bool] = False
    fab_text: Optional[str] = "Baixar App"

@router.get("/config")
def get_config(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config: 
        # Retorna padrão se não existir
        return {
            "app_name": "Minha Loja", 
            "theme_color": "#000000", 
            "logo_url": "", 
            "whatsapp": "",
            "fab_enabled": False,
            "fab_text": "Baixar App"
        }
    return config

@router.get("/store-info")
def get_store_info(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    return {"url": loja.url if loja else ""}

@router.post("/config")
def save_config(payload: ConfigPayload, store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        config = AppConfig(store_id=store_id)
        db.add(config)
    
    config.app_name = payload.app_name
    config.theme_color = payload.theme_color
    config.logo_url = payload.logo_url
    config.whatsapp_number = payload.whatsapp
    
    # Salva Widgets
    config.fab_enabled = payload.fab_enabled
    config.fab_text = payload.fab_text
    
    db.commit()
    return {"status": "success"}

@router.post("/create-page")
def manual_create_page(payload: ConfigPayload, store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja: return {"error": "Loja não encontrada"}
    create_landing_page_internal(store_id, loja.access_token, payload.theme_color)
    return {"status": "success"}
