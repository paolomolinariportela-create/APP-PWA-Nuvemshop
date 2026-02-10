from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_bulk_action",
            "description": "Gera o comando JSON para alteração de ESTOQUE.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "scope": {"type": "string", "enum": ["VARIANT", "PRODUCT"]},
                    "find_product": {
                        "type": "object", 
                        "properties": {
                            "title_contains": {"type": "string", "description": "O nome MAIS COMPLETO possível que o usuário forneceu."},
                            "category_contains": {"type": "string"},
                            "exclude_terms": {"type": "array", "items": {"type": "string"}}
                        }
                    },
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "enum": ["stock"]}, 
                                "action": {"type": "string", "enum": ["SET", "ADD"]},
                                "value": {"type": "integer"}
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
Você é um Gerente de Estoque de Alta Precisão.

⛔ REGRAS DE BUSCA (CRÍTICO):
1. O usuário vai fornecer nomes longos e específicos (Ex: "Nike LeBron Witness 8 Armory Navy").
2. Você deve copiar o nome **COMPLETO** para o campo `title_contains`.
3. NÃO RESUMA. Se você tirar "Armory Navy", vai alterar 50 tênis errados.
4. Apenas remova palavras de conexão inúteis: "o produto", "estoque do", "alterar", "para".

⛔ REGRAS DE ESTOQUE:
- "Zerar" -> action: "SET", value: 0
- "Mudar para 12" -> action: "SET", value: 12
- "Adicionar 5" -> action: "ADD", value: 5
"""

def run_logic(db: Session, store_id: str, plan: Dict[str, Any]):
    try:
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = []
        
        change = plan['changes'][0]
        val_int = int(change['value']) 

        for p in products:
            if len(samples) < 5:
                samples.append(f"• {p.name}")

        acao_txt = f"Definir estoque para {val_int}" if change['action'] == "SET" else f"Somar/Subtrair {val_int} un."
        
        # Lógica de Alerta de Precisão
        aviso = ""
        termo_usado = plan['find_product'].get('title_contains', '')
        
        if affected_count > 5:
            aviso = (f"\n⚠️ **CUIDADO:** Encontrei {affected_count} produtos com '{termo_usado}'. "
                     "Verifique se você não está alterando modelos diferentes (Ex: cores variadas). "
                     "Se quiser ser mais específico, digite o nome completo da cor.")
        elif affected_count == 0:
            aviso = f"\n❌ **Erro:** Nenhum produto encontrado com o nome exato '{termo_usado}'. Tente remover uma ou duas palavras."

        resumo = (
            f"✅ **Planejamento de Estoque:**\n"
            f"📦 Ação: {acao_txt}\n"
            f"🎯 Filtro usado: '{termo_usado}'\n"
            f"🔢 Produtos Encontrados: {affected_count}\n"
            f"Exemplos:\n" + "\n".join(samples) + aviso
        )

        return {"total_affected": affected_count, "samples": samples, "plan_summary": resumo}
    except Exception as e:
        return {"error": str(e)}
