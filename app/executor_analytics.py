from sqlalchemy.orm import Session
from .models import Loja, Produto
from .utils import get_filtered_products

def get_inventory_valuation(store_id: str, plan: dict, db: Session):
    """
    Calcula o valor total do estoque (Valuation) baseado no Custo.
    Retorna um resumo formatado.
    """
    print(f"📊 [ANALYTICS] Calculando Valuation para loja: {store_id}")
    
    # 1. Busca produtos (respeitando filtros se houver, ex: 'só da Nike')
    products = get_filtered_products(db, store_id, plan)
    
    total_items = 0
    total_cost_value = 0.0
    total_sale_value = 0.0
    items_without_cost = 0

    for p in products:
        # Tenta ler o JSON de variantes
        variants = []
        if p.variants_json:
            import json
            try: variants = json.loads(p.variants_json)
            except: variants = []
        
        # Se não tiver variantes, usa dados do produto pai (fallback)
        if not variants:
            stock = int(p.stock or 0)
            cost = float(p.cost or 0)
            price = float(p.price or 0)
            
            if stock > 0:
                total_items += stock
                total_cost_value += (stock * cost)
                total_sale_value += (stock * price)
                if cost == 0: items_without_cost += 1
        
        # Se tiver variantes, soma uma por uma
        else:
            for v in variants:
                stock = int(v.get('stock', 0) or 0)
                cost = float(v.get('cost', 0) or 0)
                price = float(v.get('price', 0) or 0)
                
                if stock > 0:
                    total_items += stock
                    total_cost_value += (stock * cost)
                    total_sale_value += (stock * price)
                    if cost == 0: items_without_cost += 1

    # Formatação do Relatório
    potential_profit = total_sale_value - total_cost_value
    margin = (potential_profit / total_sale_value * 100) if total_sale_value > 0 else 0

    report = (
        f"💰 **Relatório de Valuation (Estoque)**\n\n"
        f"📦 **Total de Itens:** {total_items} unidades\n"
        f"🏭 **Custo Total:** R$ {total_cost_value:,.2f}\n"
        f"🏷️ **Valor de Venda:** R$ {total_sale_value:,.2f}\n"
        f"📈 **Lucro Potencial:** R$ {potential_profit:,.2f} (Margem aprox: {margin:.1f}%)\n\n"
    )

    if items_without_cost > 0:
        report += f"⚠️ **Atenção:** {items_without_cost} itens estão com Custo R$ 0,00 (O valor real pode ser maior)."
    
    return report
