# app/security.py
import os
import hmac
import hashlib
from fastapi import Request, HTTPException, status

CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")

async def validate_proxy_hmac(request: Request):
    """
    Valida a assinatura enviada pelo App Proxy da Nuvemshop.
    Usa os headers:
      - X-Store-Id
      - X-Customer-Id
      - X-Request-Id
      - X-Linkedstore-HMAC-SHA256
    Concatena: store_id + customer_id + request_id
    Gera HMAC-SHA256 com CLIENT_SECRET e compara com o header.
    """
    if not CLIENT_SECRET:
        # Se não tiver secret configurado, por segurança bloqueia
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Client Secret não configurado"
        )

    headers = request.headers
    received_hmac = headers.get("X-Linkedstore-HMAC-SHA256")
    store_id = headers.get("X-Store-Id", "")
    customer_id = headers.get("X-Customer-Id", "")
    request_id = headers.get("X-Request-Id", "")

    if not received_hmac or not store_id or not request_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assinatura inválida ou headers ausentes"
        )

    # Concatenação exata: store_id + customer_id + request_id
    message = (store_id + customer_id + request_id).encode("utf-8")
    secret = CLIENT_SECRET.encode("utf-8")

    computed = hmac.new(secret, message, hashlib.sha256).hexdigest()

    # Comparação segura
    if not hmac.compare_digest(computed, received_hmac):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Assinatura HMAC inválida"
        )

    # Se passou, não precisa retornar nada específico
    return True
