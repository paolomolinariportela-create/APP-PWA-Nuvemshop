from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from datetime import datetime, timedelta
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
    # janelas de tempo
    agora = datetime.now()
    sete_dias_atras = agora - timedelta(days=7)
    quatorze_dias_atras = agora - timedelta(days=14)

    # VENDAS / RECEITA
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum(float(v.valor) for v in vendas)
    qtd_vendas = len(vendas)

    # VISITANTES ÚNICOS (todos, site + PWA)
    visitantes_unicos = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(VisitaApp.store_id == store_id)
        .scalar()
        or 0
    )

    # INFO EXTRA: VISITAS PWA vs SITE
    visitas_pwa = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
        )
        .scalar()
        or 0
    )
    visitas_site = max(0, visitantes_unicos - visitas_pwa)

    # INFO EXTRA: VENDAS PWA vs SITE
    vendas_pwa = (
        db.query(func.count(VendaApp.id))
        .filter(
            VendaApp.store_id == store_id,
            VendaApp.visitor_id.in_(
                db.query(VisitaApp.visitor_id).filter(
                    VisitaApp.store_id == store_id,
                    VisitaApp.is_pwa == True,
                )
            ),
        )
        .scalar()
        or 0
    )
    vendas_site = max(0, qtd_vendas - vendas_pwa)

    # CHECKOUT / CARRINHO (todos)
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

    # CLIENTES RECORRENTES (2+ compras)
    subquery = (
        db.query(VendaApp.visitor_id)
        .filter(VendaApp.store_id == store_id)
        .group_by(VendaApp.visitor_id)
        .having(func.count(VendaApp.id) > 1)
        .subquery()
    )
    recorrentes = db.query(func.count(subquery.c.visitor_id)).scalar() or 0

    # BASE DE VISITAS (todos)
    visitas_qs = db.query(VisitaApp).filter(VisitaApp.store_id == store_id)

    # PAGEVIEWS E TOP PÁGINAS SOMENTE PWA
    visitas_pwa_qs = visitas_qs.filter(VisitaApp.is_pwa == True)
    pageviews_pwa = visitas_pwa_qs.count()

    top_paginas_pwa = [
        p[0]
        for p in db.query(
            VisitaApp.pagina,
            func.count(VisitaApp.pagina).label("total"),
        )
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
        )
        .group_by(VisitaApp.pagina)
        .order_by(desc("total"))
        .limit(5)
        .all()
    ]

    # CRESCIMENTO DE INSTALAÇÕES (PWA) NOS ÚLTIMOS 7 DIAS
    installs_7d = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.data >= sete_dias_atras.isoformat(),
        )
        .scalar()
        or 0
    )

    installs_7d_antes = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.data >= quatorze_dias_atras.isoformat(),
            VisitaApp.data < sete_dias_atras.isoformat(),
        )
        .scalar()
        or 0
    )

    if installs_7d_antes > 0:
        crescimento_instalacoes_7d = round(
            (installs_7d - installs_7d_antes) / installs_7d_antes * 100,
            1,
        )
    else:
        crescimento_instalacoes_7d = 0.0

    # INSTALAÇÕES ATIVAS PWA (visitantes que passaram pela página 'install' em modo PWA)
    instalacoes_pwa = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.pagina == "install",
        )
        .scalar()
        or 0
    )

    # TEMPO MÉDIO NO APP (PWA) – SESSÃO MÁX 5 MIN ENTRE PÁGINAS
    from datetime import datetime as _dt

    visitas_pwa_list = (
        visitas_pwa_qs.filter(VisitaApp.visitor_id.isnot(None))
        .order_by(VisitaApp.visitor_id, VisitaApp.data)
        .all()
    )

    total_segundos = 0
    total_sessoes = 0

    ultimo_visitante = None
    ultima_data = None

    LIMITE_SESSAO = 5 * 60  # 5 minutos

    for v in visitas_pwa_list:
        try:
            dt = _dt.fromisoformat(v.data)
        except Exception:
            continue

        if v.visitor_id != ultimo_visitante:
            ultimo_visitante = v.visitor_id
            ultima_data = dt
            total_sessoes += 1
        else:
            diff = (dt - ultima_data).total_seconds()
            if 0 < diff <= LIMITE_SESSAO:
                total_segundos += diff
            ultima_data = dt

    if total_sessoes > 0 and total_segundos > 0:
        media_segundos = total_segundos / total_sessoes
        media_minutos = media_segundos / 60
        tempo_medio_str = f"{media_minutos:.1f} min".replace(".", ",")
    else:
        tempo_medio_str = "--"

    return {
        "receita": total_receita,
        "vendas": qtd_vendas,
        # agora só instalações PWA
        "instalacoes": instalacoes_pwa,
        "crescimento_instalacoes_7d": crescimento_instalacoes_7d,
        "carrinhos_abandonados": {
            "valor": abandonos * ticket_medio,
            "qtd": abandonos,
        },
        "visualizacoes": {
            # só pageviews PWA
            "pageviews": pageviews_pwa,
            "tempo_medio": tempo_medio_str,
            # top páginas também só PWA
            "top_paginas": top_paginas_pwa,
            "top_paginas_pwa": top_paginas_pwa,
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
        "extra_pwa": {
            "visitas_pwa": visitas_pwa,
            "visitas_site": visitas_site,
            "vendas_pwa": vendas_pwa,
            "vendas_site": vendas_site,
        },
    }
