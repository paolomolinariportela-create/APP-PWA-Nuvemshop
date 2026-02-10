from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

# --- SCHEMA (FERRAMENTA) ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_bulk_action",
            "description": "Gera a caixa de confirmação para o usuário aprovar a alteração.",
            "parameters": {
                "type": "object",
                "properties": {
                    "scope": {"type": "string", "enum": ["PRODUCT", "VARIANT"]},
                    "find_product": {"type": "object", "properties": {"title_contains": {"type": "string"}}},
                    "find_variant": {
                        "type": "object",
                        "properties": {
                            "attributes": {
                                "type": "array",
                                "items": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "string"}}}
                            }
                        }
                    },
                    "changes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "field": {"type": "string", "enum": ["price", "stock", "title", "tags", "promotional_price"]},
                                "action": {"type": "string", "enum": ["SET", "ADD", "INCREASE_PERCENT", "DECREASE_PERCENT", "INCREASE_FIXED", "DECREASE_FIXED", "APPEND"]},
                                "value": {"type": "string"}
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

# --- PROMPT DO SISTEMA (AJUSTADO PARA AÇÃO IMEDIATA) ---
def get_system_prompt(context: str):
    return f"""
    Você é um Operador Técnico. Contexto Atual: Editando {context.upper()}.
    
    SUA ÚNICA FUNÇÃO É GERAR COMANDOS.
    
    REGRAS DE COMPORTAMENTO:
    1. Se o usuário pedir uma alteração clara (ex: "Muda pra 649", "Aumenta 10%"), NÃO PERGUNTE "Posso prosseguir?".
    2. CHAME A FERRAMENTA 'propose_bulk_action' IMEDIATAMENTE. Isso vai mostrar a caixa de confirmação para o usuário.
    3. Se houver ambiguidade (ex: "Aumenta 10" sem dizer se é R$ ou %), aí sim pergunte.
    4. Se o usuário disser "Sim" ou "Confirmar", chame a ferramenta novamente com os mesmos dados.
    
    DICAS TÉCNICAS:
    - Para "Mudar para X", use action='SET', value='X'.
    - Para "Aumentar X", use action='INCREASE_FIXED' (se dinheiro) ou 'INCREASE_PERCENT' (se %).
    - Se o usuário falar uma Cor/Tamanho, preencha 'find_variant'.
    """

# --- LÓGICA DE EXECUÇÃO (SIMULAÇÃO) ---
def run_logic(db: Session, store_id: str, plan: Dict[str, Any]):
    try:
        products = get_filtered_products(db, store_id, plan)
        affected_count = 0
        samples = []
        
        variant_filters = plan.get('find_variant', {}).get('attributes', [])
        filter_desc = "TODAS as variantes"
        if variant_filters: filter_desc = f"apenas variantes {variant_filters[0]['value']}"

        for p in products:
            if plan.get('scope') == 'VARIANT':
                match_vars = 0
                if p.variants_json:
                    for v in p.variants_json:
                        match = True
                        if variant_filters:
                            for req in variant_filters:
                                found = False
                                for val in v.get('values', []):
                                    if str(req['value']).lower() in str(val.get('pt', '')).lower(): found = True
                                if not found: match = False
                        if match: match_vars += 1
                else: match_vars = 1 
                
                if match_vars > 0:
                    affected_count += match_vars
                    if len(samples) < 3: samples.append(f"{p.name} ({match_vars} vars)")
            else:
                affected_count += 1
                if len(samples) < 3: samples.append(p.name)

        # Tradução da ação para humano
        action_map = {
            "INCREASE_PERCENT": "Aumentar %",
            "DECREASE_PERCENT": "Diminuir %",
            "INCREASE_FIXED": "Aumentar R$",
            "DECREASE_FIXED": "Diminuir R$",
            "SET": "Definir Preço para R$",
            "ADD": "Adicionar ao Estoque"
        }
        try:
            act_code = plan['changes'][0]['action']
            act_human = action_map.get(act_code, act_code)
            val_human = plan['changes'][0]['value']
        except:
            act_human = "Alterar"
            val_human = "?"

        # ESSE RETORNO É O QUE O FRONTEND LÊ PARA MONTAR A CAIXINHA
        return {
            "total_affected": affected_count,
            "samples": samples,
            "plan_summary": f"{act_human} {val_human}"
        }
    except Exception as e:
        return {"error": str(e)}
