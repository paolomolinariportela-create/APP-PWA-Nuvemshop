from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from .models import Produto

def get_strict_filtered_products(db: Session, store_id: str, plan: dict):
    """
    Busca ESTRITA/RIGOROSA para o Card de Relacionados.
    Aqui a ordem das palavras importa ("Air Jordan 6" não pega "Air ... Jordan ... 6").
    """
    query = db.query(Produto).filter(Produto.store_id == store_id)
    
    filters = plan.get('find_product', {})
    
    # === 1. Filtro por Título (RIGOROSO / SEQUENCIAL) ===
    if filters.get('title_contains'):
        search_text = filters['title_contains'].strip()
        if search_text:
            # AQUI ESTÁ A DIFERENÇA:
            # Usamos o texto inteiro no ILIKE. O banco busca a frase exata.
            # Não fazemos .split() aqui.
            query = query.filter(Produto.name.ilike(f"%{search_text}%"))

    # === 2. Filtro por Categoria (Mantém igual) ===
    if filters.get('category_contains'):
        cat_search = filters['category_contains'].strip()
        query = query.filter(Produto.categories_json.ilike(f"%{cat_search}%"))

    # === 3. Exclusões (Mantém igual) ===
    if filters.get('exclude_terms'):
        exclusions = filters['exclude_terms']
        if isinstance(exclusions, list):
            for term in exclusions:
                clean_term = term.strip()
                if clean_term:
                    query = query.filter(~Produto.name.ilike(f"%{clean_term}%"))

    return query.all()
