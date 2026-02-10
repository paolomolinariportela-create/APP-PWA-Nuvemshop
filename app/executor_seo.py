import requests
import json
import re

def process_seo_update(product_id, modifications, store_id, headers):
    """
    Aplica otimizações APENAS nos campos de SEO (Título SEO, Descrição SEO, Tags).
    JAMAIS altera o Nome principal do produto.
    """
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{product_id}"
    
    try:
        # 1. Lê o produto original
        r = requests.get(url, headers=headers)
        if r.status_code != 200: return False
        data = r.json()
        
        # Pega o nome atual apenas como BASE para a otimização
        original_name = data.get('name', {}).get('pt', '')
        novo_seo_title = original_name
        payload = {}

        # --- LÓGICA DE DECISÃO: TÍTULO EXATO vs EDIÇÃO ---
        
        # CASO 1: O usuário deu um título pronto (Prioridade Máxima)
        if modifications.get('set_seo_title'):
            novo_seo_title = modifications['set_seo_title']
            
        # CASO 2: O usuário quer editar/limpar o nome atual
        else:
            # 1. Limpeza (Regex)
            if modifications.get('clean_pattern'):
                ptype = modifications['clean_pattern']
                if ptype in ["PARENTHESES", "ALL_SYMBOLS"]:
                    novo_seo_title = re.sub(r'\([^)]*\)', '', novo_seo_title)
                if ptype in ["BRACKETS", "ALL_SYMBOLS"]:
                    novo_seo_title = re.sub(r'\[[^]]*\]', '', novo_seo_title)
                if ptype in ["CURLY_BRACES", "ALL_SYMBOLS"]:
                    novo_seo_title = re.sub(r'\{[^}]*\}', '', novo_seo_title)
                novo_seo_title = re.sub(r'\s+', ' ', novo_seo_title).strip()

            # 2. Formatação
            if modifications.get('format_type'):
                fmt = modifications['format_type']
                if fmt == "UPPERCASE": novo_seo_title = novo_seo_title.upper()
                elif fmt == "LOWERCASE": novo_seo_title = novo_seo_title.lower()
                elif fmt == "TITLE_CASE": novo_seo_title = novo_seo_title.title()
                elif fmt == "CAPITALIZE": novo_seo_title = novo_seo_title.capitalize()

            # 3. Prefixo/Sufixo (Adiciona palavras-chave ao SEO)
            if modifications.get('title_prefix'):
                if not novo_seo_title.startswith(modifications['title_prefix']):
                    novo_seo_title = f"{modifications['title_prefix']}{novo_seo_title}"
            
            if modifications.get('title_suffix'):
                if not novo_seo_title.endswith(modifications['title_suffix']):
                    novo_seo_title = f"{novo_seo_title}{modifications['title_suffix']}"

        # === O PULO DO GATO (A Correção) ===
        # Se geramos um título novo, salvamos no SEO_TITLE, não no NAME.
        # Verifica se mudou em relação ao nome original OU se é um set forçado
        if novo_seo_title != original_name or modifications.get('set_seo_title'):
            # payload['name'] = ...  <-- REMOVIDO COM SEGURANÇA!
            payload['seo_title'] = {"pt": novo_seo_title}

        # 4. Descrição SEO (Se houver)
        if modifications.get('set_seo_description'):
            payload['seo_description'] = {"pt": modifications['set_seo_description']}

        # 5. Tags
        if modifications.get('add_tags'):
            current_tags = [t.strip() for t in data.get('tags', '').split(',') if t.strip()]
            new_tags = modifications['add_tags']
            final_tags = list(set(current_tags + new_tags))
            payload['tags'] = ",".join(final_tags)

        # --- ENVIO ---
        if not payload:
            return True # Nenhuma mudança necessária

        print(f"📡 [SEO] Otimizando Produto {product_id} (Campos: {list(payload.keys())})...")
        r_put = requests.put(url, json=payload, headers=headers)
        
        return r_put.status_code == 200

    except Exception as e:
        print(f"❌ Erro executor SEO: {e}")
        return False
