from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, distinct, desc
from datetime import datetime
from typing import List

# Importando do nível superior (..)
from ..database import get_db
from ..models import VendaApp, VisitaApp
from ..auth import get_current_store
from pydantic import BaseModel

router = APIRouter(prefix="/stats", tags=["Stats"])

# --- MODELOS DE ENTRADA ---
class VendaPayload(BaseModel):
    store_id: str
    valor: str
    visitor_id: str

class VisitaPayload(BaseModel):
    store_id: str
    pagina: str
    is_pwa: bool
    visitor_id: str

# --- ROTAS DE REGISTRO (Ouvidos do Sistema) ---

@router.post("/visita")
def registrar_visita(payload: VisitaPayload, db: Session = Depends(get_db)):
    db.add(VisitaApp(
        store_id=payload.store_id, 
        pagina=payload.pagina, 
        is_pwa=payload.is_pwa,
        visitor_id=payload.visitor_id,
        data=datetime.now().isoformat()
    ))
    db.commit()
    return {"status": "ok"}

@router.post("/venda")
def registrar_venda(payload: VendaPayload, db: Session = Depends(get_db)):
    db.add(VendaApp(
        store_id=payload.store_id, 
        valor=payload.valor, 
        visitor_id=payload.visitor_id,
        data=datetime.now().isoformat()
    ))
    db.commit()
    return {"status": "ok"}

@router.get("/total-vendas")
def get_stats_simples(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total = sum([float(v.valor) for v in vendas])
    return {"total": total, "quantidade": len(vendas)}

# --- O DASHBOARD INTELIGENTE (Lógica Real) ---
@router.get("/dashboard")
def get_dashboard_stats(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    # 1. Vendas e Receita
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum([float(v.valor) for v in vendas])
    qtd_vendas = len(vendas)

    # 2. Visitantes Únicos (Base para cálculos)
    visitantes_unicos = db.query(func.count(distinct(VisitaApp.visitor_id))).filter(VisitaApp.store_id == store_id).scalar() or 0
    
    # 3. Funil (Quem chegou no checkout/carrinho)
    # Contamos quantos visitor_id únicos visitaram páginas com "checkout" ou "cart"
    qtd_checkout = db.query(func.count(distinct(VisitaApp.visitor_id))).filter(
        VisitaApp.store_id == store_id, 
        (VisitaApp.pagina.contains("checkout") | VisitaApp.pagina.contains("carrinho") | VisitaApp.pagina.contains("cart"))
    ).scalar() or 0

    # 4. Carrinhos Abandonados (Chegou no checkout mas não comprou)
    # Simplificação: Checkout - Vendas. (Pode ser negativo se tiver erro de tracking, então usamos max(0))
    abandonos = max(0, qtd_checkout - qtd_vendas)
    ticket_medio_app = total_receita / max(1, qtd_vendas)
    valor_perdido = abandonos * ticket_medio_app

    # 5. Recorrência (Clientes com mais de 1 pedido)
    subquery = db.query(VendaApp.visitor_id).filter(VendaApp.store_id == store_id)\
                 .group_by(VendaApp.visitor_id).having(func.count(VendaApp.id) > 1).subquery()
    recorrentes = db.query(func.count(subquery.c.visitor_id)).scalar() or 0

    # 6. Pageviews Totais
    pageviews = db.query(VisitaApp).filter(VisitaApp.store_id == store_id).count()

    # 7. Top Páginas (As 5 mais acessadas)
    top_paginas_query = db.query(VisitaApp.pagina, func.count(VisitaApp.pagina).label('total'))\
        .filter(VisitaApp.store_id == store_id)\
        .group_by(VisitaApp.pagina)\
        .order_by(desc('total'))\
        .limit(5).all()
    
    top_paginas_list = [p[0] for p in top_paginas_query]

    # 8. Taxas Calculadas
    taxa_conversao_app = round((qtd_vendas / max(1, visitantes_unicos) * 100), 1)
    taxa_recompra = round((recorrentes / max(1, qtd_vendas) * 100), 1)

    return {
        "receita": total_receita,
        "vendas": qtd_vendas,
        "instalacoes": visitantes_unicos, # Usamos visitantes únicos como proxy de "usuários ativos"
        "carrinhos_abandonados": { "valor": valor_perdido, "qtd": abandonos },
        "visualizacoes": { 
            "pageviews": pageviews, 
            "tempo_medio": "Calculando...", # Complexo de calcular sem sessão, deixamos placeholder
            "top_paginas": top_paginas_list 
        },
        "funil": { 
            "visitas": visitantes_unicos, 
            "carrinho": qtd_checkout, 
            "checkout": qtd_vendas # No funil simplificado, checkout concluído = venda
        },
        "recorrencia": { 
            "clientes_2x": recorrentes, 
            "taxa_recompra": taxa_recompra 
        },
        "ticket_medio": { 
            "app": round(ticket_medio_app, 2), 
            "site": 0.0 # Sem API Nuvemshop, não sabemos o do site. Frontend pode ocultar ou mostrar 0.
        },
        "taxa_conversao": { 
            "app": taxa_conversao_app, 
            "site": 0.0 
        },
        "economia_ads": visitantes_unicos * 0.50 # Estimativa: R$0,50 por clique economizado
    }
