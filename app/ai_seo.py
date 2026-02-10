import re
from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils_seo import get_seo_products

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_seo",
            "description": "Otimiza SEO (Títulos, Tags) com limpeza e formatação.",
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
                    "modifications": {
                        "type": "object",
                        "properties": {
                            # --- OPÇÕES DE TEXTO LITERAL ---
                            "set_seo_title": {"type": "string", "description": "Define o Título SEO EXATO. Sem completar."},
                            "set_seo_description": {"type": "string", "description": "Define a Descrição SEO EXATA."},
                            
                            # --- OPÇÕES DE EDIÇÃO ---
                            "title_prefix": {"type": "string"},
                            "title_suffix": {"type": "string"},
                            "add_tags": {"type": "array", "items": {"type": "string"}},
                            "clean_pattern": {
                                "type": "string",
                                "enum": ["PARENTHESES", "BRACKETS", "CURLY_BRACES", "ALL_SYMBOLS"]
                            },
                            "format_type": {
                                "type": "string",
                                "enum": ["UPPERCASE", "LOWERCASE", "TITLE_CASE", "CAPITALIZE"]
                            }
                        }
                    }
                },
                "required": ["plan_summary", "find_product", "modifications"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um ESPECIALISTA EM SEO TÉCNICO.
Sua função é converter pedidos em regras de modificação JSON.

⚠️ REGRAS CRÍTICAS:
1. Se o usuário fornecer um título específico (ex: "Use este título: X"), use o campo `set_seo_title`.
2. JAMAIS invente texto para completar 70 caracteres. Use APENAS o texto fornecido.
3. Se o usuário pedir para limpar ou formatar, use `clean_pattern` ou `format_type`.

NÃO GERE TEXTO CONVERSACIONAL. Apenas o JSON da tool.
"""

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        products = get_seo_products(db, store_id, args)
        mods = args.get('modifications', {})
        count = len(products)
        samples = []
        
        # --- SIMULAÇÃO VISUAL ---
        for p in products[:5]: 
            # Começa com o nome original se não houver um título setado
            if mods.get('set_seo_title'):
                novo = mods['set_seo_title'] # Usa o texto LITERAL do usuário
            else:
                novo = p.name or ""
            
            # Aplica limpeza/formatação se solicitado
            if mods.get('clean_pattern'):
                ptype = mods['clean_pattern']
                if ptype in ["PARENTHESES", "ALL_SYMBOLS"]: novo = re.sub(r'\([^)]*\)', '', novo)
                if ptype in ["BRACKETS", "ALL_SYMBOLS"]: novo = re.sub(r'\[[^]]*\]', '', novo)
                if ptype in ["CURLY_BRACES", "ALL_SYMBOLS"]: novo = re.sub(r'\{[^}]*\}', '', novo)
                novo = re.sub(r'\s+', ' ', novo).strip()

            if mods.get('format_type'):
                fmt = mods['format_type']
                if fmt == "UPPERCASE": novo = novo.upper()
                elif fmt == "LOWERCASE": novo = novo.lower()
                elif fmt == "TITLE_CASE": novo = novo.title()
                elif fmt == "CAPITALIZE": novo = novo.capitalize()

            if mods.get('title_prefix') and not mods.get('set_seo_title'):
                if not novo.startswith(mods['title_prefix']): novo = f"{mods['title_prefix']}{novo}"
            
            if mods.get('title_suffix') and not mods.get('set_seo_title'):
                if not novo.endswith(mods['title_suffix']): novo = f"{novo}{mods['title_suffix']}"

            # Mostra na amostra
            tags_msg = f" (+Tags: {mods['add_tags']})" if mods.get('add_tags') else ""
            samples.append(f"• {p.name}\n  ✨ SEO: {novo}{tags_msg}")

        # --- RESUMO ---
        acao_desc = "Otimização SEO"
        if mods.get('set_seo_title'): acao_desc = "Definir Título SEO Exato"
        
        resumo = (
            f"✅ **Planejamento SEO:**\n"
            f"🎯 **Alvo:** {count} produtos\n"
            f"🛠️ **Ação:** {acao_desc}\n"
            f"📝 **Amostra:**\n" + "\n".join(samples)
        )
        
        return {
            "plan_summary": resumo,
            "command": {
                "target_ids": [p.nuvemshop_id for p in products if p.nuvemshop_id],
                "modifications": mods,
                # Compatibilidade Frontend
                "find_product": args.get('find_product'),
                "changes": [{"field": "seo", "action": "UPDATE", "value": "SEO Changes"}]
            }
        }

    except Exception as e:
        return {"plan_summary": f"Erro técnico: {str(e)}", "error": str(e)}
