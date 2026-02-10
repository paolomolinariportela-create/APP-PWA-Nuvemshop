import requests
import json
import re

def process_product_code(product, change, store_id, headers):
    """
    Executa alterações de SKU e BARCODE nas VARIANTES do produto.
    Funcionalidades: Set, Clear, Generate (ID), Inherit (Pai), Sanitize (Limpeza).
    """
    p_nuvem_id = product.nuvemshop_id 
    # 1. Busca as variantes atuais na API (para garantir integridade)
    endpoint_get = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}/variants"
    
    try:
        r = requests.get(endpoint_get, headers=headers)
        if r.status_code != 200: return False
        variants = r.json()
    except:
        return False

    action = change['action']
    target_field = change['field'] # 'sku' ou 'barcode'
    target_value = change.get('value', '')
    
    updated_any = False

    # Tenta obter um SKU "Pai" (baseado no produto ou na primeira variante)
    parent_sku_base = ""
    if variants:
        # Pega o SKU da primeira variante como "base" se não tiver um explícito no produto
        parent_sku_base = variants[0].get('sku', '') or f"PROD-{p_nuvem_id}"

    # 2. Loop pelas variantes
    for v in variants:
        variant_id = v['id']
        current_val = v.get(target_field, '') or ""
        new_val = current_val

        # --- LÓGICA DE CÓDIGO ---
        if action == 'CLEAR_CODE':
            new_val = "" # Limpar
            
        elif action == 'SET_SKU' and target_field == 'sku':
            new_val = target_value 
            
        elif action == 'SET_BARCODE' and target_field == 'barcode':
            new_val = target_value
            
        elif action == 'GENERATE_SKU_FROM_ID' and target_field == 'sku':
            # Gera SKU único: {ID_PRODUTO}-{ID_VARIANTE}
            new_val = f"{p_nuvem_id}-{variant_id}"

        elif action == 'INHERIT_SKU_FROM_PARENT' and target_field == 'sku':
            # Herda do pai + ID da variante para garantir unicidade
            # Ex: CAMISA-AZUL-12345
            clean_parent = parent_sku_base.split('-')[0] # Pega só o prefixo antes do traço se houver
            new_val = f"{clean_parent}-{variant_id}"

        elif action == 'SANITIZE_CODES':
            # Remove tudo que NÃO for letra ou número (mantém apenas alfanumérico)
            # Ex: "REF 123-A *" -> "REF123A"
            if current_val:
                new_val = re.sub(r'[^a-zA-Z0-9]', '', current_val).upper()

        # 3. Envia atualização se mudou
        # (Força envio se for CLEAR/GENERATE/SANITIZE para garantir)
        if str(new_val) != str(current_val) or action in ['CLEAR_CODE', 'GENERATE_SKU_FROM_ID', 'SANITIZE_CODES']:
            payload = {target_field: new_val}
            endpoint_put = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}/variants/{variant_id}"
            try:
                r_put = requests.put(endpoint_put, json=payload, headers=headers)
                if r_put.status_code == 200:
                    updated_any = True
            except: pass

    return updated_any
