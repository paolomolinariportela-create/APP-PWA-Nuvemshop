from typing import Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import and_ # Importante para a busca combinada
from .models import Produto
from .utils_related import get_strict_filtered_products 

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "manage_related",
            "description": "Gerencia produtos relacionados (Cross-Sell).",
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
                        "enum": ["ADD_RELATED", "SET_RELATED", "CLEAR_RELATED"],
                        "description": "Ação a ser executada."
                    },
                    "related_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Lista de IDs."
                    },
                    "related_names": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Palavras-chave para encontrar produtos (Ex: 'Air Jordan 6')."
                    }
                },
                "required": ["plan_summary", "find_product", "action"]
            }
        }
    }
]

SYSTEM_PROMPT = """
Você é um especialista em Cross-sell. 
Se o usuário pedir para vincular produtos com termos como "Air Jordan 6", 
coloque "Air Jordan 6" na lista 'related_names'.
"""

def find_ids_by_keywords(db: Session, store_id: str, keywords: List[str]) -> List[int]:
    """
    Busca Inteligente: Encontra produtos que contenham TODAS as palavras do termo.
    Ex: 'Air Jordan 6' -> Encontra 'Air Jordan Retro 6' e 'Jordan 6 Air'.
    """
    found_ids = []
    if not keywords: return []
    
    print(f"🔎 [DEBUG] Palavras-chave recebidas: {keywords}")
    
    for term in keywords:
        # Quebra a frase em palavras ("Air", "Jordan", "6")
        words = term.strip().split()
        if not words: continue
        
        # Cria filtros: O nome deve conter Palavra 1 E Palavra 2 E Palavra 3...
        filters = [Produto.name.ilike(f"%{w}%") for w in words]
        
        # Busca no banco
        results = db.query(Produto).filter(
            Produto.store_id == store_id,
            and_(*filters) # Exige todas as palavras
        ).limit(20).all() # Traz até 20 candidatos
        
        if results:
            print(f"   ✅ Termo '{term}' encontrou {len(results)} produtos.")
            for p in results:
                # Debug dos nomes encontrados
                # print(f"      -> {p.name}")
                if p.nuvemshop_id:
                    found_ids.append(int(p.nuvemshop_id))
        else:
            print(f"   ❌ Nada encontrado combinando: {words}")
            
    return found_ids

def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    # 1. Pega as palavras-chave
    target_keywords = args.get('related_names', [])
    
    try:
        # 2. Busca o PRODUTO PAI (Ex: Hare)
        products = get_strict_filtered_products(db, store_id, args)
        
        # 3. Busca os RELACIONADOS (Ex: Air Jordan 6...)
        ids_to_link = args.get('related_ids') or []
        
        if target_keywords:
            found = find_ids_by_keywords(db, store_id, target_keywords)
            if found:
                ids_to_link.extend(found)
        
        # 4. Remove duplicatas e o próprio pai da lista
        final_ids_pool = []
        # Lista de IDs dos produtos pai para não linkar neles mesmos
        parent_ids = [int(p.nuvemshop_id) for p in products if p.nuvemshop_id]
        
        for pid in ids_to_link:
            if str(pid).isdigit():
                ipid = int(pid)
                # Regra: Não pode ser o pai
                if ipid not in parent_ids:
                    final_ids_pool.append(ipid)
        
        # 5. Limite de 8 da Nuvemshop
        final_ids = list(set(final_ids_pool))[:8]
        
        # 6. Atualiza o comando
        args['related_ids'] = final_ids
        args['related_names'] = [] # Limpa para o front não travar

        args['changes'] = [{
            'field': 'related',
            'action': args.get('action'),
            'related_ids': final_ids 
        }]

        # Resumo
        count_prods = len(products)
        count_links = len(final_ids)
        prod_names = [p.name for p in products[:3]]
        
        resumo = f"✅ **Sucesso!** Encontrei {count_links} modelos relacionados para vincular em: {', '.join(prod_names)}..."
        
        if not final_ids and args.get('action') != 'CLEAR_RELATED':
            if target_keywords:
                resumo = f"⚠️ **Atenção:** Não encontrei produtos com as palavras '{target_keywords[0]}'. Tente termos mais simples."
            else:
                resumo = "⚠️ **Atenção:** Nenhum produto selecionado."

        return {
            "plan_summary": resumo,
            "command": args
        }
        
    except Exception as e:
        print(f"🔥 [ERRO] {str(e)}")
        return {"plan_summary": f"Erro Técnico: {str(e)}", "error": str(e)}
