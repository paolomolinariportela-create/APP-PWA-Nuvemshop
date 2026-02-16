import os
import requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_store
from app.models import Loja

router = APIRouter(prefix="/nuvemshop", tags=["Nuvemshop Sync"])

@router.get("/orders")
def get_official_orders(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    """Busca pedidos OFICIAIS direto da API da Nuvemshop"""
    
    # 1. Busca o Token da Loja
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja or not loja.access_token:
        return {"error": "Loja não conectada ou sem token."}

    headers = {
        "Authentication": f"bearer {loja.access_token}",
        "User-Agent": "AppBuilder (contato@seuapp.com)"
    }

    # 2. Consulta API de Pedidos (Últimos 30 dias, Pagos)
    # Filtra: status=paid (pago)
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/orders?status=paid&per_page=50"
    
    try:
        req = requests.get(url, headers=headers)
        if req.status_code != 200:
            return {"error": "Erro na API Nuvemshop", "details": req.text}
        
        orders = req.json()
        
        # 3. Processa os Dados
        total_faturado = 0
        total_pedidos = len(orders)
        
        # Tenta identificar pedidos vindos do App (Ex: via user_agent ou campo note se tivermos injetado)
        # Por enquanto, vamos retornar o TOTAL OFICIAL DA LOJA para comparação
        for order in orders:
            total_faturado += float(order.get("total", 0))

        return {
            "origem": "Nuvemshop API",
            "total_pedidos_pagos": total_pedidos,
            "total_faturado": total_faturado,
            "ultimos_pedidos": orders[:5] # Retorna os 5 últimos para preview
        }

    except Exception as e:
        return {"error": "Falha na conexão", "details": str(e)}

@router.get("/abandoned-checkouts")
def get_official_abandoned(store_id: str = Depends(get_current_store), db: Session = Depends(get_db)):
    """Busca checkouts abandonados OFICIAIS"""
    
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja or not loja.access_token:
        return {"error": "Loja sem token."}

    headers = { "Authentication": f"bearer {loja.access_token}", "User-Agent": "AppBuilder" }
    
    # API de Checkouts (buscando os que não viraram pedido ainda)
    # Nota: A API de 'abandoned_checkouts' da Nuvemshop é um pouco restrita,
    # às vezes usamos a de 'orders' com status 'open' ou endpoint específico se disponível.
    # Vamos tentar o endpoint padrão de checkouts.
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/checkouts?per_page=50"

    try:
        req = requests.get(url, headers=headers)
        checkouts = req.json() if req.status_code == 200 else []
        
        # Filtra simples (apenas checkouts sem order_id costumam ser abandonos)
        abandonados = [c for c in checkouts if not c.get("order_id")]
        
        total_valor = sum([float(c.get("total", 0)) for c in abandonados])

        return {
            "qtd_abandonados": len(abandonados),
            "valor_estimado": total_valor,
            "lista": abandonados[:5]
        }
    except:
        return {"qtd_abandonados": 0, "valor_estimado": 0}
