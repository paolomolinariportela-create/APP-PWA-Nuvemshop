import requests
import json

def process_related_update(product, change, store_id, headers):
    """
    MODO RAIO-X: Apenas LÊ os dados para descobrirmos o campo secreto.
    """
    p_id = product.nuvemshop_id
    print(f"\n☢️ --- INICIANDO RAIO-X NO PRODUTO {p_id} ---")
    
    # 1. Busca os dados Padrão
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_id}"
    r = requests.get(url, headers=headers)
    data = r.json()
    
    # Verifica se existe algum campo com "related" ou "cross" no nome
    print("🔍 Procurando campos suspeitos no Produto Principal:")
    found_keys = [k for k in data.keys() if 'related' in k or 'cross' in k or 'products' in k]
    for k in found_keys:
        print(f"   👉 {k}: {data[k]}")
        
    if not found_keys:
        print("   ❌ Nenhum campo óbvio encontrado no nível principal.")

    # 2. Busca nos METAFIELDS (O esconderijo provável)
    print("\n🔍 Investigando Metafields (Dados Extras):")
    url_meta = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_id}/metafields"
    r_meta = requests.get(url_meta, headers=headers)
    metafields = r_meta.json()
    
    if isinstance(metafields, list):
        for m in metafields:
            # Imprime namespace e key para analisarmos
            print(f"   📦 Namespace: {m.get('namespace')} | Key: {m.get('key')} | Value: {m.get('value')}")
            if m.get('namespace') == 'related_products':
                print("   🎉 BINGO! ENCONTRAMOS O ESCONDERIJO!")
    else:
        print(f"   ⚠️ Resposta estranha dos metafields: {metafields}")

    print("------------------------------------------------")
    return True # Retorna True para não dar erro no fluxo
