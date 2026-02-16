from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from datetime import datetime
from pydantic import BaseModel

from app.database import get_db
from app.models import VendaApp, VisitaApp
from app.auth import get_current_store
from app.security import validate_proxy_hmac  # novo import

router = APIRouter(prefix="/analytics", tags=["Analytics"])

class VendaPayload(BaseModel):
    store_id: str
    valor: str
    visitor_id: str

class VisitaPayload(BaseModel):
    store_id: str
    pagina: str
    is_pwa: bool
    visitor_id: str

@router.post("/visita")
async def registrar_visita(
    payload: VisitaPayload,
    request: Request,
    _valid=Depends(validate_proxy_hmac),
    db: Session = Depends(get_db)
):
    db.add(
        VisitaApp(
            store_id=payload.store_id,
            pagina=payload.pagina,
            is_pwa=payload.is_pwa,
            visitor_id=payload.visitor_id,
            data=datetime.now().isoformat()
        )
    )
    db.commit()
    return {"status": "ok"}

@router.post("/venda")
async def registrar_venda(
    payload: VendaPayload,
    request: Request,
    _valid=Depends(validate_proxy_hmac),
    db: Session = Depends(get_db)
):
    db.add(
        VendaApp(
            store_id=payload.store_id,
            valor=payload.valor,
            visitor_id=payload.visitor_id,
            data=datetime.now().isoformat()
        )
    )
    db.commit()
    return {"status": "ok"}

@router.get("/dashboard")
def get_dashboard_stats(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db)
):
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum([float(v.valor) for v in vendas])
    qtd_vendas = len(vendas)
    visitantes_unicos = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(VisitaApp.store_id == store_id)
        .scalar()
        or 0
    )
    qtd_checkout = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            (VisitaApp.pagina.contains("checkout") | VisitaApp.pagina.contains("carrinho")),
        )
        .scalar()
        or 0
    )
    abandonos = max(0, qtd_checkout - qtd_vendas)
    ticket_medio = total_receita / max(1, qtd_vendas) if qtd_vendas > 0 else 0
    subquery = (
        db.query(VendaApp.visitor_id)
        .filter(VendaApp.store_id == store_id)
        .group_by(VendaApp.visitor_id)
        .having(func.count(VendaApp.id) > 1)
        .subquery()
    )
    recorrentes = db.query(func.count(subquery.c.visitor_id)).scalar() or 0
    pageviews = db.query(VisitaApp).filter(VisitaApp.store_id == store_id).count()
    top_paginas = [
        p[0]
        for p in db.query(
            VisitaApp.pagina,
            func.count(VisitaApp.pagina).label("total"),
        )
        .filter(VisitaApp.store_id == store_id)
        .group_by(VisitaApp.pagina)
        .order_by(desc("total"))
        .limit(5)
        .all()
    ]

    return {
        "receita": total_receita,
        "vendas": qtd_vendas,
        "instalacoes": visitantes_unicos,
        "carrinhos_abandonados": {"valor": abandonos * ticket_medio, "qtd": abandonos},
        "visualizacoes": {
            "pageviews": pageviews,
            "tempo_medio": "--",
            "top_paginas": top_paginas,
        },
        "funil": {"visitas": visitantes_unicos, "carrinho": qtd_checkout, "checkout": qtd_vendas},
        "recorrencia": {
            "clientes_2x": recorrentes,
            "taxa_recompra": round((recorrentes / max(1, qtd_vendas) * 100), 1),
        },
        "ticket_medio": {"app": round(ticket_medio, 2), "site": 0.0},
        "taxa_conversao": {
            "app": round((qtd_vendas / max(1, visitantes_unicos) * 100), 1),
            "site": 0.0,
        },
        "economia_ads": visitantes_unicos * 0.50,
    }
