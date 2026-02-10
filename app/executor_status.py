import requests
import json

def process_product_status(product, change, store_id, headers):
    """
    Executa alteração de STATUS (Publicado/Rascunho).
    """
    p_nuvem_id = product.nuvemshop_id 
    endpoint = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}"
    
    target_status = change.get('value') # ACTIVE ou INACTIVE
    
    # Traduz para a linguagem da Nuvemshop (published: true/false)
    is_published = True if target_status == 'ACTIVE' else False
    
    # Verifica estado atual no banco para evitar chamada inútil
    # (Assume que product.published é boolean no banco)
    current_published = getattr(product, 'published', None)
    
    # Se já está no estado desejado, pula (Opcional, mas economiza API)
    # Se quiser forçar sempre, remova o if abaixo.
    if current_published is not None and current_published == is_published:
        return False

    payload = {"published": is_published}

    try:
        r = requests.put(endpoint, json=payload, headers=headers)
        if r.status_code == 200:
            # Atualiza banco local
            product.published = is_published
            return True
    except:
        pass
        
    return False
