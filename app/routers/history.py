import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.models import HistoryLog
from app.security import verify_token_access
from app.executor import execute_nuvemshop_update

router = APIRouter()

@router.get("/history")
def get_history(store_id_secure: str = Depends(verify_token_access), db: Session = Depends(get_db)):
    return db.query(HistoryLog).filter(HistoryLog.store_id == store_id_secure).order_by(text("created_at desc")).limit(20).all()

@router.post("/history/revert/{log_id}")
async def revert_history(
    log_id: int, 
    background_tasks: BackgroundTasks, 
    store_id_secure: str = Depends(verify_token_access), 
    db: Session = Depends(get_db)
):
    log = db.query(HistoryLog).filter(HistoryLog.id == log_id, HistoryLog.store_id == store_id_secure).first()
    
    if not log: raise HTTPException(404, detail="Log não encontrado.")
    if log.status == "REVERTED": return {"status": "error", "message": "Já revertido"}
        
    try:
        original = json.loads(log.full_command)
        if 'changes' in original and original['changes']:
            change = original['changes'][0]
            revert_plan = original.copy()
            
            # Lógica simples de inversão
            if change['field'] == 'title':
                revert_plan['changes'][0]['action'] = 'REPLACE'
                revert_plan['changes'][0]['replace_this'] = change['value']
                revert_plan['changes'][0]['value'] = change.get('replace_this', "")
            
            # (Adicione aqui a lógica completa de reversão se tiver mais tipos)

            background_tasks.add_task(execute_nuvemshop_update, log.store_id, revert_plan, db)
            log.status = "REVERTED"
            db.commit()
            return {"status": "ok"}
        return {"status": "error", "message": "Formato não suportado"}

    except Exception as e: 
        return {"status": "error", "message": str(e)}
