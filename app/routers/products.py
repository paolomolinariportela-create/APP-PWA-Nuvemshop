from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Loja, Produto
from app.security import verify_token_access
from app.services import sync_full_store_data

router = APIRouter()

@router.get("/products")
def list_products(limit: int = 100, store_id_secure: str = Depends(verify_token_access), db: Session = Depends(get_db)):
    return db.query(Produto).filter(Produto.store_id == store_id_secure).limit(limit).all()

@router.get("/admin/status")
def check_sync_status(store_id_secure: str = Depends(verify_token_access), db: Session = Depends(get_db)):
    loja = db.query(Loja).filter(Loja.store_id == store_id_secure).first()
    if not loja: raise HTTPException(404, detail="Loja não encontrada")
    
    total = db.query(Produto).filter(Produto.store_id == store_id_secure).count()
    return {"loja_nome": loja.nome_loja, "total_produtos_banco": total}

@router.post("/sync")
async def sync_products(
    force: bool = False, 
    background_tasks: BackgroundTasks = None, 
    store_id_secure: str = Depends(verify_token_access), 
    db: Session = Depends(get_db)
):
    # Aqui chamamos o service blindado que criamos antes
    if background_tasks:
        background_tasks.add_task(sync_full_store_data, store_id_secure, db, force)
    else:
        await sync_full_store_data(store_id_secure, db, force)
        
    return {"status": "ok", "message": "Sincronização iniciada com segurança."}
