from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

# ==============================================================================
# 🛠️ DEFINIÇÃO DAS FERRAMENTAS
# ==============================================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_tags",
            "description": "Gerencia tags: Adiciona, Remove, Substitui, Padroniza ou Gera Auto-Tags.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_summary": {"type": "string"},
                    "find_product": {
                        "type": "object",
                        "properties": {
                            "title_contains": {"type": "string"},
                            "category_contains": {"type": "string"},
                            "tag_contains": {"type": "string"}
                        }
                    },
                    "action": {
                        "type": "string",
                        "enum": [
                            "ADD_TAG", 
                            "REMOVE_TAG", 
                            "REPLACE_TAG", 
                            "AUTO_TAG_FROM_TITLE", 
                            "STANDARDIZE_CASE",   # <--- NOVO
                            "REMOVE_BY_PATTERN"   # <--- NOVO
                        ],
                        "description": "Ação a realizar nas tags."
                    },
                    "tag_value": {
                        "type": "string",
                        "description": "Tag alvo ou padrão de texto para remover (ex: '2023')."
                    },
                    "replace_with": {"type": "string"},
                    "case_type": {
                        "type": "string",
                        "enum": ["UPPERCASE", "LOWERCASE", "TITLE_CASE"],
                        "description": "Formato para padronização (ex: 'Nike' é TITLE_CASE)."
                    }
                },
                "required": ["plan_summary", "find_product", "action"]
            }
        }
    }
]

# ==============================================================================
# 🧠 CÉREBRO DA IA
# ==============================================================================
SYSTEM_PROMPT = """
Você é o Especialista em Organização de Tags da Nuvemshop.

NOVAS HABILIDADES:
1. PADRONIZAR ("STANDARDIZE_CASE"):
   - Arruma a bagunça de maiúsculas/minúsculas.
   - Ex: "Deixar todas as tags em Maiúsculo" -> action="STANDARDIZE_CASE", case_type="UPPERCASE".
   - Ex: "Padronizar tags bonitas (Título)" -> action="STANDARDIZE_CASE", case_type="TITLE_CASE".

2. LIMPEZA POR PADRÃO ("REMOVE_BY_PATTERN"):
   - Remove qualquer tag que contenha um texto específico.
   - Ex: "Tirar tudo que tem 2023" -> action="REMOVE_BY_PATTERN", tag_value="2023".

HABILIDADES ANTIGAS:
- AUTO_TAG_FROM_TITLE (Extrair do título)
- ADD_TAG (Adicionar)
- REMOVE_TAG (Remover exata)
- REPLACE_TAG (Substituir)
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        plan = args
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = [f"• {p.name}" for p in products[:5]]

        act = plan.get('action')
        tag = plan.get('tag_value', '')
        case = plan.get('case_type', '')

        txt_acao = ""
        if act == 'ADD_TAG': txt_acao = f"🏷️ **Adicionar:** '{tag}'"
        elif act == 'REMOVE_TAG': txt_acao = f"🗑️ **Remover:** '{tag}'"
        elif act == 'AUTO_TAG_FROM_TITLE': txt_acao = "🤖 **Auto-Tag:** Extraindo do título."
        elif act == 'STANDARDIZE_CASE': txt_acao = f"✨ **Padronizar:** Tudo para {case}."
        elif act == 'REMOVE_BY_PATTERN': txt_acao = f"🧹 **Faxina:** Remover tags contendo '{tag}'."

        resumo = (
            f"📢 **Ação nas Tags:**\n{txt_acao}\n"
            f"🎯 **Produtos:** {affected_count}\n"
            f"📝 **Amostra:**\n" + "\n".join(samples)
        )
        
        plan['changes'] = [{
            'field': 'tags',
            'action': act,
            'value': tag,
            'replace_with': plan.get('replace_with', ''),
            'case_type': case
        }]

        return {
            "plan_summary": resumo,
            "plan_json": plan,
            "total_affected": affected_count
        }
    except Exception as e:
        return {"plan_summary": f"Erro: {str(e)}", "error": str(e)}
