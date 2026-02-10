import re
from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_bulk_action",
            "description": "Gera comando para alterar textos.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "scope": {"type": "string", "enum": ["PRODUCT"]},
                    "find_product": {
                        "type": "object", 
                        "properties": {
                            "title_contains": {"type": "string"},
                            "category_contains": {"type": "string"},
                            "exclude_terms": {"type": "array", "items": {"type": "string"}}
                        }
                    },
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "enum": ["title", "description"]}, 
                                
                                # ADICIONADO: CLEAN_PATTERN
                                "action": {
                                    "type": "string", 
                                    "enum": ["SET", "APPEND", "PREPEND", "REPLACE", "FORMAT", "REMOVE_AFTER", "REMOVE_BEFORE", "CLEAN_PATTERN"],
                                },
                                
                                # NOVO: ESPECÍFICO PARA LIMPEZA
                                "pattern_type": {
                                    "type": "string",
                                    "enum": ["PARENTHESES", "BRACKETS", "CURLY_BRACES", "ALL_SYMBOLS"],
                                    "description": "PARENTHESES=(), BRACKETS=[], CURLY_BRACES={}, ALL_SYMBOLS=Tudo isso."
                                },

                                "format_type": {"type": "string", "enum": ["UPPERCASE", "LOWERCASE", "TITLE_CASE", "CAPITALIZE"]},
                                "value": {"type": "string"},
                                "replace_this": {"type": "string"},
                                "separator": {"type": "string"}
                            },
                            "required": ["field", "action"]
                        }
                    }
                },
                "required": ["scope", "find_product", "changes"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um Especialista em Edição de Texto.

⛔ REGRAS DE LIMPEZA (CLEAN_PATTERN):
Se o usuário pedir: "Tire tudo entre parênteses", "Remova códigos em colchetes", "Limpe referências".
Use `action`: "CLEAN_PATTERN" e escolha o `pattern_type`:
- "PARENTHESES" -> Remove (texto)
- "BRACKETS" -> Remove [texto]
- "ALL_SYMBOLS" -> Remove qualquer coisa entre (), [] ou {}.

⛔ OUTRAS REGRAS (MANTIDAS):
- Formatação: FORMAT
- Corte: REMOVE_AFTER / REMOVE_BEFORE
- Substituição: REPLACE
"""

def run_logic(db: Session, store_id: str, plan: Dict[str, Any]):
    try:
        products = get_filtered_products(db, store_id, plan)
        
        real_changes = []
        samples = []
        change = plan['changes'][0]

        for p in products:
            original = p.name or ""
            novo = original
            
            # === LÓGICA DE LIMPEZA DE PADRÕES (NOVO) ===
            if change['action'] == "CLEAN_PATTERN":
                ptype = change.get('pattern_type')
                # Remove conteúdo e os próprios símbolos
                if ptype == "PARENTHESES" or ptype == "ALL_SYMBOLS":
                    novo = re.sub(r'\([^)]*\)', '', novo) # Remove (...)
                
                if ptype == "BRACKETS" or ptype == "ALL_SYMBOLS":
                    novo = re.sub(r'\[[^]]*\]', '', novo) # Remove [...]
                
                if ptype == "CURLY_BRACES" or ptype == "ALL_SYMBOLS":
                    novo = re.sub(r'\{[^}]*\}', '', novo) # Remove {...}
                
                # Remove espaços duplos que sobram após a limpeza
                novo = re.sub(r'\s+', ' ', novo).strip()

            # === LÓGICA ANTERIOR (MANTIDA) ===
            elif change['action'] == "REMOVE_AFTER":
                sep = change.get('separator')
                if sep and sep in original: novo = original.split(sep)[0].strip()
            
            elif change['action'] == "REMOVE_BEFORE":
                sep = change.get('separator')
                if sep and sep in original:
                    parts = original.split(sep, 1)
                    if len(parts) > 1: novo = parts[1].strip()

            elif change['action'] == "FORMAT":
                fmt = change.get('format_type')
                if fmt == "UPPERCASE": novo = original.upper()
                elif fmt == "LOWERCASE": novo = original.lower()
                elif fmt == "TITLE_CASE": novo = original.title()
                elif fmt == "CAPITALIZE": novo = original.capitalize()
            
            elif change['action'] == "SET": novo = change['value']
            elif change['action'] == "APPEND": novo = f"{original} {change['value']}"
            elif change['action'] == "PREPEND": novo = f"{change['value']} {original}"
            elif change['action'] == "REPLACE": 
                old = change.get('replace_this', '')
                val = change.get('value', '')
                if old and old in original: novo = original.replace(old, val)

            if novo != original:
                real_changes.append(p)
                if len(samples) < 5:
                    samples.append(f"• {original} \n  ✨ {novo}")

        affected_count = len(real_changes)

        acao_humana = change['action']
        if change['action'] == "CLEAN_PATTERN":
            acao_humana = f"Limpar padrões: {change.get('pattern_type')}"
        elif "REMOVE" in change['action']:
            acao_humana = f"Cortar texto usando: '{change.get('separator')}'"

        aviso = ""
        if len(products) > 0 and affected_count == 0:
            aviso = "\n⚠️ **Nenhum produto continha o padrão para limpar.**"
        elif affected_count == 0:
            aviso = "\n⚠️ **Nenhum produto encontrado.**"

        resumo = (
            f"✅ **Planejamento de Texto:**\n"
            f"📝 Ação: {acao_humana}\n"
            f"🔍 Encontrados: {len(products)}\n"
            f"🧹 **Serão Limpos: {affected_count}**\n"
            f"Exemplos:\n" + "\n".join(samples) + aviso
        )

        return {"total_affected": affected_count, "samples": samples, "plan_summary": resumo}
    except Exception as e:
        return {"error": str(e)}
