import json
from sqlalchemy.orm import Session
from .models import Loja, HistoryLog
from .utils import get_filtered_products

# Importa os ESPECIALISTAS (Eles é que trabalham de verdade)
from .executor_math import process_variant_math
from .executor_text import process_product_content
from .executor_status import process_product_status
from .executor_code import process_product_code
from .executor_logistics import process_logistics_update
from .executor_demographics import process_demographics_update
from .executor_related import process_related_update
from .executor_seo import process_seo_update
from .executor_category import process_category_update, process_structural_update  
from .executor_variants import process_variant_update # <--- NOVO ESPECIALISTA (VARIAÇÕES)

def execute_nuvemshop_update(store_id: str, plan: dict, db: Session):
    print(f"🚀 [EXECUTION] Job iniciado Loja: {store_id}")
    
    # 1. Validação de Segurança (O Crachá)
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja or not loja.access_token: 
        print("❌ Loja não encontrada ou sem token de acesso.")
        return

    headers = {
        "Authentication": f"bearer {loja.access_token}",
        "Content-Type": "application/json",
        "User-Agent": "KingUrbanAI"
    }

    # === DETECÇÃO DE AÇÃO ESTRUTURAL (Categorias - Uma vez só) ===
    cat_rules = plan.get('category_rules', {})
    if cat_rules.get('action') in ["RENAME", "MOVE_TREE", "DELETE"]:
        print("🏗️ Detectada ação estrutural de categoria. Executando...")
        success = process_structural_update(cat_rules, store_id, headers)
        
        status = "SUCCESS" if success else "ERROR"
        try:
            db.add(HistoryLog(
                store_id=store_id, 
                action_summary=f"ESTRUTURA: {cat_rules['action']} {cat_rules['target_category_name']}",
                full_command=json.dumps(plan), 
                affected_count=1, 
                status=status
            ))
            db.commit()
        except Exception as e:
            print(f"⚠️ Erro log estrutural: {e}")
            
        print(f"🏁 Job Estrutural Finalizado: {status}")
        return # Encerra aqui.

    # 2. Busca os produtos (O Material)
    products = get_filtered_products(db, store_id, plan)
    print(f"🔎 [FILTRO] Analisando {len(products)} produtos candidatos...")
    
    # Detecta Modos Especiais
    is_seo_mode = 'modifications' in plan
    is_cat_mode = 'category_rules' in plan
    is_var_mode = 'variant_rules' in plan # <--- DETECTOR DE VARIAÇÕES
    
    # Se não for nenhum modo especial nem padrão, encerra.
    if not is_seo_mode and not is_cat_mode and not is_var_mode and not plan.get('changes'): 
        return 

    # Prepara variável de controle legado
    change = None
    if not is_seo_mode and not is_cat_mode and not is_var_mode and plan.get('changes'):
        change = plan['changes'][0]
        
    success_count = 0

    # 3. Loop Principal (O Gerente distribuindo tarefas)
    for p in products:
        try:
            if not p.nuvemshop_id: continue

            processed = False
            
            # --- EQUIPE DE SEO ---
            if is_seo_mode:
                mods = plan['modifications']
                processed = process_seo_update(p.nuvemshop_id, mods, store_id, headers)

            # --- EQUIPE DE CATEGORIAS (PRODUTOS) ---
            elif is_cat_mode:
                rules = plan['category_rules']
                processed = process_category_update(p.nuvemshop_id, rules, store_id, headers)

            # --- EQUIPE DE VARIAÇÕES (NOVO) ---
            elif is_var_mode:
                rules = plan['variant_rules']
                processed = process_variant_update(p.nuvemshop_id, rules, store_id, headers)

            # --- EQUIPE PADRÃO (Legado/Geral) ---
            elif change:
                field = change['field']

                if field in ['title', 'description', 'tags', 'seo', 'handle', 'brand']:
                    processed = process_product_content(p, change, store_id, headers)

                elif field == 'status':
                    processed = process_product_status(p, change, store_id, headers)

                elif field in ['sku', 'barcode', 'gtin']:
                    processed = process_product_code(p, change, store_id, headers)    
                    
                elif field == 'logistics_batch' or field in ['weight', 'height', 'width', 'depth']:
                    processed = process_logistics_update(p, change, store_id, headers)
                    
                elif field == 'demographics' or field in ['mpn', 'gender', 'age_group', 'ncm']:
                    processed = process_demographics_update(p, change, store_id, headers)  
                    
                elif field == 'related':
                    processed = process_related_update(p, change, store_id, headers)
                
                elif field in ['price', 'promotional_price', 'stock', 'cost', 'weight', 'width', 'height', 'depth']:
                    variant_filters = plan.get('find_product', {}) 
                    processed = process_variant_math(p, change, variant_filters, store_id, headers)
            
            # Se alguém trabalhou, conta o sucesso
            if processed: 
                success_count += 1
            
        except Exception as e:
            print(f"❌ Erro Crítico Prod {p.id}: {e}")

    # 4. Registro Centralizado (O Relatório Final)
    try:
        db.commit() # Salva o estado dos objetos
        
        # Define o resumo da ação para o log
        if is_seo_mode:
            summary_text = "SEO UPDATE (Advanced)"
        elif is_cat_mode:
            summary_text = f"CATEGORY ({plan['category_rules']['action']})"
        elif is_var_mode: # <--- NOVO
            summary_text = f"VARIANT ({plan['variant_rules']['action']})"
        else:
            summary_text = f"{change['action']} {change['field']}"

        status_log = "SUCCESS" if success_count > 0 else "SKIPPED"
        
        new_log = HistoryLog(
            store_id=store_id, 
            action_summary=f"{summary_text} (Realizados: {success_count})", 
            full_command=json.dumps(plan), 
            affected_count=success_count, 
            status=status_log
        )
        db.add(new_log)
        db.commit()
    except Exception as log_err:
        print(f"⚠️ Erro ao salvar log: {log_err}")
        
    print(f"🏁 Job Finalizado. Alterados realmente: {success_count}")
