from sqlalchemy.orm import Session
from .models import Produto

def get_seo_products(db: Session, store_id: str, plan: dict):
    query = db.query(Produto).filter(Produto.store_id == store_id)
    filters = plan.get('find_product', {})
    
    # Busca Flexível (Nome)
    if filters.get('title_contains'):
        term = filters['title_contains'].strip()
        query = query.filter(Produto.name.ilike(f"%{term}%"))

    # Busca Flexível (Categoria)
    if filters.get('category_contains'):
        cat = filters['category_contains'].strip()
        query = query.filter(Produto.categories_json.ilike(f"%{cat}%"))

    return query.all()
