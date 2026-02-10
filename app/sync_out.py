import requests
import time
from sqlalchemy.orm import Session
from .models import Loja, Produto

def push_changes_to_nuvemshop(store_id: str, product_ids: list, db: Session):
    """
    Envia atualizações para Nuvemshop com logs detalhados de variantes.
    """
    print(f"🚀 [SYNC-OUT] Iniciando envio de {len(product_ids)} produtos...")
    
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja or not loja.access_token:
        print("❌ [SYNC-OUT] Erro: Sem token.")
        return

    headers = {
        "Authentication": f"bearer {loja.access_token}",
        "Content-Type": "application/json",
        "User-Agent": "NewSkinLab (contato@newskinlab.com.br)"
    }

    count = 0
    
    for pid in product_ids:
        # Recarrega o produto do banco para garantir dados frescos
        db.expire_all() 
        produto = db.query(Produto).filter(Produto.id == pid).first()
        
        if not produto: 
            print(f"⚠️ Produto {pid} não encontrado no banco.")
            continue

        print(f"🔄 Processando Produto: {produto.name} (ID: {produto.id})")

        # --- 1. ATUALIZA O PAI ---
        url_main = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{produto.id}"
        payload_main = {
            "price": str(produto.price),
            "promotional_price": str(produto.promotional_price) if produto.promotional_price else None
        }
        
        try:
            r = requests.put(url_main, json=payload_main, headers=headers)
            if r.status_code == 200:
                print(f"   ✅ Pai atualizado. Preço base: {payload_main['price']}")
                count += 1
            else:
                print(f"   ⚠️ Erro no Pai: {r.status_code} - {r.text}")
        except Exception as e:
            print(f"   ❌ Erro Conexão Pai: {e}")

        # --- 2. ATUALIZA AS VARIANTES ---
        # Verifica se existe e se é lista
        variants = produto.variants_json
        
        if variants and isinstance(variants, list) and len(variants) > 0:
            print(f"   found {len(variants)} variantes. Atualizando uma por uma...")
            
            for variant in variants:
                vid = variant.get('id')
                v_price = variant.get('price')
                v_promo = variant.get('promotional_price')
                
                if not vid: continue

                url_var = f"https://api.nuvemshop.com.br/v1/{store_id}/products/{produto.id}/variants/{vid}"
                
                # Payload forçado para string
                payload_var = {
                    "price": str(v_price),
                    "promotional_price": str(v_promo) if v_promo else None
                }

                try:
                    rv = requests.put(url_var, json=payload_var, headers=headers)
                    if rv.status_code == 200:
                        print(f"      ✅ Variante {vid}: R$ {v_price}")
                    else:
                        print(f"      ❌ Variante {vid} Falhou: {rv.status_code} - {rv.text}")
                except Exception as ev:
                    print(f"      ❌ Erro Conexão Variante: {ev}")
                
                time.sleep(0.2) # Pausa rápida
        else:
            print("   ℹ️ Nenhuma variante encontrada neste produto.")

        time.sleep(0.5)

    print(f"🏁 [SYNC-OUT] Finalizado.")
