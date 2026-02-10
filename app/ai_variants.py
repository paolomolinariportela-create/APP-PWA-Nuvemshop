import requests
import json
import itertools

def process_variant_update(product_id, rules, store_id, headers):
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{product_id}"
    
    try:
        # 1. Pega dados do produto
        r = requests.get(url, headers=headers)
        if r.status_code != 200: return False
        data = r.json()
        
        variants = data.get('variants', [])
        attributes = data.get('attributes', []) # Ex: [{'id': '1', 'pt': 'Cor'}, {'id': '2', 'pt': 'Tamanho'}]
        
        action = rules.get('action')
        prop_target = rules.get('property_name') # "Cor"
        val_target = rules.get('target_value')   # "Azul"
        
        print(f"🎨 [VAR] Prod {product_id}: {action} {prop_target}='{val_target}'")

        # ====================================================
        # AÇÃO 1: REMOVER (REMOVE_VALUE)
        # ====================================================
        if action == "REMOVE_VALUE":
            ids_to_delete = []
            
            # Varre todas as variantes
            for v in variants:
                # Olha os valores dessa variante (Ex: ["Azul", "M"])
                values_list = [val.get('pt', '').lower() for val in v.get('values', [])]
                
                # Se o valor alvo estiver na lista, marca para morrer
                if val_target.lower() in values_list:
                    ids_to_delete.append(v['id'])
            
            if not ids_to_delete:
                return True # Nada a deletar, sucesso.
            
            print(f"   🔥 Apagando {len(ids_to_delete)} variantes...")
            for vid in ids_to_delete:
                requests.delete(f"{url}/variants/{vid}", headers=headers)
            return True

        # ====================================================
        # AÇÃO 2: ADICIONAR (ADD_VALUE) - O DESAFIO DA MATRIZ
        # ====================================================
        elif action == "ADD_VALUE":
            # Verifica se a propriedade existe (Ex: O produto tem "Cor"?)
            prop_exists = False
            for attr in attributes:
                if attr.get('pt', '').lower() == prop_target.lower():
                    prop_exists = True
                    break
            
            # Se a propriedade não existe (ex: Produto simples e estamos add "Tamanho"), 
            # na Nuvemshop isso é complexo pois exige criar o Atributo primeiro.
            # Por segurança, vamos focar em EXPANDIR grades existentes ou produtos simples.
            
            # LOGICA DE MATRIZ:
            # Se temos Cor: [A, B] e Tamanho: [P]. Queremos adicionar Tamanho M.
            # Temos que criar: A-M e B-M.
            
            # 1. Identificar os valores das OUTRAS propriedades
            # Se estamos mexendo em "Tamanho", quais são as "Cores" que existem?
            
            # Simplificação Segura:
            # Vamos pegar uma variante existente como 'molde', copiar seus dados (preço, peso)
            # e trocar apenas o valor da propriedade alvo.
            
            if not variants:
                 # Produto sem variação. Cria a primeira.
                 payload = {
                     "price": data.get('price'),
                     "stock": 0, # Começa sem estoque por segurança
                     "values": [{"pt": val_target}]
                 }
                 r = requests.post(f"{url}/variants", json=payload, headers=headers)
                 return r.status_code == 201
            
            # Se tem variantes, vamos clonar.
            # Precisamos achar variantes que representam as "outras" combinações.
            # Ex: Se queremos add Tamanho G, pegamos uma variante "Azul-P" e criamos "Azul-G".
            # Mas cuidado para não criar duplicado.
            
            # Agrupa valores existentes das outras propriedades
            other_combinations = []
            
            for v in variants:
                # Cria uma assinatura da variante (ex: "Azul") ignorando a propriedade que estamos mexendo
                # Essa lógica é complexa para um script genérico. 
                
                # ABORDAGEM DIRETA:
                # Tenta criar a variante. Se a combinação já existe, a API ignora ou dá erro (que tratamos).
                
                # Clona a variante
                new_variant = {
                    "price": v.get('price'),
                    "promotional_price": v.get('promotional_price'),
                    "stock": 0,
                    "weight": v.get('weight'),
                    "width": v.get('width'),
                    "height": v.get('height'),
                    "depth": v.get('depth'),
                    "values": []
                }
                
                # Reconstrói os valores
                valid_clone = False
                current_values = v.get('values', [])
                
                # Se attributes e values não baterem, pula
                if len(current_values) != len(attributes): continue
                
                for i, attr in enumerate(attributes):
                    attr_name = attr.get('pt', '')
                    curr_val = current_values[i].get('pt', '')
                    
                    if attr_name.lower() == prop_target.lower():
                        # É a propriedade que estamos mudando! Põe o NOVO valor.
                        # Ex: Era "P", vira "GG"
                        new_variant['values'].append({"pt": val_target})
                        valid_clone = True
                    else:
                        # É outra propriedade (ex: Cor). Mantém o valor original (Azul).
                        new_variant['values'].append({"pt": curr_val})
                
                if valid_clone:
                    # Tenta criar essa nova combinação
                    # A API da Nuvemshop valida duplicidade.
                    r = requests.post(f"{url}/variants", json=new_variant, headers=headers)
                    if r.status_code == 201:
                        print(f"   ✨ Criada variante combinada.")
                    # Se der 422, é porque já existe, ignora.

            return True

    except Exception as e:
        print(f"❌ Erro executor Variantes: {e}")
        return False
