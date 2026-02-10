from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from .models import Produto
import re  # <--- Importante para a busca exata

def get_filtered_products(db: Session, store_id: str, plan: dict):
    # 1. Busca Inicial (Pega candidatos no Banco)
    query = db.query(Produto).filter(Produto.store_id == store_id)
    filters = plan.get('find_product', {})
    
    # Lista para acumular filtros de texto
    text_filters = []

    # --- FILTRO DE TÍTULO (LITERAL) ---
    if filters.get('title_contains'):
        search_term = filters['title_contains'].strip()
        # Busca no banco usando LIKE normal (traz Jordan 3 e Jordan 36)
        query = query.filter(Produto.name.ilike(f"%{search_term}%"))
        text_filters.append(search_term)

    # --- FILTRO DE CATEGORIA ---
    if filters.get('category_contains'):
        cat_search = filters['category_contains'].strip()
        query = query.filter(Produto.categories_json.ilike(f"%{cat_search}%"))

    # --- EXCLUSÕES ---
    if filters.get('exclude_terms'):
        for term in filters['exclude_terms']:
            query = query.filter(~Produto.name.ilike(f"%{term.strip()}%"))

    # Pega os candidatos brutos
    candidates = query.all()
    
    # 2. Peneira Fina (Refinamento Literal em Python)
    # Aqui removemos o "Jordan 36" se a busca for "Jordan 3"
    final_products = []
    
    if text_filters:
        for p in candidates:
            match_all = True
            name_clean = (p.name or "").lower()
            
            for term in text_filters:
                term_clean = term.lower()
                # Cria um padrão que exige que o termo seja uma PALAVRA INTEIRA
                # \b = borda de palavra (espaço, fim de linha, pontuação)
                # Assim, "3" não casa com "36"
                pattern = r"(?<!\w)" + re.escape(term_clean) + r"(?!\w)"
                
                if not re.search(pattern, name_clean):
                    match_all = False
                    break
            
            if match_all:
                final_products.append(p)
    else:
        final_products = candidates

    print(f"🔎 [UTILS] Buscando '{filters.get('title_contains', '')}' -> Banco: {len(candidates)} | Literal: {len(final_products)}")
    
    return final_products

def calculate_new_value(current_val, action, target_val):
    # (Mantém a lógica matemática igual estava...)
    try:
        curr = float(current_val or 0)
        tgt = float(target_val)
        if action == "SET": return tgt
        if action == "INCREASE_PERCENT": return curr + (curr * tgt / 100)
        if action == "DECREASE_PERCENT": return curr - (curr * tgt / 100)
        if action == "INCREASE_FIXED": return curr + tgt
        if action == "DECREASE_FIXED": return curr - tgt
        if action == "ADD": return curr + tgt 
        return curr
    except:
        return current_val
