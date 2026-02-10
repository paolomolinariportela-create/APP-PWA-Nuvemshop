from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_brand",
            "description": "Executa alterações na MARCA do produto.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_summary": {"type": "string"},
                    "find_product": {
                        "type": "object", 
                        "properties": {
                            "title_contains": {"type": "string"}, 
                            "brand_contains": {"type": "string"}
                        }
                    },
                    "action": {
                        "type": "string",
                        "enum": [
                            "SET_BRAND",            # Definir Manualmente
                            "REPLACE_BRAND",        # Trocar X por Y
                            "REMOVE_BRAND",         # Limpar
                            "STANDARDIZE_CASE",     # Padronizar (Nike, NIKE -> Nike)
                            "SET_FROM_TITLE_KEYWORD"# Se achar palavra no título, vira marca
                        ],
                        "description": "Ações literais de marca."
                    },
                    "value": {
                        "type": "string",
                        "description": "Nome da marca ou Palavra-chave para buscar no título."
                    },
                    "case_type": {
                        "type": "string",
                        "enum": ["TITLE_CASE", "UPPERCASE", "LOWERCASE"],
                        "description": "Usar com STANDARDIZE_CASE. Padrão: TITLE_CASE."
                    },
                    "replace_this": {"type": "string"}
                },
                "required": ["plan_summary", "find_product", "action"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um OPERADOR DE MARCAS.
SUA FUNÇÃO É EXECUTAR COMANDOS LITERAIS.

NOVAS HABILIDADES:
1. "Padronizar marcas" -> action="STANDARDIZE_CASE", case_type="TITLE_CASE" (ou UPPERCASE/LOWERCASE)
2. "Se tiver Nike no título, põe na marca" -> action="SET_FROM_TITLE_KEYWORD", value="Nike"

HABILIDADES ANTIGAS:
- "Mudar marca para X" -> action="SET_BRAND", value="X"
- "Trocar X por Y" -> action="REPLACE_BRAND"
- "Remover/Limpar" -> action="REMOVE_BRAND"

NÃO INVENTE NOMES. USE EXATAMENTE O QUE O USUÁRIO DISSER.
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        plan = args
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = [f"• {p.name}" for p in products[:5]] if products else []

        act = plan.get('action')
        val = plan.get('value', '')
        
        txt_acao = ""
        if act == 'SET_BRAND': txt_acao = f"🏷️ **Definir Marca:** '{val}'"
        elif act == 'REPLACE_BRAND': txt_acao = f"🔄 **Trocar Marca:** '{plan.get('replace_this')}' por '{val}'"
        elif act == 'REMOVE_BRAND': txt_acao = "🗑️ **Remover Marca**"
        elif act == 'STANDARDIZE_CASE': txt_acao = f"🎨 **Padronizar:** {plan.get('case_type', 'TITLE_CASE')}"
        elif act == 'SET_FROM_TITLE_KEYWORD': txt_acao = f"🕵️ **Extrair do Título:** Se achar '{val}', definir como Marca."

        resumo = (
            f"🤖 **Comando de Marca:**\n{txt_acao}\n"
            f"🎯 **Alvo:** {affected_count} produtos\n"
            f"📝 **Amostra:**\n" + "\n".join(samples)
        )

        plan['changes'] = [{
            'field': 'brand',
            'action': act,
            'value': val,
            'replace_this': plan.get('replace_this', ''),
            'case_type': plan.get('case_type', 'TITLE_CASE')
        }]

        return {"plan_summary": resumo, "plan_json": plan}
    except Exception as e:
        return {"plan_summary": f"Erro: {str(e)}", "error": str(e)}
