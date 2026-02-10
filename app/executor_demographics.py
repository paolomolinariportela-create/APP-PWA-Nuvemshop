import requests
import json

def process_demographics_update(product, change, store_id, headers):
    """
    Atualiza MPN, NCM, GENDER e AGE_GROUP nas variantes.
    """
    p_nuvem_id = product.nuvemshop_id 
    endpoint_get = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}/variants"
    
    try:
        r = requests.get(endpoint_get, headers=headers)
        if r.status_code != 200: return False
        variants = r.json()
    except:
        return False

    action = change.get('action')
    target_mpn = change.get('mpn')
    target_ncm = change.get('ncm')
    target_gender = change.get('gender')
    target_age = change.get('age_group')
    
    updated_any = False

    for v in variants:
        variant_id = v['id']
        payload = {}
        
        if action == 'CLEAR_DEMOGRAPHICS':
            # Se a intenção é limpar, mandamos string vazia ou null
            # Verifica quais campos foram solicitados para limpeza (geralmente vêm como string "true" ou valor no argumento)
            # Para simplificar: se o usuário pediu CLEAR e passou "mpn" no argumento, limpamos.
            # Mas como o JSON vem estruturado, se o valor for None, ignoramos.
            # Vamos assumir que CLEAR limpa tudo que não for None no plano.
            pass # Lógica simplificada abaixo
            
        # Lógica de SET (Define ou Limpa se for string vazia)
        # NCM
        if target_ncm is not None:
            if str(v.get('ncm', '')) != str(target_ncm):
                payload['ncm'] = target_ncm
        
        # MPN
        if target_mpn is not None:
            if str(v.get('mpn', '')) != str(target_mpn):
                payload['mpn'] = target_mpn

        # GENDER
        if target_gender is not None:
            if str(v.get('gender', '')) != str(target_gender):
                payload['gender'] = target_gender

        # AGE GROUP
        if target_age is not None:
            if str(v.get('age_group', '')) != str(target_age):
                payload['age_group'] = target_age
        
        # Se tiver atualização, envia
        if payload:
            endpoint_put = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}/variants/{variant_id}"
            try:
                r_put = requests.put(endpoint_put, json=payload, headers=headers)
                if r_put.status_code == 200:
                    updated_any = True
            except: pass

    return updated_any
