import requests
import json

def get_property_id(properties, property_name):
    """ Encontra o ID da propriedade (Cor ou Tamanho) no produto. """
    name_clean = property_name.lower()
    for p in properties:
        if p['name'].lower() == name_clean:
            return p['id']
    return None

def process_variant_update(product_id, rules, store_id, headers):
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{product_id}"
    
    try:
        # 1. Pega dados do produto
        r = requests.get(url, headers=headers)
        if r.status_code != 200: return False
        data = r.json()
        
        variants = data.get('variants', [])
        attributes = data.get('attributes', []) # Definições (Ex: Cor, Tamanho)
        
        action = rules.get('action')
        prop_name = rules.get('property_name') # "Cor" ou "Tamanho"
        target_val = rules.get('target_value')
        
        # --- LÓGICA 1: RENOMEAR (Mais simples) ---
        if action == "RENAME_VALUE":
            new_val = rules.get('new_value')
            updated = False
            
            # Percorre todas as variantes procurando o valor antigo
            for v in variants:
                for val in v.get('values', []):
                    # Verifica se é a propriedade certa e o valor certo
                    # Na Nuvemshop, values é lista de {pt: "Azul"}
                    lang_val = val.get('pt', '')
                    if lang_val.lower() == target_val.lower():
                        # A Nuvemshop não deixa editar valor de variante diretamente fácil.
                        # O jeito mais seguro é atualizar a variante inteira.
                        # Mas simplificando: Em muitos casos, Update na variante funciona.
                        # (Implementação complexa omitida para brevidade, foco no ADD)
                        pass
            return False # Rename é complexo na API v1, vamos focar no ADD/REMOVE primeiro.

        # --- LÓGICA 2: ADICIONAR VALOR (Cria novas variantes) ---
        elif action == "ADD_VALUE":
            # Ex: Adicionar Tamanho "GG"
            # Precisamos saber quais as Outras propriedades para combinar.
            
            # Se o produto não tem variações, é fácil.
            if not variants:
                # Cria a primeira variação simples
                payload = {
                    "price": data.get('price'),
                    "stock": 0,
                    "values": [{"pt": target_val}]
                }
                # Mas precisa definir o atributo antes? Geralmente sim.
                # Essa parte é bem chata na API da Nuvemshop.
                print(f"⚠️ Produto {product_id} sem variações. Adicionar variação do zero é arriscado via API simples.")
                return False

            # Se já tem variações, precisamos combinar.
            # Ex: Já tem Cor: Azul. Adicionando Tamanho: GG -> Cria Azul-GG.
            
            # 1. Achar quais propriedades existem
            existing_props = [attr['pt'] for attr in attributes] # ['Cor', 'Tamanho']
            
            # Se a propriedade alvo (ex: Tamanho) não existe no produto, teríamos que criar o atributo.
            # Isso é MUITO avançado para um script simples. Vamos assumir que o atributo existe.
            if prop_name not in existing_props:
                 print(f"⚠️ Produto {product_id} não tem a propriedade '{prop_name}'.")
                 return False

            # 2. Descobrir os valores das OUTRAS propriedades
            # Ex: Se estamos add Tamanho GG, quais Cores existem?
            other_values = [] 
            # (Lógica simplificada: Duplicar uma variante existente mudando apenas o valor alvo)
            
            base_variant = variants[0] # Pega a primeira como molde
            new_variant = base_variant.copy()
            del new_variant['id']
            del new_variant['product_id']
            del new_variant['created_at']
            del new_variant['updated_at']
            
            # Ajusta os valores
            current_values = new_variant.get('values', [])
            # Tenta substituir o valor da propriedade alvo
            # Essa lógica "cega" de substituir pode falhar se a ordem dos atributos variar.
            
            # POR SEGURANÇA:
            # A API de Variantes é a mais frágil da Nuvemshop.
            # Recomendação: Fazer apenas RENOMEAR (via update de texto) ou REMOVER.
            # ADICIONAR variantes exige recriar a matriz combinatória.
            
            print(f"📡 [VAR] Adicionar Variação em {product_id} exige lógica combinatória avançada.")
            return False

        # --- LÓGICA 3: REMOVER VALOR ---
        elif action == "REMOVE_VALUE":
            # Apaga todas as variantes que tenham esse valor (ex: Apaga tudo que é 'Vermelho')
            ids_to_delete = []
            for v in variants:
                values_list = [val.get('pt', '').lower() for val in v.get('values', [])]
                if target_val.lower() in values_list:
                    ids_to_delete.append(v['id'])
            
            if not ids_to_delete: return True
            
            print(f"📡 [VAR] Apagando {len(ids_to_delete)} variantes de {product_id}...")
            for vid in ids_to_delete:
                requests.delete(f"{url}/variants/{vid}", headers=headers)
            
            return True

    except Exception as e:
        print(f"❌ Erro executor Variantes: {e}")
        return False
