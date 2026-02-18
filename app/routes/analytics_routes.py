from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from datetime import datetime
from pydantic import BaseModel
from typing import Optional, Union

from app.database import get_db
from app.models import VendaApp, VisitaApp, VariantEvent
from app.auth import get_current_store
# from app.security import validate_proxy_hmac  # não usado nas rotas chamadas pelo browser

router = APIRouter(prefix="/analytics", tags=["Analytics"])

# ----- PAYLOADS -----


class VendaPayload(BaseModel):
    store_id: str
    valor: str
    visitor_id: str


class VisitaPayload(BaseModel):
    store_id: str
    pagina: str
    is_pwa: bool
    visitor_id: str
    store_ls_id: Optional[Union[str, int]] = None
    product_id: Optional[Union[str, int]] = None
    product_name: Optional[str] = None
    cart_total: Optional[Union[int, float, str]] = None
    cart_items_count: Optional[int] = None

class VariantEventPayload(BaseModel):
    store_id: str
    visitor_id: str
    product_id: str
    variant_id: str
    variant_name: str | None = None
    price: str | None = None
    stock: int | None = None


class InstallPayload(BaseModel):
    store_id: str
    visitor_id: str


# ----- ENDPOINTS DE REGISTRO (chamados pelo loader.js, sem HMAC) -----


@router.post("/visita")
async def registrar_visita(
    payload: VisitaPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    db.add(
        VisitaApp(
            store_id=payload.store_id,
            pagina=payload.pagina,
            is_pwa=payload.is_pwa,
            visitor_id=payload.visitor_id,
            data=datetime.now().isoformat(),
        )
    )
    db.commit()
    return {"status": "ok"}


@router.post("/venda")
async def registrar_venda(
    payload: VendaPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    db.add(
        VendaApp(
            store_id=payload.store_id,
            valor=payload.valor,
            visitor_id=payload.visitor_id,
            data=datetime.now().isoformat(),
        )
    )
    db.commit()
    return {"status": "ok"}


@router.post("/variant")
async def registrar_variant_event(
    payload: VariantEventPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    db.add(
        VariantEvent(
            store_id=payload.store_id,
            visitor_id=payload.visitor_id,
            product_id=payload.product_id,
            variant_id=payload.variant_id,
            variant_name=payload.variant_name,
            price=payload.price,
            stock=payload.stock,
            data=datetime.now().isoformat(),
        )
    )
    db.commit()
    return {"status": "ok"}


@router.post("/install")
async def registrar_install(
    payload: InstallPayload,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Marca explicitamente uma instalação de app.
    Para manter compatibilidade, gravamos como uma visita 'install' em modo PWA.
    """
    db.add(
        VisitaApp(
            store_id=payload.store_id,
            pagina="install",
            is_pwa=True,
            visitor_id=payload.visitor_id,
            data=datetime.now().isoformat(),
        )
    )
    db.commit()
    return {"status": "ok"}


# ----- DASHBOARD -----


@router.get("/dashboard")
def get_dashboard_stats(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum(float(v.valor) for v in vendas)
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
            (
                VisitaApp.pagina.contains("checkout")
                | VisitaApp.pagina.contains("carrinho")
            ),
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

    # PAGEVIEWS E TOP PÁGINAS (igual estava)
    visitas_qs = db.query(VisitaApp).filter(VisitaApp.store_id == store_id)
    pageviews = visitas_qs.count()

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

    # CÁLCULO DO TEMPO MÉDIO NO APP (em minutos, string tipo "3,2 min")
    from datetime import datetime

    # buscamos só visitas que são PWA (is_pwa=True)
    visitas_pwa = (
        visitas_qs.filter(VisitaApp.is_pwa == True)
        .order_by(VisitaApp.visitor_id, VisitaApp.data)
        .all()
    )

    total_segundos = 0
    total_sessoes = 0

    ultimo_visitante = None
    ultima_data = None

    for v in visitas_pwa:
        try:
            dt = datetime.fromisoformat(v.data)
        except Exception:
            # se não conseguir converter a data, pula esse registro
            continue

        if v.visitor_id != ultimo_visitante:
            # nova sessão
            ultimo_visitante = v.visitor_id
            ultima_data = dt
            total_sessoes += 1
        else:
            # mesmo visitante, soma diferença de tempo entre páginas
            diff = (dt - ultima_data).total_seconds()
            if diff > 0:
                total_segundos += diff
            ultima_data = dt

    if total_sessoes > 0:
        media_segundos = total_segundos / total_sessoes
        media_minutos = media_segundos / 60
        tempo_medio_str = f"{media_minutos:.1f} min".replace(".", ",")
    else:
        tempo_medio_str = "--"

    return {
        "receita": total_receita,
        "vendas": qtd_vendas,
        "instalacoes": visitantes_unicos,
        "carrinhos_abandonados": {
            "valor": abandonos * ticket_medio,
            "qtd": abandonos,
        },
        "visualizacoes": {
            "pageviews": pageviews,
            "tempo_medio": tempo_medio_str,
            "top_paginas": top_paginas,
        },
        "funil": {
            "visitas": visitantes_unicos,
            "carrinho": qtd_checkout,
            "checkout": qtd_vendas,
        },
        "recorrencia": {
            "clientes_2x": recorrentes,
            "taxa_recompra": round(
                (recorrentes / max(1, qtd_vendas) * 100),
                1,
            ),
        },
        "ticket_medio": {"app": round(ticket_medio, 2), "site": 0.0},
        "taxa_conversao": {
            "app": round(
                (qtd_vendas / max(1, visitantes_unicos) * 100),
                1,
            ),
            "site": 0.0,
        },
        "economia_ads": visitantes_unicos * 0.50,
    }

