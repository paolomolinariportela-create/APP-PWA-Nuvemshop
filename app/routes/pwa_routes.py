from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Store
from typing import Optional

router = APIRouter()

@router.get("/manifest/{store_id}.json")
async def get_manifest(store_id: str, db: Session = Depends(get_db)):
    """
    Gera o manifesto do PWA dinamicamente para cada loja.
    O navegador do visitante vai acessar essa URL.
    """
    # 1. Busca as configurações da loja no banco de dados
    store = db.query(Store).filter(Store.store_id == store_id).first()

    if not store:
        # Se a loja não configurou o app, retorna um manifesto genérico ou erro 404
        raise HTTPException(status_code=404, detail="Loja não encontrada ou não configurada")

    # 2. Define valores padrão caso o lojista não tenha preenchido tudo
    app_name = store.app_name or "Minha Loja"
    short_name = store.app_name[:12] if store.app_name else "Loja"
    theme_color = store.theme_color or "#000000"
    background_color = store.background_color or "#ffffff"
    
    # Ícones: O ideal é ter o link da imagem hospedada. 
    # Por enquanto, vamos usar um placeholder se não tiver.
    icon_src = store.app_icon_url or "https://via.placeholder.com/192.png?text=App"

    # 3. Monta o JSON do Manifesto (Padrão PWA)
    manifest = {
        "name": app_name,
        "short_name": short_name,
        "start_url": "/",
        "display": "standalone",
        "background_color": background_color,
        "theme_color": theme_color,
        "orientation": "portrait",
        "icons": [
            {
                "src": icon_src,
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": icon_src,
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }

    # Retorna com o cabeçalho correto para JSON
    return JSONResponse(content=manifest)

