from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_bulk_action",
            "description": "Gera o comando JSON para alteração de títulos em massa.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "scope": {
                        "type": "string", 
                        "enum": ["PRODUCT"],
                        "description": "Títulos são sempre alterados no nível do PRODUTO."
                    },
                    "find_product": {
                        "type": "object", 
                        "properties": {
                            "title_contains": {"type": "string", "description": "Busca produtos que tenham este termo no título."},
                            "category_contains": {"type": "string", "description": "Busca produtos por categoria específica."}
                        }
                    },
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "enum": ["title"]}, 
                                "action": {
                                    "type": "string", 
                                    "enum": ["SET", "APPEND", "PREPEND", "REPLACE"],
                                    "description": "SET (Mudar tudo), APPEND (Fim), PREPEND (Início), REPLACE (Substituir termo)"
                                },
                                "value": {"type": "string", "description": "O TEXTO FINAL. Se for remover, envie string vazia."},
                                "replace_this": {"type": "string", "description": "Obrigatório para REPLACE: o termo exato a ser removido/trocado."}
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
Você é um Especialista em SEO e COPYWRITING para E-commerce.

⛔ PROIBIDO USAR CÓDIGO: NUNCA retorne código como "{{title.replace...}}". Você deve retornar APENAS os dados brutos.

REGRAS DE TÍTULO (IMPORTANTE):
1. **PARA REMOVER UMA PALAVRA:**
   - Use action: "REPLACE"
   - `replace_this`: "palavra a remover"
   - `value`: "" (String vazia)
   
2. **PARA TROCAR UMA PALAVRA:**
   - Use action: "REPLACE"
   - `replace_this`: "palavra antiga"
   - `value`: "palavra nova"

3. **PARA ADICIONAR:**
   - Use "APPEND" (fim) ou "PREPEND" (início).

EXEMPLO CORRETO PARA REMOVER "PROMOÇÃO":
{
  "action": "REPLACE",
  "replace_this": "Promoção",
  "value": ""
}
"""

def run_logic(db: Session, store_id: str, plan: Dict[str, Any]):
    try:
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = []
        
        change = plan['changes'][0]
        act_code = change['action']
        val_text = change['value']

        for p in products:
            if len(samples) < 5:
                # Mostra como o título FICARÁ para o cliente conferir
                novo_nome = p.name
                if act_code == "SET": novo_nome = val_text
                elif act_code == "APPEND": novo_nome = f"{p.name} {val_text}"
                elif act_code == "PREPEND": novo_nome = f"{val_text} {p.name}"
                elif act_code == "REPLACE": 
                    old = change.get('replace_this', '')
                    if old:
                        novo_nome = p.name.replace(old, val_text)
                    else:
                        novo_nome = p.name # Se não tiver o que trocar, mantém
                
                samples.append(f"• **De:** {p.name}\n  **Para:** {novo_nome}")

        # Tradução amigável
        hum_map = {
            "SET": f"Substituir título por: **'{val_text}'**",
            "APPEND": f"Adicionar ao final: **'{val_text}'**",
            "PREPEND": f"Adicionar ao início: **'{val_text}'**",
            "REPLACE": f"Remover/Trocar **'{change.get('replace_this')}'** por **'{val_text}'**"
        }
        
        filter_msg = "Todos os produtos"
        if plan['find_product'].get('category_contains'):
             filter_msg = f"Categoria: **{plan['find_product']['category_contains']}**"
        elif plan['find_product'].get('title_contains'):
             filter_msg = f"Filtro: **{plan['find_product']['title_contains']}**"

        resumo = (
            f"✅ **Plano de Edição de Título Gerado:**\n\n"
            f"📝 **Ação:** {hum_map.get(act_code, act_code)}\n"
            f"🎯 **Alvo:** {filter_msg}\n"
            f"🔢 **Total afetado:** {affected_count} produtos\n\n"
            f"👀 **Prévia das alterações:**\n" + "\n".join(samples)
        )

        return {
            "total_affected": affected_count,
            "samples": samples,
            "plan_summary": resumo
        }
    except Exception as e:
        return {"error": str(e)}
