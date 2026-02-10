import requests
import json
from decimal import Decimal

def process_logistics_update(product, change, store_id, headers):
    """
    Executa alterações de LOGÍSTICA:
    - SET_DIMENSIONS: Define valor fixo.
    - ADD_TO_DIMENSIONS: Soma valor ao atual (útil para embalagem).
    - SET_FREE_SHIPPING: Liga/Desliga frete grátis.
    """
    p_nuvem_id = product.nuvemshop_id 
    endpoint_get = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}/variants"
    
    try:
        r = requests.get(endpoint_get, headers=headers)
        if r.status_code != 200: return False
        variants = r.json()
    except:
        return False

    action = change['action']
    dims = change.get('dimensions', {})
    free_shipping = change.get('free_shipping')
    
    updated_any = False

    for v in variants:
        variant_id = v['id']
        payload = {}
        
        # --- LÓGICA DE FRETE GRÁTIS ---
        if action == 'SET_FREE_SHIPPING':
            current_free = v.get('free_shipping', False)
            if current_free != free_shipping:
                payload['free_shipping'] = free_shipping

        # --- LÓGICA DE DIMENSÕES (Set ou Add) ---
        elif action in ['SET_DIMENSIONS', 'ADD_TO_DIMENSIONS']:
            for key, val_str in dims.items():
                # key: weight, height, width, depth
                current_val = v.get(key)
                
                # Garante que seja número para cálculo
                try:
                    current_num = Decimal(str(current_val)) if current_val else Decimal('0')
                    target_num = Decimal(str(val_str))
                except: continue

                new_val = target_num
                
                if action == 'ADD_TO_DIMENSIONS':
                    new_val = current_num + target_num
                    # Evita valores negativos
                    if new_val < 0: new_val = Decimal('0')

                # Formatação para API (String)
                final_val_str = str(new_val)
                
                if str(current_val) != final_val_str:
                    payload[key] = final_val_str

        # Se tiver algo para atualizar, envia
        if payload:
            endpoint_put = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}/variants/{variant_id}"
            try:
                r_put = requests.put(endpoint_put, json=payload, headers=headers)
                if r_put.status_code == 200:
                    updated_any = True
            except: pass

    return updated_any
