from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_demographics",
            "description": "Gerencia Dados Técnicos (Google Shopping) e Fiscais (NCM).",
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
                        "enum": ["SET_DEMOGRAPHICS", "CLEAR_DEMOGRAPHICS"],
                        "description": "Definir ou Limpar dados técnicos."
                    },
                    "mpn": {
                        "type": "string",
                        "description": "Manufacturer Part Number (Código do Fabricante)."
                    },
                    "ncm": {
                        "type": "string",
                        "description": "Código NCM (Fiscal) - Ex: 6109.10.00."
                    },
                    "gender": {
                        "type": "string",
                        "enum": ["male", "female", "unisex"],
                        "description": "Gênero (Masculino, Feminino, Unissex)."
                    },
                    "age_group": {
                        "type": "string",
                        "enum": ["adult", "kids", "toddler", "infant"],
                        "description": "Faixa Etária."
                    }
                },
                "required": ["plan_summary", "find_product", "action"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um ESPECIALISTA TÉCNICO E FISCAL (Google Shopping & NCM).
SUA FUNÇÃO É PADRONIZAR DADOS OBRIGATÓRIOS.

CAMPOS:
1. NCM (Fiscal): Obrigatório para Nota Fiscal (ex: 6109.10.00).
2. MPN, Gender, Age Group: Obrigatórios para Google Shopping.

COMANDOS:
- "Definir NCM 1234.56.78 para todos" -> action="SET_DEMOGRAPHICS", ncm="1234.56.78"
- "Colocar gênero unissex e adulto" -> action="SET_DEMOGRAPHICS", gender="unisex", age_group="adult"
- "Limpar MPN dos produtos" -> action="CLEAR_DEMOGRAPHICS", mpn="true"

TRADUÇÃO GÊNERO:
- Homem -> "male"
- Mulher -> "female"
- Unissex -> "unisex"
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        plan = args
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = [f"• {p.name}" for p in products[:5]] if products else []

        mpn = plan.get('mpn')
        ncm = plan.get('ncm')
        gender = plan.get('gender')
        age = plan.get('age_group')
        action = plan.get('action')
        
        detalhes = []
        if action == 'CLEAR_DEMOGRAPHICS':
            detalhes.append("🗑️ Limpar dados selecionados")
        else:
            if ncm: detalhes.append(f"NCM='{ncm}'")
            if mpn: detalhes.append(f"MPN='{mpn}'")
            if gender: detalhes.append(f"Gênero='{gender}'")
            if age: detalhes.append(f"Faixa Etária='{age}'")
        
        resumo = (
            f"🏷️ **Dados Técnicos/Fiscais:** {', '.join(detalhes)}\n"
            f"🎯 **Alvo:** {affected_count} produtos\n"
            f"📝 **Amostra:**\n" + "\n".join(samples)
        )

        plan['changes'] = [{
            'field': 'demographics',
            'action': action,
            'mpn': mpn,
            'ncm': ncm,
            'gender': gender,
            'age_group': age
        }]

        return {"plan_summary": resumo, "plan_json": plan}
    except Exception as e:
        return {"plan_summary": f"Erro: {str(e)}", "error": str(e)}
