from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc
from .models import Produto

# --- SCHEMA (FERRAMENTA) ---
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consult_database",
            "description": "Busca produtos no banco. Use para responder sobre preços, estoque, ou encontrar produtos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_term": {"type": "string", "description": "Nome/Categoria. Vazio = todos."},
                    "sort_by": {"type": "string", "enum": ["price", "stock", "name"], "description": "Campo para ordenar."},
                    "order": {"type": "string", "enum": ["asc", "desc"], "description": "asc=Crescente, desc=Decrescente."},
                    "limit": {"type": "integer", "description": "Limite de itens (max 20)."}
                },
                "required": []
            }
        }
    }
]

# --- PROMPT DO SISTEMA ---
SYSTEM_PROMPT = """
Você é um Analista de E-commerce Senior.
Sua função é ler os dados do banco e EXPLICAR para o dono da loja.

DICAS DE USO DO BANCO:
- Para "mais barato": sort_by='price', order='asc'.
- Para "mais caro": sort_by='price', order='desc'.
- Para "maior estoque": sort_by='stock', order='desc'.
- Nunca invente dados. Use a ferramenta 'consult_database'.
"""

# --- LÓGICA DE EXECUÇÃO ---
def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    query = db.query(Produto).filter(Produto.store_id == store_id)
    
    # 1. Filtro
    term = args.get('search_term')
    if term:
        t = f"%{term}%"
        query = query.filter(or_(Produto.name.ilike(t), Produto.categories_json.ilike(t), Produto.variants_json.ilike(t)))
    
    # 2. Ordenação
    sort_col = args.get('sort_by', 'name')
    order_dir = args.get('order', 'asc')
    
    col_map = {'price': Produto.price, 'stock': Produto.stock, 'name': Produto.name}
    column = col_map.get(sort_col, Produto.name)

    if order_dir == 'desc': query = query.order_by(desc(column))
    else: query = query.order_by(asc(column))

    # 3. Busca
    total = query.count()
    if total == 0: return f"BANCO: Nenhum produto encontrado para '{term}'."
    
    limit = min(args.get('limit', 5), 20)
    products = query.limit(limit).all()
    
    details = [f"- {p.name} | R$ {p.price:.2f} | Estoque: {p.stock}" for p in products]
    
    return (f"BANCO: Encontrei {total} produtos.\n"
            f"Top {len(products)} ordenados por {sort_col} ({order_dir}):\n" + "\n".join(details))
