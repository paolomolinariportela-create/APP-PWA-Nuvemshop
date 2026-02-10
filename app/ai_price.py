from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_bulk_action",
            "description": "Gera comando de precificação, suportando margem de lucro e travas de segurança.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "scope": {
                        "type": "string", 
                        "enum": ["PRODUCT", "VARIANT"],
                        "description": "VARIANT para cor/tamanho específico, PRODUCT para geral."
                    },
                    "find_product": {
                        "type": "object", 
                        "properties": {
                            "title_contains": {"type": "string"},
                            "category_contains": {"type": "string"},
                            "stock_min": {"type": "integer", "description": "Filtra produtos com estoque ACIMA deste valor (ex: para liquidação)."}
                        }
                    },
                    "find_variant": {
                        "type": "object",
                        "properties": {
                            "attributes": {
                                "type": "array",
                                "items": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "string"}}}
                            }
                        }
                    },
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "enum": ["price", "promotional_price", "cost"]}, 
                                "action": {
                                    "type": "string", 
                                    "enum": ["SET", "INCREASE_PERCENT", "DECREASE_PERCENT", "INCREASE_FIXED", "DECREASE_FIXED", "REMOVE", "APPLY_MARKUP"],
                                    "description": "Use APPLY_MARKUP para definir preço baseado no Custo."
                                },
                                "value": {"type": "string", "description": "Valor numérico. Para Markup, 100% de lucro = value '100'."},
                                "rounding": {"type": "string", "enum": ["NONE", "0.90", "0.99", "0.00"]},
                                "safety_lock": {
                                    "type": "boolean", 
                                    "description": "Se true, impede que o preço final fique menor que o Custo do produto."
                                }
                            },
                            "required": ["field", "action", "value"]
                        }
                    }
                },
                "required": ["scope", "find_product", "changes"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um Estrategista de Preços (Pricing Manager).

NOVAS HABILIDADES:
1. MARKUP (LUCRO): Se o usuário disser "Quero 100% de lucro", "Margem de 50%" ou "Preço baseado no custo", use a ação 'APPLY_MARKUP'.
   - O 'value' é a porcentagem de lucro sobre o custo. (Ex: Custo 100 + 50% lucro = Preço 150).
2. TRAVA DE SEGURANÇA: Se o usuário disser "Não venda abaixo do custo" ou "Cuidado com o prejuízo", defina 'safety_lock': true.
3. LIQUIDAÇÃO: Se disser "Liquidar estoque alto" ou "Produtos encalhados", use o filtro 'stock_min'.

EXEMPLOS:
- "Colocar margem de 100% em tudo da Nike" -> action: APPLY_MARKUP, value: "100", filter: title_contains "Nike".
- "Dar 40% de desconto mas não baixar do custo" -> action: DECREASE_PERCENT, value: "40", safety_lock: true.

Nota: Se o usuário pedir para mudar o 'Custo', o field é 'cost'. Se pedir preço de venda, é 'price'.
"""

def run_logic(db: Session, store_id: str, plan: Dict[str, Any]):
    try:
        products = get_filtered_products(db, store_id, plan)
        affected_count = 0
        samples = []
        
        variant_filters = plan.get('find_variant', {}).get('attributes', [])
        
        # Lógica de contagem (simplificada para o resumo)
        for p in products:
            if plan.get('scope') == 'VARIANT':
                # (Lógica de contagem de variantes mantida igual ao anterior...)
                match_vars = 0
                if p.variants_json:
                    import json
                    try: v_list = json.loads(p.variants_json)
                    except: v_list = []
                    for v in v_list:
                        match_vars += 1 # Simplificação para contagem rápida
                if match_vars > 0:
                    affected_count += match_vars
                    if len(samples) < 5: samples.append(f"• {p.name}")
            else:
                affected_count += 1
                if len(samples) < 5: samples.append(f"• {p.name}")

        # --- TRADUÇÃO DO RESUMO ---
        change = plan['changes'][0]
        act = change['action']
        val = change['value']
        safe = change.get('safety_lock', False)
        
        hum_map = {
            "APPLY_MARKUP": f"Definir preço para Custo + {val}% (Markup)",
            "SET": f"Definir valor exato R$ {val}",
            "INCREASE_PERCENT": f"Aumentar {val}%",
            "DECREASE_PERCENT": f"Desconto de {val}%",
            "REMOVE": "Remover oferta"
        }
        
        txt_action = hum_map.get(act, f"{act} {val}")
        if safe: txt_action += " 🛡️ (Com Trava de Custo)"
        
        resumo = (
            f"✅ **Estratégia Definida:**\n"
            f"🔧 **Ação:** {txt_action}\n"
            f"📦 **Afetados:** {affected_count} itens\n\n"
            f"📝 **Exemplos:**\n" + "\n".join(samples)
        )

        return {"plan_summary": resumo, "command": plan}
    except Exception as e:
        return {"error": str(e)}
