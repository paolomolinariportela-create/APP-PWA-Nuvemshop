import requests
import json
from fastapi import APIRouter, Request, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from .database import get_db
from .services import update_single_product_webhook
from .models import Loja
# Importamos o nosso guarda-costas (Função de Segurança)
from .security import verify_nuvemshop_signature

router = APIRouter()

# ==============================================================================
# 1. O OUVIDO BLINDADO (Recebe os avisos com segurança)
# ==============================================================================
@router.post("/nuvemshop/product-updated")
async def nuvemshop_webhook_listener(
    request: Request,
    # O FastAPI converte headers para lowercase automaticamente. 
    # Pegamos o HMAC enviado pela Nuvemshop para validar a origem.
    x_linkedstore_hmac_sha256: str = Header(None), 
    db: Session = Depends(get_db)
):
    try:
        # 1. SEGURANÇA: Verificar se o cabeçalho existe
        if not x_linkedstore_hmac_sha256:
            print("🚫 [WEBHOOK] Rejeitado: Cabeçalho HMAC ausente.")
            raise HTTPException(status_code=401, detail="Assinatura ausente")

        # 2. SEGURANÇA: Ler o corpo bruto (bytes) é obrigatório para o cálculo do hash
        body_bytes = await request.body()
        
        # 3. SEGURANÇA: Validar a Assinatura Digital
        # Se a assinatura não bater, significa que o dado foi alterado ou não veio da Nuvemshop.
        is_valid = verify_nuvemshop_signature(body_bytes, x_linkedstore_hmac_sha256)
        
        if not is_valid:
            print("🚫 [WEBHOOK] ALERTA: Assinatura inválida! Tentativa de ataque bloqueada.")
            raise HTTPException(status_code=401, detail="Assinatura inválida")

        # 4. PROCESSAMENTO: Se passou na segurança, processa o JSON tranquilamente
        try:
            data = json.loads(body_bytes)
        except json.JSONDecodeError:
            print("⚠️ [WEBHOOK] Erro: JSON malformado recebido.")
            return {"status": "error", "detail": "Invalid JSON"}

        store_id = str(data.get("store_id"))
        event = data.get("event")
        product_id = str(data.get("id"))

        # Verificação extra: A loja existe no nosso banco?
        # Isso evita processar webhooks de lojas antigas que já desinstalaram o app
        loja_existe = db.query(Loja).filter(Loja.store_id == store_id).first()
        if not loja_existe:
            print(f"⚠️ [WEBHOOK] Ignorado: Loja {store_id} não encontrada no banco.")
            return {"status": "ignored", "detail": "Store not found"}

        print(f"📨 [WEBHOOK VERIFICADO ✅] Evento: {event} | Loja: {store_id} | ID: {product_id}")

        if event == "product/updated" or event == "product/created":
            # Chama o serviço de atualização cirúrgica
            update_single_product_webhook(store_id, product_id, db)
            
        elif event == "product/deleted":
            print(f"🗑️ [WEBHOOK] Produto {product_id} deletado na loja.")
            # Aqui futuramente você pode implementar a remoção do produto do seu banco local

        return {"status": "received"}

    except HTTPException as he:
        raise he # Repassa o erro de segurança (401)
    except Exception as e:
        print(f"❌ [WEBHOOK ERROR] Falha interna: {e}")
        # Retorna 200 para a Nuvemshop não ficar reenviando (loop de erro), 
        # pois o erro foi interno nosso e não da requisição.
        return {"status": "error", "detail": str(e)}


# ==============================================================================
# 2. O INSTALADOR (Configura a Nuvemshop para nós)
# ==============================================================================
@router.get("/setup")
def setup_webhooks_automatic(
    store_id: str, 
    backend_url: str, 
    db: Session = Depends(get_db)
):
    """
    Roda um comando na API da Nuvemshop para registrar nossos webhooks.
    Uso: /webhooks/setup?store_id=123&backend_url=https://seu-app.railway.app
    """
    # Busca o token da loja no banco para ter permissão de criar o webhook
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja:
        return {"error": "Loja não encontrada no banco de dados."}

    headers = {
        "Authentication": f"bearer {loja.access_token}",
        "Content-Type": "application/json"
    }

    # URL final do nosso ouvidor (garante que não tenha barra duplicada)
    base = backend_url.rstrip("/")
    target_url = f"{base}/webhooks/nuvemshop/product-updated"

    # Eventos que queremos ouvir
    events_to_register = ["product/updated", "product/created"]
    results = []

    print(f"🔌 [SETUP] Configurando webhooks para loja {store_id} em {target_url}...")

    for event in events_to_register:
        payload = {
            "event": event,
            "url": target_url
        }
        
        try:
            r = requests.post(f"https://api.nuvemshop.com.br/v1/{store_id}/webhooks", json=payload, headers=headers)
            
            if r.status_code == 201:
                results.append(f"✅ {event}: Criado com sucesso!")
            elif r.status_code == 422:
                 results.append(f"⚠️ {event}: Já existia (ou URL inválida).")
            else:
                results.append(f"❌ {event}: Erro {r.status_code} - {r.text}")
        except Exception as req_err:
            results.append(f"❌ {event}: Erro de conexão - {str(req_err)}")

    return {
        "status": "Finalizado",
        "target_url": target_url,
        "nuvemshop_response": results
    }
