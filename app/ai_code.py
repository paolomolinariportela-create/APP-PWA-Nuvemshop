from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_code",
            "description": "Gerencia códigos do produto (SKU/Referência e Barcode/GTIN).",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_summary": {"type": "string"},
                    "find_product": {
                        "type": "object", 
                        "properties": {
                            "title_contains": {"type": "string"}, 
                            "sku_contains": {"type": "string"}
                        }
                    },
                    "action": {
                        "type": "string",
                        "enum": [
                            "SET_SKU",              # Definir SKU manual
                            "GENERATE_SKU_FROM_ID", # Gerar SKU automático (ID-VARIANTE)
                            "INHERIT_SKU_FROM_PARENT", # Herdar do pai (PAI-VARIANTE) -> NOVO
                            "SANITIZE_CODES",       # Limpar espaços/símbolos -> NOVO
                            "SET_BARCODE",          # Definir EAN/GTIN
                            "CLEAR_CODE"            # Limpar (SKU ou Barcode)
                        ],
                        "description": "Ação técnica sobre os códigos."
                    },
                    "target_field": {
                        "type": "string",
                        "enum": ["sku", "barcode"],
                        "description": "Qual código alterar."
                    },
                    "value": {
                        "type": "string",
                        "description": "O valor literal (se for SET)."
                    }
                },
                "required": ["plan_summary", "find_product", "action", "target_field"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um OPERADOR DE CÓDIGOS (SKU/EAN).
SUA FUNÇÃO É EXECUTAR COMANDOS LITERAIS.

COMANDOS:
1. "Mudar SKU para X" -> action="SET_SKU", value="X"
2. "Gerar SKU pelo ID" -> action="GENERATE_SKU_FROM_ID"
3. "Copiar SKU do pai para variantes" -> action="INHERIT_SKU_FROM_PARENT"
4. "Limpar códigos (tirar espaços/símbolos)" -> action="SANITIZE_CODES"
5. "Definir EAN/GTIN para Y" -> action="SET_BARCODE", value="Y"
6. "Apagar SKU/Barcode" -> action="CLEAR_CODE"

IMPORTANTE:
- SKU é a Referência.
- Barcode é o Código de Barras (GTIN/EAN).
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        plan = args
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = [f"• {p.name}" for p in products[:5]] if products else []

        act = plan.get('action')
        field = plan.get('target_field', 'sku')
        val = plan.get('value', '')
        
        txt_acao = ""
        if act == 'SET_SKU': txt_acao = f"🔢 **Definir SKU:** '{val}'"
        elif act == 'GENERATE_SKU_FROM_ID': txt_acao = "⚙️ **Gerar SKU Automático** (Baseado no ID)"
        elif act == 'INHERIT_SKU_FROM_PARENT': txt_acao = "👪 **Herdar SKU do Pai** (Prefixo Padrão)"
        elif act == 'SANITIZE_CODES': txt_acao = "🧹 **Higienizar Códigos** (Remover espaços/símbolos)"
        elif act == 'SET_BARCODE': txt_acao = f"barcode **Definir GTIN/EAN:** '{val}'"
        elif act == 'CLEAR_CODE': txt_acao = f"🗑️ **Apagar {field.upper()}**"

        resumo = (
            f"🤖 **Comando de Código:**\n{txt_acao}\n"
            f"🎯 **Alvo:** {affected_count} produtos\n"
            f"📝 **Amostra:**\n" + "\n".join(samples)
        )

        plan['changes'] = [{
            'field': field,
            'action': act,
            'value': val
        }]

        return {"plan_summary": resumo, "plan_json": plan}
    except Exception as e:
        return {"plan_summary": f"Erro: {str(e)}", "error": str(e)}
