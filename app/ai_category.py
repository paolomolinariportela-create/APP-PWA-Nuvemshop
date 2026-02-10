from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_categories",
            "description": "Gerencia categorias (Produtos e Estrutura).",
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
                    "category_rules": {
                        "type": "object",
                        "properties": {
                            "action": {
                                "type": "string", 
                                "enum": ["ADD", "REMOVE", "SET", "RENAME", "MOVE_TREE", "DELETE"],
                                "description": "Ações de Produto: ADD, REMOVE, SET. Ações de Estrutura: RENAME, MOVE_TREE, DELETE."
                            },
                            "target_category_name": {
                                "type": "string",
                                "description": "Nome da categoria alvo."
                            },
                            "parent_category_name": {
                                "type": "string",
                                "description": "Para MOVE_TREE: O novo pai. Para ADD/SET: O pai da subcategoria."
                            },
                            "new_name": {
                                "type": "string",
                                "description": "Para RENAME: O novo nome da categoria."
                            }
                        },
                        "required": ["action", "target_category_name"]
                    }
                },
                "required": ["plan_summary", "find_product", "category_rules"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um OPERADOR DE CATEGORIAS.

REGRAS DE PRODUTO (Afetam produtos):
1. "Coloca na categoria X" -> action: "ADD"
2. "Tira da categoria X" -> action: "REMOVE"

REGRAS DE ESTRUTURA (Afetam a árvore da loja):
3. "Renomeia a categoria X para Y" -> action: "RENAME", target="X", new_name="Y"
4. "Move a categoria X para dentro de Y" -> action: "MOVE_TREE", target="X", parent="Y"
5. "Apaga a categoria X" -> action: "DELETE", target="X"

NÃO GERE TEXTO. Apenas JSON.
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        # Busca produtos apenas se for ação de produto
        rules = args.get('category_rules', {})
        action = rules.get('action')
        is_structure = action in ["RENAME", "MOVE_TREE", "DELETE"]
        
        products = []
        if not is_structure:
            products = get_filtered_products(db, store_id, args)
        
        count = len(products)
        target = rules.get('target_category_name', 'Desconhecida')

        resumo = f"📂 **Gestão de Categorias**\n🛠️ **Ação:** {action} em '{target}'\n"
        
        if is_structure:
            resumo += "⚙️ **Tipo:** Alteração Estrutural (Loja)"
        else:
            resumo += f"🎯 **Alvo:** {count} produtos"

        return {
            "plan_summary": resumo,
            "command": {
                # Se for estrutural, target_ids vai vazio para não travar o filtro
                "target_ids": [p.nuvemshop_id for p in products if p.nuvemshop_id],
                "category_rules": rules,
                "find_product": args.get('find_product'),
                "changes": [{"field": "category", "action": "UPDATE", "value": target}]
            }
        }

    except Exception as e:
        return {"plan_summary": f"Erro técnico: {str(e)}", "error": str(e)}
