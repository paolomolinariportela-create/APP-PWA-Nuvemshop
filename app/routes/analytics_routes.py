import os
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Optional, Union

from app.database import get_db
from app.models import VendaApp, VisitaApp, VariantEvent, CarrinhoAbandonado
from app.auth import get_current_store

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def get_db_url():
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("PGDATABASE_URL")
    )


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
    # ✅ e-mail do cliente logado (enviado pelo initUserIdentity)
    customer_email: Optional[str] = None


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

    # ✅ Integração com o agendador de carrinho abandonado
    try:
        cart_count = payload.cart_items_count or 0
        scheduler = request.app.state.scheduler
        db_url = get_db_url()

        from app.routes.automacao_routes import (
            agendar_recuperacao_carrinho,
            cancelar_recuperacao_carrinho,
        )

        if cart_count > 0:
            # Carrinho ativo — agenda recuperacao
            cart_total = None
            try:
                cart_total = float(payload.cart_total) if payload.cart_total else None
            except Exception:
                pass

            # Pega email do payload ou do carrinho existente
            external_id = payload.customer_email or ""
            if not external_id:
                carrinho = db.query(CarrinhoAbandonado).filter(
                    CarrinhoAbandonado.store_id == payload.store_id,
                    CarrinhoAbandonado.visitor_id == payload.visitor_id,
                ).first()
                if carrinho and carrinho.external_id:
                    external_id = carrinho.external_id

            agendar_recuperacao_carrinho(
                store_id=payload.store_id,
                visitor_id=payload.visitor_id,
                external_id=external_id,
                cart_count=cart_count,
                cart_total=cart_total,
                scheduler=scheduler,
                db=db,
                db_url=db_url,
            )

        else:
            # Carrinho vazio — cancela jobs se existirem
            carrinho = db.query(CarrinhoAbandonado).filter(
                CarrinhoAbandonado.store_id == payload.store_id,
                CarrinhoAbandonado.visitor_id == payload.visitor_id,
                CarrinhoAbandonado.status == "ativo",
            ).first()
            if carrinho:
                cancelar_recuperacao_carrinho(
                    store_id=payload.store_id,
                    visitor_id=payload.visitor_id,
                    scheduler=scheduler,
                    db=db,
                )

    except Exception as e:
        print(f"[AUTOMACAO] Erro ao processar carrinho: {e}")

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

    # ✅ Cancela jobs de carrinho abandonado quando cliente compra
    try:
        scheduler = request.app.state.scheduler
        from app.routes.automacao_routes import cancelar_recuperacao_carrinho
        cancelar_recuperacao_carrinho(
            store_id=payload.store_id,
            visitor_id=payload.visitor_id,
            scheduler=scheduler,
            db=db,
        )
        # Marca carrinho como comprado
        carrinho = db.query(CarrinhoAbandonado).filter(
            CarrinhoAbandonado.store_id == payload.store_id,
            CarrinhoAbandonado.visitor_id == payload.visitor_id,
        ).first()
        if carrinho:
            carrinho.status = "comprou"
            carrinho.atualizado_em = datetime.now().isoformat()
            db.commit()
    except Exception as e:
        print(f"[AUTOMACAO] Erro ao cancelar carrinho apos venda: {e}")

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


@router.get("/dashboard")
def get_dashboard_stats(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    agora = datetime.now()
    sete_dias_atras = agora - timedelta(days=7)
    quatorze_dias_atras = agora - timedelta(days=14)

    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum(float(v.valor) for v in vendas)
    qtd_vendas = len(vendas)

    visitantes_unicos = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(VisitaApp.store_id == store_id)
        .scalar() or 0
    )

    visitas_pwa = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(VisitaApp.store_id == store_id, VisitaApp.is_pwa == True)
        .scalar() or 0
    )
    visitas_site = max(0, visitantes_unicos - visitas_pwa)

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
        .scalar() or 0
    )
    vendas_site = max(0, qtd_vendas - vendas_pwa)

    qtd_checkout = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            (VisitaApp.pagina.contains("checkout") | VisitaApp.pagina.contains("carrinho")),
        )
        .scalar() or 0
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

    visitas_pwa_qs = db.query(VisitaApp).filter(
        VisitaApp.store_id == store_id, VisitaApp.is_pwa == True
    )
    pageviews_pwa = visitas_pwa_qs.count()

    top_paginas_pwa = [
        p[0]
        for p in db.query(VisitaApp.pagina, func.count(VisitaApp.pagina).label("total"))
        .filter(VisitaApp.store_id == store_id, VisitaApp.is_pwa == True)
        .group_by(VisitaApp.pagina)
        .order_by(desc("total"))
        .limit(5)
        .all()
    ]

    installs_7d = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.data >= sete_dias_atras.isoformat(),
        )
        .scalar() or 0
    )
    installs_7d_antes = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.data >= quatorze_dias_atras.isoformat(),
            VisitaApp.data < sete_dias_atras.isoformat(),
        )
        .scalar() or 0
    )

    crescimento_instalacoes_7d = (
        round((installs_7d - installs_7d_antes) / installs_7d_antes * 100, 1)
        if installs_7d_antes > 0 else 0.0
    )

    instalacoes_pwa = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.pagina == "install",
        )
        .scalar() or 0
    )

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
    LIMITE_SESSAO = 5 * 60

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
        tempo_medio_str = f"{media_segundos / 60:.1f} min".replace(".", ",")
    else:
        tempo_medio_str = "--"

    qtd_checkout_pwa = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            (VisitaApp.pagina.contains("checkout") | VisitaApp.pagina.contains("carrinho")),
        )
        .scalar() or 0
    )

    # ✅ Carrinhos abandonados ativos
    carrinhos_ativos = (
        db.query(func.count(CarrinhoAbandonado.id))
        .filter(
            CarrinhoAbandonado.store_id == store_id,
            CarrinhoAbandonado.status == "ativo",
        )
        .scalar() or 0
    )

    return {
        "receita": total_receita,
        "vendas": qtd_vendas,
        "instalacoes": instalacoes_pwa,
        "crescimento_instalacoes_7d": crescimento_instalacoes_7d,
        "carrinhos_abandonados": {
            "valor": abandonos * ticket_medio,
            "qtd": abandonos,
            "ativos_automacao": carrinhos_ativos,
        },
        "visualizacoes": {
            "pageviews": pageviews_pwa,
            "tempo_medio": tempo_medio_str,
            "top_paginas": top_paginas_pwa,
            "top_paginas_pwa": top_paginas_pwa,
        },
        "funil": {
            "visitas": visitas_pwa,
            "carrinho": qtd_checkout_pwa,
            "checkout": vendas_pwa,
        },
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
        "extra_pwa": {
            "visitas_pwa": visitas_pwa,
            "visitas_site": visitas_site,
            "vendas_pwa": vendas_pwa,
            "vendas_site": vendas_site,
        },
    }
