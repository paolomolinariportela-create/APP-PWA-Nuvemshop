from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_description",
            "description": "Executa alterações literais na descrição.",
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
                        "enum": [
                            "APPEND",       # Adicionar no Fim
                            "PREPEND",      # Adicionar no Início
                            "REPLACE",      # Substituir
                            "REMOVE_AFTER", # Cortar DEPOIS de...
                            "REMOVE_BEFORE",# Cortar ANTES de... (NOVO)
                            "REMOVE_IMAGES",# Remover tags <img> (NOVO)
                            "SET"           # Apagar tudo/Definir
                        ],
                        "description": "Ação técnica literal."
                    },
                    "value": {"type": "string"},
                    "replace_this": {"type": "string"},
                    "separator": {"type": "string", "description": "Palavra chave para os cortes."}
                },
                "required": ["plan_summary", "find_product", "action"]
            }
        }
    }
]

# --- ROBÔ LITERAL ---
SYSTEM_PROMPT = """
Você é um OPERADOR TÉCNICO.
SUA FUNÇÃO É EXTRAIR COMANDOS LITERAIS.

NOVAS HABILIDADES:
1. "Apagar tudo antes de X" -> action="REMOVE_BEFORE", separator="X"
2. "Remover imagens" / "Tirar fotos da descrição" -> action="REMOVE_IMAGES"

REGRAS ANTIGAS:
- APPEND/PREPEND: Adicionar texto exato.
- REPLACE: Troca exata.
- SET: Apagar tudo (value="") ou Definir (value="Texto").

NÃO INVENTE TEXTO. USE O QUE O USUÁRIO DEU.
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        plan = args
        products = get_filtered_products(db, store_id, plan)
        affected_count = len(products)
        samples = [f"• {p.name}" for p in products[:5]] if products else []

        act = plan.get('action')
        val = plan.get('value', '')
        sep = plan.get('separator', '')
        
        txt_acao = ""
        if act == 'APPEND': txt_acao = f"➕ **Adicionar (Fim):** '{val}'"
        elif act == 'PREPEND': txt_acao = f"⬅️ **Adicionar (Início):** '{val}'"
        elif act == 'REPLACE': txt_acao = f"🔄 **Trocar:** '{plan.get('replace_this')}' por '{val}'"
        elif act == 'REMOVE_AFTER': txt_acao = f"✂️ **Cortar:** Tudo DEPOIS de '{sep}'"
        elif act == 'REMOVE_BEFORE': txt_acao = f"✂️ **Cortar:** Tudo ANTES de '{sep}'"
        elif act == 'REMOVE_IMAGES': txt_acao = "🖼️ **Remover Imagens** (Manter texto)"
        elif act == 'SET': 
            if not val: txt_acao = "🗑️ **APAGAR TUDO**"
            else: txt_acao = f"✏️ **Definir:** '{val}'"

        resumo = (
            f"🤖 **Comando Técnico:**\n{txt_acao}\n"
            f"🎯 **Alvo:** {affected_count} produtos\n"
            f"📝 **Amostra:**\n" + "\n".join(samples)
        )

        plan['changes'] = [{
            'field': 'description',
            'action': act,
            'value': val,
            'replace_this': plan.get('replace_this', ''),
            'separator': sep
        }]

        return {"plan_summary": resumo, "plan_json": plan}
    except Exception as e:
        return {"plan_summary": f"Erro: {str(e)}", "error": str(e)}
