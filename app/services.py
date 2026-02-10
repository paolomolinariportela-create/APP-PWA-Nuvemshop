import requests
import json
import time
from sqlalchemy.orm import Session
from datetime import datetime
from .models import Loja, Produto
from .database import SessionLocal 

# ==============================================================================
# 1. SINCRONIZAÇÃO COMPLETA (ESPELHO FIEL)
# ==============================================================================
def sync_full_store_data(store_id: str, db_ignored: Session = None, force: bool = True):
    """
    SYNC ESPELHO FIEL:
    Baixa produtos e salva usando APENAS as colunas que existem no banco.
    NOTA: Abre uma conexão independente (SessionLocal) para rodar em background com segurança.
    """
    print(f"🔄 [SYNC] Iniciando Espelhamento Completo para Loja {store_id}...")
    
    # 2. CRIA UMA NOVA SESSÃO EXCLUSIVA PARA ESTA TAREFA
    db = SessionLocal()

    try:
        loja = db.query(Loja).filter(Loja.store_id == str(store_id)).first()
        
        if not loja:
            print(f"❌ [SYNC] Erro Crítico: Loja {store_id} não encontrada no banco.")
            return

        if not loja.access_token:
            print("❌ [SYNC] Erro: Loja sem token.")
            return

        headers = {
            "Authentication": f"bearer {loja.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "NewSkin-App"
        }

        page = 1
        total_atualizados = 0
        total_novos = 0
        total_iguais = 0
        
        while True:
            try:
                # Baixa 50 produtos por vez para estabilidade
                url = f"https://api.nuvemshop.com.br/v1/{store_id}/products?page={page}&per_page=50"
                r = requests.get(url, headers=headers)
                
                if r.status_code != 200:
                    if r.status_code == 429: # Rate limit
                        time.sleep(2)
                        continue
                    print(f"⚠️ [SYNC] Erro API Página {page}: {r.status_code}")
                    break
                    
                items = r.json()
                if not items: break

                changes_in_page = False 

                for item in items:
                    p_id = str(item.get('id'))
                    
                    # --- EXTRAÇÃO DE DADOS ---
                    api_titulo = item['name'].get('pt', 'Sem nome')
                    api_handle = item.get('handle', {}).get('pt', '')
                    api_status = "active" if item.get('published') else "paused"
                    
                    # Salva o JSON completo (Descrição, imagens, tags ficam aqui dentro)
                    api_dados_completos = json.dumps(item) 
                    
                    # Cálculo de Preço e Estoque
                    api_preco = 0.0
                    api_estoque = 0
                    
                    variants = item.get('variants', [])
                    if variants:
                        v0 = variants[0]
                        api_preco = float(v0.get('price', 0) or 0)
                        # Soma estoque de todas as variantes
                        for v in variants:
                            qtd = v.get('stock', 0)
                            if qtd: api_estoque += int(qtd)

                    # --- BUSCA NO BANCO ---
                    prod_db = db.query(Produto).filter(Produto.id_nuvemshop == p_id).first()

                    if prod_db:
                        # ATUALIZAÇÃO
                        mudou = False
                        
                        if prod_db.titulo != api_titulo: mudou = True
                        if str(prod_db.preco) != str(api_preco): mudou = True
                        if prod_db.estoque != api_estoque: mudou = True
                        if prod_db.status != api_status: mudou = True
                        if prod_db.dados_completos != api_dados_completos: mudou = True
                        
                        if mudou or force:
                            prod_db.titulo = api_titulo
                            prod_db.preco = str(api_preco)
                            prod_db.estoque = api_estoque
                            prod_db.status = api_status
                            prod_db.handle = api_handle
                            prod_db.dados_completos = api_dados_completos
                            prod_db.updated_at = datetime.utcnow()
                            
                            total_atualizados += 1
                            changes_in_page = True
                        else:
                            total_iguais += 1
                    else:
                        # CRIAÇÃO (Correção: Removido description_text)
                        new_prod = Produto(
                            store_id=str(store_id),
                            id_nuvemshop=p_id,
                            titulo=api_titulo,
                            preco=str(api_preco),
                            estoque=api_estoque,
                            status=api_status,
                            handle=api_handle,
                            dados_completos=api_dados_completos
                        )
                        db.add(new_prod)
                        total_novos += 1
                        changes_in_page = True

                if changes_in_page:
                    db.commit()
                
                print(f"✅ [SYNC] Pág {page}: +{total_novos} Novos | ♻️ {total_atualizados} Atualizados")
                page += 1
                
            except Exception as e:
                print(f"❌ [SYNC] Erro Crítico na Página {page}: {str(e)}")
                break

        print(f"🏁 [SYNC] Concluído! Novos: {total_novos}, Atualizados: {total_atualizados}, Iguais: {total_iguais}")

    except Exception as e:
        print(f"❌ [SYNC] Falha Geral: {str(e)}")
    finally:
        db.close()


# ==============================================================================
# 2. WEBHOOK: ATUALIZAÇÃO ÚNICA
# ==============================================================================
def update_single_product_webhook(store_id: str, product_id: str, db_ignored: Session = None):
    """
    Atualiza APENAS um produto específico via Webhook.
    """
    print(f"🔔 [WEBHOOK] Produto {product_id} Loja {store_id}...")
    
    db = SessionLocal()
    try:
        loja = db.query(Loja).filter(Loja.store_id == str(store_id)).first()
        if not loja or not loja.access_token: return False

        headers = {"Authentication": f"bearer {loja.access_token}"}
        url = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{product_id}"
        r = requests.get(url, headers=headers)
        
        if r.status_code != 200: return False
        item = r.json()
        
        p_id = str(item.get('id'))
        api_titulo = item['name'].get('pt', '')
        api_handle = item.get('handle', {}).get('pt', '')
        api_status = "active" if item.get('published') else "paused"
        api_dados_completos = json.dumps(item)
        
        api_preco = 0.0
        api_estoque = 0
        variants = item.get('variants', [])
        if variants:
            api_preco = float(variants[0].get('price', 0) or 0)
            for v in variants:
                qtd = v.get('stock', 0)
                if qtd: api_estoque += int(qtd)

        prod_db = db.query(Produto).filter(Produto.id_nuvemshop == p_id).first()

        if prod_db:
            prod_db.titulo = api_titulo
            prod_db.preco = str(api_preco)
            prod_db.estoque = api_estoque
            prod_db.status = api_status
            prod_db.handle = api_handle
            prod_db.dados_completos = api_dados_completos
            prod_db.updated_at = datetime.utcnow()
            print(f"✅ [WEBHOOK] Atualizado: {api_titulo}")
        else:
            new_prod = Produto(
                store_id=str(store_id),
                id_nuvemshop=p_id,
                titulo=api_titulo,
                preco=str(api_price),
                estoque=api_estoque,
                status=api_status,
                handle=api_handle,
                dados_completos=api_dados_completos
            )
            db.add(new_prod)
            print(f"✅ [WEBHOOK] Criado: {api_titulo}")

        db.commit()
        return True

    except Exception as e:
        print(f"❌ [WEBHOOK] Erro: {e}")
        return False
    finally:
        db.close()
