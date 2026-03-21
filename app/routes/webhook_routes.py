import hmac
import hashlib
import httpx
from fastapi import APIRouter, Request, Depends, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import AppConfig, Loja
from app.auth import decrypt_token

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def get_onesignal_credentials(store_id: str, db: Session):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return None, None
    return (
        getattr(config, "onesignal_app_id", None),
        getattr(config, "onesignal_api_key", None),
    )


STATUS_MESSAGES = {
    "packed":      ("📦 Pedido embalado!", "Seu pedido #{order} foi embalado e está pronto para envio."),
    "shipped":     ("🚚 Pedido enviado!", "Seu pedido #{order} foi enviado. Acompanhe a entrega!"),
    "delivered":   ("✅ Pedido entregue!", "Seu pedido #{order} foi entregue. Aproveite!"),
    "cancelled":   ("❌ Pedido cancelado", "Seu pedido #{order} foi cancelado. Entre em contato conosco."),
    "ready":       ("🏪 Pronto para retirada!", "Seu pedido #{order} está pronto para ser retirado na loja."),
}


async def send_push_to_user(
    app_id: str,
    api_key: str,
    external_id: str,
    title: str,
    message: str,
    url: str = "/",
) -> dict:
    """Envia push para um usuário específico pelo external_user_id (e-mail)."""
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "app_id": app_id,
        "headings": {"en": title, "pt": title},
        "contents": {"en": message, "pt": message},
        "url": url,
        "include_aliases": {"external_id": [external_id]},
        "target_channel": "push",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://onesignal.com/api/v1/notifications",
            headers=headers,
            json=payload,
        )
        return resp.json()


@router.post("/nuvemshop/order")
async def nuvemshop_order_webhook(
    request: Request,
    db: Session = Depends(get_db),
    x_linked_store_id: Optional[str] = Header(None),
    x_store_id: Optional[str] = Header(None),
):
    """
    Recebe webhooks de atualização de pedidos da Nuvemshop.
    A Nuvemshop envia o store_id no header X-Linked-Store-Id ou X-Store-Id.
    Payload exemplo:
    {
        "id": 10542,
        "number": 1042,
        "status": "shipped",
        "customer": { "email": "joao@email.com", "name": "João" }
    }
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON"}

    # Pega store_id do header
    store_id = x_linked_store_id or x_store_id
    if not store_id:
        # Tenta pegar do body se vier
        store_id = str(body.get("store_id", ""))

    if not store_id:
        print("[WEBHOOK] store_id não encontrado no header nem no body")
        return {"status": "ignored", "detail": "store_id not found"}

    order_id = body.get("id") or body.get("number", "")
    order_number = body.get("number") or order_id
    status = body.get("status", "").lower()
    customer = body.get("customer", {})
    customer_email = customer.get("email", "")
    customer_name = customer.get("name", "Cliente")

    print(f"[WEBHOOK] Pedido #{order_number} — status: {status} — loja: {store_id} — cliente: {customer_email}")

    if not customer_email:
        print("[WEBHOOK] E-mail do cliente ausente, não é possível enviar push")
        return {"status": "ignored", "detail": "no customer email"}

    if status not in STATUS_MESSAGES:
        print(f"[WEBHOOK] Status '{status}' não mapeado para push")
        return {"status": "ignored", "detail": f"status '{status}' not mapped"}

    app_id, api_key = get_onesignal_credentials(store_id, db)
    if not app_id or not api_key:
        print(f"[WEBHOOK] OneSignal não configurado para loja {store_id}")
        return {"status": "ignored", "detail": "OneSignal not configured"}

    title_tpl, msg_tpl = STATUS_MESSAGES[status]
    title = title_tpl
    message = msg_tpl.replace("{order}", str(order_number)).replace("{name}", customer_name)

    result = await send_push_to_user(
        app_id=app_id,
        api_key=api_key,
        external_id=customer_email,
        title=title,
        message=message,
        url="/minha-conta",
    )

    print(f"[WEBHOOK] Push enviado para {customer_email}: {result}")
    return {"status": "ok", "onesignal": result}


@router.post("/nuvemshop/order/{store_id}")
async def nuvemshop_order_webhook_with_store(
    store_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Alternativa com store_id na URL — útil se a Nuvemshop não enviar no header.
    URL: /webhooks/nuvemshop/order/{store_id}
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON"}

    order_number = body.get("number") or body.get("id", "")
    status = body.get("status", "").lower()
    customer = body.get("customer", {})
    customer_email = customer.get("email", "")
    customer_name = customer.get("name", "Cliente")

    print(f"[WEBHOOK] Pedido #{order_number} — status: {status} — loja: {store_id} — cliente: {customer_email}")

    if not customer_email or status not in STATUS_MESSAGES:
        return {"status": "ignored"}

    app_id, api_key = get_onesignal_credentials(store_id, db)
    if not app_id or not api_key:
        return {"status": "ignored", "detail": "OneSignal not configured"}

    title_tpl, msg_tpl = STATUS_MESSAGES[status]
    title = title_tpl
    message = msg_tpl.replace("{order}", str(order_number)).replace("{name}", customer_name)

    result = await send_push_to_user(
        app_id=app_id,
        api_key=api_key,
        external_id=customer_email,
        title=title,
        message=message,
        url="/minha-conta",
    )

    return {"status": "ok", "onesignal": result}
