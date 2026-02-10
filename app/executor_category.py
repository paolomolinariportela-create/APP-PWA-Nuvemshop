import requests
import json

CATEGORY_CACHE = {}

def get_all_categories(store_id, headers):
    if store_id in CATEGORY_CACHE: return CATEGORY_CACHE[store_id]
    categories = []
    page = 1
    base_url = f"https://api.nuvemshop.com.br/v1/{store_id}/categories"
    while True:
        try:
            r = requests.get(f"{base_url}?page={page}&per_page=200", headers=headers)
            if r.status_code != 200: break
            batch = r.json()
            if not batch: break
            categories.extend(batch)
            if len(batch) < 200: break
            page += 1
        except: break
    CATEGORY_CACHE[store_id] = categories
    return categories

def get_category_id_exact(store_id, category_name, headers):
    if not category_name: return None
    categories = get_all_categories(store_id, headers)
    target = category_name.lower().strip()
    for cat in categories:
        if cat.get('name', {}).get('pt', '').lower() == target:
            return cat['id']
    return None

def get_or_create_category_id(store_id, category_name, parent_name, headers):
    cat_id = get_category_id_exact(store_id, category_name, headers)
    if cat_id: return cat_id

    print(f"✨ [CAT] Criando: '{category_name}'...")
    payload = {
        "name": {"pt": category_name}, 
        "handle": {"pt": category_name.lower().replace(" ", "-")}
    }
    if parent_name:
        pid = get_category_id_exact(store_id, parent_name, headers)
        if pid: payload["parent"] = pid
    
    r = requests.post(f"https://api.nuvemshop.com.br/v1/{store_id}/categories", json=payload, headers=headers)
    if r.status_code == 201:
        new_cat = r.json()
        if store_id in CATEGORY_CACHE: CATEGORY_CACHE[store_id].append(new_cat)
        return new_cat['id']
    return None

def process_category_update(product_id, rules, store_id, headers):
    """ Atualiza PRODUTOS (Add/Remove/Set) """
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{product_id}"
    target = rules.get('target_category_name')
    parent = rules.get('parent_category_name')
    tid = get_or_create_category_id(store_id, target, parent, headers)
    
    if not tid: return False
    
    try:
        r = requests.get(url, headers=headers)
        if r.status_code != 200: return False
        current = [c['id'] for c in r.json().get('categories', [])]
        action = rules.get('action')
        
        new_ids = []
        if action == "SET": new_ids = [tid]
        elif action == "ADD": 
            new_ids = list(current)
            if tid not in new_ids: new_ids.append(tid)
        elif action == "REMOVE":
            new_ids = [c for c in current if c != tid]
            
        if set(new_ids) == set(current): return True
        
        requests.put(url, json={"categories": new_ids}, headers=headers)
        return True
    except: return False

def process_structural_update(rules, store_id, headers):
    """ Atualiza ESTRUTURA (Rename/Move Tree/Delete) """
    action = rules.get('action')
    target = rules.get('target_category_name')
    cid = get_category_id_exact(store_id, target, headers)
    
    if not cid: 
        print(f"⚠️ Categoria '{target}' não encontrada.")
        return False
    
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/categories/{cid}"
    print(f"🏗️ [ESTRUTURA] {action} em '{target}'...")

    if action == "DELETE":
        return requests.delete(url, headers=headers).status_code == 200
        
    payload = {}
    if action == "RENAME":
        payload = {"name": {"pt": rules.get('new_name')}}
    elif action == "MOVE_TREE":
        pid = get_category_id_exact(store_id, rules.get('parent_category_name'), headers)
        if pid: payload = {"parent": pid}
        
    if payload:
        return requests.put(url, json=payload, headers=headers).status_code == 200
    return False
