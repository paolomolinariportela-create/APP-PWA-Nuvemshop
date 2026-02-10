from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_logistics",
            "description": "Gerencia frete, peso e dimensões do produto em lote.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_summary": {"type": "string"},
                    "find_product": {
                        "type": "object", 
                        "properties": {
                            "title_contains": {"type": "string"}, 
                            "category_contains": {"type": "string"}
                        }
                    },
                    "action": {
                        "type": "string",
                        "enum": ["SET_DIMENSIONS", "ADD_TO_DIMENSIONS", "SET_FREE_SHIPPING"],
                        "description": "Definir medidas, Somar medidas (embalagem) ou Ligar/Desligar Frete Grátis."
                    },
                    "dimensions": {
                        "type": "object",
                        "properties": {
                            "weight": {"type": "string", "description": "Peso em KG (ex: 0.500)"},
                            "height": {"type": "string", "description": "Altura em CM"},
                            "width": {"type": "string", "description": "Largura em CM"},
                            "depth": {"type": "string", "description": "Profundidade em CM"}
                        },
                        "description": "Objeto com valores. Se for ADD, será somado ao atual."
                    },
                    "free_shipping": {
                        "type": "boolean",
                        "description": "True para ativar frete grátis, False para cobrar."
                    }
                },
                "required": ["plan_summary", "find_product", "action"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um OPERADOR DE LOGÍSTICA E FRETE.
SUA FUNÇÃO É GERENCIAR PESO, MEDIDAS E FRETE GRÁTIS.

COMANDOS:
1. "Mudar peso para 1kg" -> action="SET_DIMENSIONS", dimensions={"weight": "1.000"}
2. "Adicionar 100g no peso (embalagem)" -> action="ADD_TO_DIMENSIONS", dimensions={"weight": "0.100"}
3. "Ativar frete grátis" -> action="SET_FREE_SHIPPING", free_shipping=true
4. "Cobrar frete normal" -> action="SET_FREE_SHIPPING", free_shipping=false

ATENÇÃO:
- ADD_TO_DIMENSIONS soma o valor ao que já existe no produto.
- SET_DIMENSIONS substitui o valor antigo.
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        plan = args
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = [f"• {p.name}" for p in products[:5]] if products else []

        act = plan.get('action')
        dims = plan.get('dimensions', {})
        free = plan.get('free_shipping')
        
        txt_acao = ""
        if act == 'SET_DIMENSIONS':
            lista = [f"{k}={v}" for k, v in dims.items()]
            txt_acao = f"📦 **Definir Medidas:** {', '.join(lista)}"
        elif act == 'ADD_TO_DIMENSIONS':
            lista = [f"{k}+{v}" for k, v in dims.items()]
            txt_acao = f"➕ **Somar Embalagem:** {', '.join(lista)}"
        elif act == 'SET_FREE_SHIPPING':
            estado = "ATIVADO (Grátis)" if free else "DESATIVADO (Cobrar)"
            txt_acao = f"🚚 **Frete Grátis:** {estado}"

        resumo = (
            f"{txt_acao}\n"
            f"🎯 **Alvo:** {affected_count} produtos\n"
            f"📝 **Amostra:**\n" + "\n".join(samples)
        )

        plan['changes'] = [{
            'field': 'logistics_batch',
            'action': act,
            'dimensions': dims,
            'free_shipping': free
        }]

        return {"plan_summary": resumo, "plan_json": plan}
    except Exception as e:
        return {"plan_summary": f"Erro: {str(e)}", "error": str(e)}
