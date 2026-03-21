import httpx
from fastapi import APIRouter, Request, Depends, Header
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import AppConfig

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# =============================================
# TEMPLATES PROFISSIONAIS — Plug & Play
# Variaveis disponiveis: {nome}, {pedido}, {loja}
# Futuramente: buscar do banco por loja (aba Automacoes)
# =============================================
MENSAGENS_AUTOMATICAS = {
    "order/paid": {
        "title": "Pagamento Confirmado!",
        "message": "Ola, {nome}! Recebemos seu pagamento do pedido #{pedido}. Ja estamos preparando tudo com carinho!",
        "url": "/minha-conta",
    },
    "order/packed": {
        "title": "Pedido Embalado!",
        "message": "{nome}, seu pedido #{pedido} esta embalado e pronto! Em breve a transportadora fara a coleta.",
        "url": "/minha-conta",
    },
    "order/shipped": {
        "title": "Seu pedido esta a caminho!",
        "message": "Saiu! Seu pedido #{pedido} foi enviado e em breve estara em suas maos, {nome}.",
        "url": "/minha-conta",
    },
    "order/delivered": {
        "title": "Pedido entregue!",
        "message": "Que alegria! Seu pedido #{pedido} chegou, {nome}. Esperamos que voce adore sua compra!",
        "url": "/minha-conta",
    },
    "order/cancelled": {
        "title": "Pedido Cancelado",
        "message": "{nome}, infelizmente seu pedido #{pedido} foi cancelado. Clique para ver os detalhes.",
        "url": "/minha-conta",
    },
    # Alias para eventos que a Nuvemshop pode enviar com status direto
    "packed":    None,
    "shipped":   None,
    "delivered": None,
    "cancelled": None,
    "paid":      None,
}

# Mapeamento de status simples para chave do dicionario
STATUS_ALIAS = {
    "packed":    "order/packed",
    "shipped":   "order/shipped",
    "delivered": "order/delivered",
    "cancelled": "order/cancelled",
    "paid":      "order/paid",
    "open":      None,
    "pending":   None,
    "voided":    None,
    "refunded":  None,
}


def get_onesignal_credentials(store_id: str, db: Session):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return None, None
    return (
        getattr(config, "onesignal_app_id", None),
        getattr(config, "onesignal_api_key", None),
    )


def resolver_template(event_key: str, nome: str, pedido: str) -> Optional[dict]:
    """Resolve o template de mensagem para o evento recebido."""
    template = MENSAGENS_AUTOMATICAS.get(event_key)
    if not template:
        return None
    return {
        "title": template["title"],
        "message": template["message"].format(nome=nome, pedido=pedido),
        "url": template.get("url", "/minha-conta"),
    }


async def disparar_push_por_email(
    app_id: str,
    api_key: str,
    external_id: str,
    title: str,
    message: str,
    url: str = "/minha-conta",
) -> dict:
    """
    Envia push para um usuario especifico via external_user_id (e-mail).
    Funciona porque o loader.js chama OneSignal.login(email) quando o
    cliente esta logado na loja.
    """
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


def extrair_dados_pedido(body: dict) -> dict:
    """Extrai os dados relevantes do payload da Nuvemshop."""
    order_id = body.get("id", "")
    order_number = body.get("number") or order_id

    customer = body.get("customer") or {}
    customer_name = (
        customer.get("name")
        or f"{customer.get('first_name', '')} {customer.get('last_name', '')}".strip()
        or "Cliente"
    )
    customer_email = customer.get("email", "")

    # Status pode vir como campo direto ou dentro de financial_status/shipping_status
    status = (
        body.get("status")
        or body.get("shipping_status")
        or body.get("payment_status")
        or ""
    ).lower()

    return {
        "order_id": str(order_id),
        "order_number": str(order_number),
        "status": status,
        "customer_name": customer_name,
        "customer_email": customer_email,
    }


async def processar_webhook(store_id: str, event: str, body: dict, db: Session) -> dict:
    """Logica central: recebe evento + payload, dispara push se aplicavel."""

    dados = extrair_dados_pedido(body)
    status = dados["status"]
    customer_email = dados["customer_email"]
    customer_name = dados["customer_name"]
    order_number = dados["order_number"]

    print(f"[WEBHOOK] Loja {store_id} | Evento: {event} | Status: {status} | Pedido: #{order_number} | Cliente: {customer_email}")

    # Resolve qual template usar — tenta pelo evento primeiro, depois pelo status
    event_key = event if event in MENSAGENS_AUTOMATICAS else STATUS_ALIAS.get(status)

    if not event_key:
        print(f"[WEBHOOK] Evento '{event}' / status '{status}' nao mapeado — ignorando")
        return {"status": "ignored", "reason": f"event '{event}' not mapped"}

    if not customer_email:
        print(f"[WEBHOOK] E-mail do cliente ausente no pedido #{order_number} — nao e possivel enviar push")
        return {"status": "ignored", "reason": "no customer email"}

    template = resolver_template(event_key, nome=customer_name, pedido=order_number)
    if not template:
        return {"status": "ignored", "reason": "no template"}

    app_id, api_key = get_onesignal_credentials(store_id, db)
    if not app_id or not api_key:
        print(f"[WEBHOOK] OneSignal nao configurado para loja {store_id}")
        return {"status": "ignored", "reason": "OneSignal not configured"}

    result = await disparar_push_por_email(
        app_id=app_id,
        api_key=api_key,
        external_id=customer_email,
        title=template["title"],
        message=template["message"],
        url=template["url"],
    )

    print(f"[WEBHOOK] Push enviado para {customer_email}: {result}")
    return {"status": "ok", "push_result": result}


# =============================================
# ROTAS — duas variantes para maximo de compatibilidade
# =============================================

@router.post("/nuvemshop/order/{store_id}")
async def webhook_com_store_id_na_url(
    store_id: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Rota principal — store_id na URL.
    Registrada automaticamente no install via auth_routes.py.
    URL: POST /webhooks/nuvemshop/order/{store_id}
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON"}

    # O evento pode vir no header X-Nuvemshop-Topic ou no body
    event = request.headers.get("X-Nuvemshop-Topic", "") or request.headers.get("x-nuvemshop-topic", "")
    if not event:
        # Tenta inferir pelo status do pedido
        status = (body.get("status") or "").lower()
        event = STATUS_ALIAS.get(status, "") or ""

    return await processar_webhook(store_id, event, body, db)


@router.post("/nuvemshop/order")
async def webhook_sem_store_id(
    request: Request,
    db: Session = Depends(get_db),
    x_linked_store_id: Optional[str] = Header(None),
    x_store_id: Optional[str] = Header(None),
):
    """
    Rota alternativa — store_id no header.
    Fallback caso a Nuvemshop envie o store_id no header.
    """
    try:
        body = await request.json()
    except Exception:
        return {"status": "error", "detail": "Invalid JSON"}

    store_id = x_linked_store_id or x_store_id or str(body.get("store_id", ""))
    if not store_id:
        return {"status": "ignored", "detail": "store_id not found"}

    event = request.headers.get("X-Nuvemshop-Topic", "") or request.headers.get("x-nuvemshop-topic", "")
    if not event:
        status = (body.get("status") or "").lower()
        event = STATUS_ALIAS.get(status, "") or ""

    return await processar_webhook(store_id, event, body, db)
