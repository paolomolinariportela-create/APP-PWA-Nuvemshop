import json
import time
import requests

# ==============================================================================
# FUNÇÃO AUXILIAR: ARREDONDAMENTO
# ==============================================================================
def apply_rounding(value: float, strategy: str) -> float:
    if value is None: return None
    if strategy == "0.99": return int(value) + 0.99
    elif strategy == "0.90": return int(value) + 0.90
    elif strategy == "0.00": return int(value) + 0.00
    return round(value, 2)

# ==============================================================================
# LÓGICA DE VARIANTES (MATEMÁTICA + PROMOÇÃO)
# ==============================================================================
def process_variant_math(product, change, variant_filters, store_id, headers):
    """
    Processa alterações numéricas (Preço, Estoque, Custo, Promoção) nas variantes.
    Retorna True se houve sucesso.
    """
    variants_list = []
    p_nuvem_id = product.nuvemshop_id 
    
    if product.variants_json:
        if isinstance(product.variants_json, str):
            try: variants_list = json.loads(product.variants_json)
            except: variants_list = [] 
        else: variants_list = product.variants_json 

    if not variants_list: return False
    
    any_success = False
    list_was_modified = False 

    # Extrai configurações do comando
    # field pode vir vazio se for ação de promoção genérica, então assumimos promotional_price
    field = change.get('field', 'promotional_price') 
    action = change['action']
    rounding = change.get('rounding', 'NONE')
    safety_lock = change.get('safety_lock', False)
    mode = change.get('mode', 'PERCENT') # PERCENT, FIXED_PRICE, FIXED_DISCOUNT
    
    val_param = 0
    if action not in ['REMOVE', 'CLEAR_PROMOTION', 'COPY_PRICE_TO_COMPARE']:
        try: val_param = float(change['value'])
        except: val_param = 0

    for i, v in enumerate(variants_list):
        variant_id = v.get('id')
        if not variant_id: continue

        payload = {}
        
        # --- LÓGICA FLOAT (Preço, Custo, Promoção) ---
        # Adicionamos CLEAR_PROMOTION e APPLY_DISCOUNT na verificação
        if field in ['price', 'promotional_price', 'cost'] or action in ['APPLY_DISCOUNT', 'CLEAR_PROMOTION']:
            
            # Recupera valores atuais
            current_price = float(v.get('price', 0) or 0)
            current_promo = float(v.get('promotional_price', 0) or 0)
            cost_value = float(v.get('cost', 0) or 0)

            # Define sobre qual valor vamos trabalhar inicialmente
            if field == 'promotional_price':
                new_val = current_promo
            else:
                new_val = current_price

            # ============================================
            # LÓGICA ESPECIAL DE PROMOÇÃO (De/Por)
            # ============================================
            if action == 'APPLY_DISCOUNT':
                # NA API NUVEMSHOP:
                # 'price' vira o preço "De" (Riscado)
                # 'promotional_price' vira o preço "Por" (Venda)
                
                # Se o preço atual for menor que o novo "De", subimos o price para gerar o efeito visual
                # Mas geralmente, mantemos o price atual como "De"
                
                # Calcula o novo valor promocional
                if mode == 'PERCENT':
                    new_val = current_price * (1 - val_param / 100)
                elif mode == 'FIXED_DISCOUNT':
                    new_val = current_price - val_param
                elif mode == 'FIXED_PRICE':
                    new_val = val_param
                
                # Garante que não vai mandar compare_at_price (campo inválido na API de escrita)
                if 'compare_at_price' in payload: del payload['compare_at_price']
                
                # O campo a ser atualizado é o promocional
                field = 'promotional_price'

            elif action == 'CLEAR_PROMOTION':
                new_val = None
                field = 'promotional_price'
                
            # ============================================
            # LÓGICA PADRÃO (Matemática)
            # ============================================
            elif action == 'APPLY_MARKUP':
                if cost_value > 0: new_val = cost_value * (1 + val_param / 100)
                else: new_val = current_price # Fallback
            elif action == 'REMOVE': 
                new_val = None
            elif action == 'SET': 
                new_val = val_param
            elif action == 'INCREASE_PERCENT': 
                new_val = new_val * (1 + val_param / 100)
            elif action == 'DECREASE_PERCENT': 
                new_val = new_val * (1 - val_param / 100)
            elif action == 'INCREASE_FIXED': 
                new_val = new_val + val_param
            elif action == 'DECREASE_FIXED': 
                new_val = new_val - val_param

            # Trava de Segurança (Não vender abaixo do custo)
            # Ignora se for None (remoção) ou se Custo for 0
            if safety_lock and new_val is not None and cost_value > 0:
                if new_val < cost_value: new_val = cost_value

            # Arredondamento
            if new_val is not None: new_val = apply_rounding(new_val, rounding)

            # Prepara Payload do Campo Principal
            if action != 'COPY_PRICE_TO_COMPARE':
                # Se mudou o valor OU se é uma ação de limpeza/remoção
                if new_val != (current_promo if field == 'promotional_price' else current_price) or action in ['REMOVE', 'CLEAR_PROMOTION']:
                    payload[field] = new_val

        # --- LÓGICA INT (Estoque) ---
        elif field == 'stock':
            current = int(v.get('stock', 0) or 0)
            new_val = current
            
            if action == 'SET': new_val = int(val_param)
            elif action == 'ADD' or action == 'INCREASE_FIXED': new_val = current + int(val_param)
            elif action == 'DECREASE_FIXED': new_val = current - int(val_param)
            
            if new_val < 0: new_val = 0
            
            if new_val != current:
                payload['stock'] = new_val

        # --- ENVIO PARA API ---
        if payload:
            endpoint = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{p_nuvem_id}/variants/{variant_id}"
            try:
                r = requests.put(endpoint, json=payload, headers=headers)
                if r.status_code in [200, 201]: 
                    any_success = True
                    # Atualiza memória local (Todos os campos que mudaram)
                    for k, val_updated in payload.items():
                        variants_list[i][k] = val_updated
                    list_was_modified = True
                
                time.sleep(0.15) 
            except Exception as e:
                print(f"Erro no update variante: {e}")

    # Atualiza memória local do produto pai
    if any_success and list_was_modified:
        product.variants_json = variants_list 

    return any_success
