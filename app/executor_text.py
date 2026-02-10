import re
import requests
import json

def process_product_content(product, change, store_id, headers):
    """
    Processa alterações de TEXTO, TAGS e MARCAS.
    VERSÃO DEBUG: Usa string vazia para limpar marca e mostra o payload no log.
    """
    payload = {}
    field = change['field']
    p_nuvem_id = product.nuvemshop_id 
    
    endpoint = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}"

    # ==============================================================================
    # 1. TRATAMENTO DE TÍTULO E DESCRIÇÃO
    # ==============================================================================
    if field in ['title', 'description']:
        current_text = ""
        
        # --- LEITURA LOCAL ---
        if field == 'title':
            current_text = product.name or ""
        elif field == 'description':
            possiveis = ['description', 'description_text', 'body_html', 'content']
            for attr in possiveis:
                val = getattr(product, attr, None)
                if val and isinstance(val, str) and len(val) > 0:
                    current_text = val
                    break
        
        current_text = current_text or ""
        new_text = current_text 
        action = change['action']

        # --- LÓGICA DE TEXTO ---
        if action == 'CLEAN_PATTERN':
            ptype = change.get('pattern_type')
            if ptype in ["PARENTHESES", "ALL_SYMBOLS"]: new_text = re.sub(r'\([^)]*\)', '', new_text)
            new_text = re.sub(r'\s+', ' ', new_text).strip()
            
        elif action == 'FORMAT':
            fmt = change.get('format_type')
            if fmt == "UPPERCASE": new_text = current_text.upper()
            elif fmt == "TITLE_CASE": new_text = current_text.title()
            
        elif action == 'REPLACE':
            old = change.get('replace_this', '')
            val = change.get('value', '')
            if old: new_text = current_text.replace(old, val)
            
        elif action == 'SET': 
            new_text = change['value']
            
        elif action == 'APPEND': 
            sep = "<br><br>" if "<" in current_text else "\n\n"
            new_text = f"{current_text}{sep}{change['value']}"
            
        elif action == 'PREPEND': 
            sep = "<br><br>" if "<" in current_text else "\n\n"
            new_text = f"{change['value']}{sep}{current_text}"

        elif action == 'REMOVE_AFTER':
            sep = change.get('separator')
            if sep and sep in current_text: new_text = current_text.split(sep)[0].strip()

        elif action == 'REMOVE_BEFORE':
            sep = change.get('separator')
            if sep and sep in current_text:
                parts = current_text.split(sep, 1)
                if len(parts) > 1: new_text = parts[1].strip()

        elif action == 'REMOVE_IMAGES':
            new_text = re.sub(r'<img[^>]*>', '', current_text, flags=re.IGNORECASE)

        # Se mudou ou é SET (forçar envio), prepara payload
        if new_text != current_text or action == 'SET':
            key_api = "name" if field == 'title' else "description"
            payload[key_api] = {"pt": new_text}

    # ==============================================================================
    # 2. TRATAMENTO DE TAGS
    # ==============================================================================
    elif field == 'tags':
        current_tags_str = getattr(product, 'tags', '') or ""
        current_tags = [t.strip() for t in current_tags_str.split(',') if t.strip()]
        target_tag = change.get('value', '').strip()
        action = change['action']
        changed = False

        if action == 'STANDARDIZE_CASE':
            case_type = change.get('case_type', 'TITLE_CASE')
            new_list = []
            seen = set()
            for t in current_tags:
                if case_type == 'UPPERCASE': t_new = t.upper()
                elif case_type == 'LOWERCASE': t_new = t.lower()
                else: t_new = t.title()
                if t_new not in seen: new_list.append(t_new); seen.add(t_new)
            if new_list != current_tags: current_tags = new_list; changed = True

        elif action == 'REMOVE_BY_PATTERN':
            original = len(current_tags)
            current_tags = [t for t in current_tags if target_tag.lower() not in t.lower()]
            if len(current_tags) < original: changed = True

        elif action == 'AUTO_TAG_FROM_TITLE':
            stopwords = ['com', 'para', 'pela', 'modelo', 'cores', 'tamanho', 'oferta', 'novo', 'frete', 'gratis']
            words = re.findall(r'\w+', product.name)
            for w in words:
                w_clean = w.strip()
                if len(w_clean) > 3 and w_clean.lower() not in stopwords:
                    if not any(t.lower() == w_clean.lower() for t in current_tags):
                        current_tags.append(w_clean)
                        changed = True

        elif action == 'ADD_TAG':
            if not any(t.lower() == target_tag.lower() for t in current_tags):
                current_tags.append(target_tag)
                changed = True
        elif action == 'REMOVE_TAG':
            original = len(current_tags)
            current_tags = [t for t in current_tags if t.lower() != target_tag.lower()]
            if len(current_tags) < original: changed = True
        elif action == 'REPLACE_TAG':
            new_tag = change.get('replace_with', '').strip()
            new_list = []
            for t in current_tags:
                if t.lower() == target_tag.lower(): new_list.append(new_tag); changed = True
                else: new_list.append(t)
            current_tags = new_list

        if changed:
            final_tags_str = ",".join(current_tags)
            payload['tags'] = final_tags_str
            product.tags = final_tags_str

    # ==============================================================================
    # 3. TRATAMENTO DE MARCAS
    # ==============================================================================
    elif field == 'brand':
        current_brand = getattr(product, 'brand', '') or ""
        target_brand = change.get('value', '').strip()
        action = change['action']
        new_brand = current_brand

        if action == 'SET_BRAND':
            new_brand = target_brand
        elif action == 'REMOVE_BRAND':
            # --- MUDANÇA AQUI: Usa string vazia "" em vez de None ---
            new_brand = "" 
        elif action == 'REPLACE_BRAND':
            replace_this = change.get('replace_this', '').strip()
            if current_brand and replace_this.lower() == current_brand.lower():
                new_brand = target_brand

        # Força o envio se mudou OU se é uma ação de forçar (SET/REMOVE)
        if new_brand != current_brand or action in ['SET_BRAND', 'REMOVE_BRAND']:
            payload['brand'] = new_brand
            product.brand = new_brand

    # ==============================================================================
    # 4. ENVIO PARA NUVEMSHOP
    # ==============================================================================
    if payload:
        try:
            # --- DEBUG VISUAL: Mostra o que estamos mandando ---
            print(f"📦 [DEBUG] Payload enviado para API: {json.dumps(payload)}")
            
            r = requests.put(endpoint, json=payload, headers=headers)
            
            if r.status_code == 200:
                # Atualiza objeto local
                if field == 'title': 
                    product.name = payload['name']['pt']
                elif field == 'description': 
                    if hasattr(product, 'description'): product.description = payload['description']['pt']
                    if hasattr(product, 'description_text'): product.description_text = payload['description']['pt']
                elif field == 'brand':
                    product.brand = payload.get('brand')
                
                return True
            else:
                print(f"❌ [ERRO API] Status: {r.status_code} | Resposta: {r.text}")
        except Exception as e:
            print(f"❌ [ERRO REQ] {str(e)}")
            pass
            
    return False
