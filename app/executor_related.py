import requests
import json

def process_related_update(product, change, store_id, headers):
    """
    EXECUTOR ROBUSTO: Grava os dados na Nuvemshop com segurança.
    """
    p_id = product.nuvemshop_id
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_id}"
    
    # 1. Prepara os IDs
    action = change.get('action', 'SET_RELATED')
    raw_ids = change.get('related_ids') or []
    new_ids = [int(x) for x in raw_ids if str(x).isdigit()]
    
    current_ids = []
    
    # 2. Se for ADICIONAR, busca os atuais primeiro
    if action == 'ADD_RELATED':
        try:
            r_get = requests.get(url, headers=headers)
            if r_get.status_code == 200:
                current_data = r_get.json()
                raw_current = current_data.get('related_products', [])
                current_ids = [int(x) for x in raw_current]
        except Exception as e:
            print(f"   ⚠️ Erro ao ler atuais: {e}")

    # 3. Mescla e Limita a 8
    final_ids = []
    if action == 'CLEAR_RELATED':
        final_ids = []
    elif action == 'SET_RELATED':
        final_ids = new_ids
    elif action == 'ADD_RELATED':
        # Mantém a ordem: Novos primeiro
        merged = new_ids + current_ids
        seen = set()
        final_ids = [x for x in merged if not (x in seen or seen.add(x))]

    final_ids = final_ids[:8]
    
    # 4. Envia para a Nuvemshop
    payload = {"related_products": final_ids}
    print(f"📡 [ENVIO] Atualizando Produto {p_id} com {len(final_ids)} relacionados...")

    try:
        r = requests.put(url, json=payload, headers=headers)
        
        if r.status_code == 200:
            print(f"✅ [SUCESSO] Produto {p_id} atualizado!")
            return True
        else:
            print(f"🔥 [ERRO] Nuvemshop recusou: {r.text}")
            return False
            
    except Exception as e:
        print(f"❌ [CRASH] Erro técnico: {e}")
        return False
