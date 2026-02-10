from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_status",
            "description": "Altera o status de publicação do produto (Ativo/Inativo).",
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
                        "enum": ["SET_STATUS"],
                        "description": "Ação única de definir status."
                    },
                    "value": {
                        "type": "string",
                        "enum": ["ACTIVE", "INACTIVE"],
                        "description": "ACTIVE = Publicado/Visível. INACTIVE = Rascunho/Oculto/Pausado."
                    }
                },
                "required": ["plan_summary", "find_product", "action", "value"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um OPERADOR DE STATUS (Liga/Desliga).
SUA FUNÇÃO É EXECUTAR COMANDOS LITERAIS.

REGRAS DE TRADUÇÃO:
1. "Ativar", "Publicar", "Mostrar", "Visível", "On" -> value="ACTIVE"
2. "Desativar", "Ocultar", "Pausar", "Rascunho", "Off" -> value="INACTIVE"

NÃO FAÇA PERGUNTAS. APENAS GERE O JSON.
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        plan = args
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = [f"• {p.name}" for p in products[:5]] if products else []

        val = plan.get('value', 'ACTIVE')
        
        txt_acao = ""
        if val == 'ACTIVE': txt_acao = "🟢 **ATIVAR (Publicar na Loja)**"
        else: txt_acao = "🔴 **DESATIVAR (Ocultar/Rascunho)**"

        resumo = (
            f"🤖 **Comando de Status:**\n{txt_acao}\n"
            f"🎯 **Alvo:** {affected_count} produtos\n"
            f"📝 **Amostra:**\n" + "\n".join(samples)
        )

        plan['changes'] = [{
            'field': 'status',
            'action': 'SET_STATUS',
            'value': val
        }]

        return {"plan_summary": resumo, "plan_json": plan}
    except Exception as e:
        return {"plan_summary": f"Erro: {str(e)}", "error": str(e)}
