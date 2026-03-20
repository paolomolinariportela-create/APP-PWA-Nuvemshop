# app/services/onesignal_service.py
import httpx
import os
import logging

logger = logging.getLogger(__name__)

ONESIGNAL_USER_AUTH_KEY = os.getenv("ONESIGNAL_USER_AUTH_KEY")
ONESIGNAL_ORG_ID = os.getenv("ONESIGNAL_ORG_ID")

BASE_URL = "https://onesignal.com/api/v1"


def _headers():
    return {
        "Authorization": f"User {ONESIGNAL_USER_AUTH_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


async def criar_app_onesignal(
    store_id: str,
    store_domain: str,
    store_name: str,
    icon_url: str = None
) -> dict:
    """
    Cria um app OneSignal para a loja.
    Retorna dict com onesignal_app_id e onesignal_api_key.
    """
    if not ONESIGNAL_USER_AUTH_KEY:
        raise Exception("ONESIGNAL_USER_AUTH_KEY não configurada no ambiente")
    if not ONESIGNAL_ORG_ID:
        raise Exception("ONESIGNAL_ORG_ID não configurada no ambiente")

    icon = icon_url or f"https://{store_domain}/favicon.ico"

    payload = {
        "name": f"PWA - {store_name} ({store_id})",
        "organization_id": ONESIGNAL_ORG_ID,
        "chrome_web_origin": f"https://{store_domain}",
        "chrome_web_default_notification_icon": icon,
        "chrome_web_sub_domain": store_id,
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{BASE_URL}/apps",
            headers=_headers(),
            json=payload
        )

    if resp.status_code not in (200, 201):
        logger.error(f"[OneSignal] Erro ao criar app para {store_id}: {resp.status_code} - {resp.text}")
        raise Exception(f"OneSignal retornou {resp.status_code}: {resp.text}")

    data = resp.json()
    app_id = data.get("id")
    api_key = data.get("basic_auth_key")

    if not app_id:
        raise Exception(f"OneSignal não retornou app_id: {data}")

    logger.info(f"[OneSignal] ✅ App criado para loja {store_id}: app_id={app_id}")

    return {
        "onesignal_app_id": app_id,
        "onesignal_api_key": api_key
    }


async def deletar_app_onesignal(app_id: str) -> bool:
    """
    Deleta o app OneSignal de uma loja (ex: loja desinstalou o PWA).
    """
    if not app_id:
        return False

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.delete(
            f"{BASE_URL}/apps/{app_id}",
            headers=_headers()
        )

    if resp.status_code in (200, 204):
        logger.info(f"[OneSignal] ✅ App {app_id} deletado")
        return True

    logger.warning(f"[OneSignal] Falha ao deletar app {app_id}: {resp.status_code} - {resp.text}")
    return False


async def enviar_notificacao(
    app_id: str,
    api_key: str,
    titulo: str,
    mensagem: str,
    url: str = None,
    segmentos: list = None,
    icone: str = None,
    imagem: str = None,
) -> dict:
    """
    Envia uma notificação push para todos os assinantes da loja.
    """
    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    payload = {
        "app_id": app_id,
        "included_segments": segmentos or ["All"],
        "headings": {"en": titulo, "pt": titulo},
        "contents": {"en": mensagem, "pt": mensagem},
    }

    if url:
        payload["url"] = url
    if icone:
        payload["chrome_web_icon"] = icone
    if imagem:
        payload["chrome_web_image"] = imagem

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{BASE_URL}/notifications",
            headers=headers,
            json=payload
        )

    data = resp.json()

    if resp.status_code not in (200, 201):
        logger.error(f"[OneSignal] Erro ao enviar notificação: {resp.status_code} - {resp.text}")
        raise Exception(f"Erro ao enviar notificação: {data}")

    logger.info(f"[OneSignal] ✅ Notificação enviada: id={data.get('id')} recipients={data.get('recipients')}")
    return data


async def buscar_total_assinantes(app_id: str, api_key: str) -> int:
    """
    Retorna total de assinantes ativos da loja.
    """
    headers = {
        "Authorization": f"Basic {api_key}",
        "Accept": "application/json"
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"{BASE_URL}/apps/{app_id}",
            headers=headers
        )

    if resp.status_code != 200:
        return 0

    data = resp.json()
    return data.get("players", 0)
