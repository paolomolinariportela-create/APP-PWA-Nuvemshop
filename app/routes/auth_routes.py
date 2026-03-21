import os
import requests
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Loja, AppConfig
from app.auth import CLIENT_ID, CLIENT_SECRET, encrypt_token, create_jwt_token

router = APIRouter(tags=["Auth"])

FRONTEND_URL = os.getenv("FRONTEND_URL") or "http://localhost:5173"
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
ONESIGNAL_USER_AUTH_KEY = os.getenv("ONESIGNAL_USER_AUTH_KEY")
ONESIGNAL_ORG_ID = os.getenv("ONESIGNAL_ORG_ID")

if FRONTEND_URL and not FRONTEND_URL.startswith("http"):
    FRONTEND_URL = f"https://{FRONTEND_URL}"
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"
if BACKEND_URL and BACKEND_URL.endswith("/"):
    BACKEND_URL = BACKEND_URL[:-1]


def criar_app_onesignal_sync(store_id: str, store_domain: str, store_name: str) -> dict:
    if not ONESIGNAL_USER_AUTH_KEY or not ONESIGNAL_ORG_ID:
        print("ONESIGNAL_USER_AUTH_KEY ou ONESIGNAL_ORG_ID nao configurados")
        return {}

    domain_clean = store_domain.replace("https://", "").replace("http://", "").rstrip("/")

    payload = {
        "name": f"PWA - {store_name} ({store_id})",
        "organization_id": ONESIGNAL_ORG_ID,
        "chrome_web_origin": f"https://{domain_clean}",
        "chrome_web_default_notification_icon": f"https://{domain_clean}/favicon.ico",
        "chrome_web_sub_domain": store_id,
    }

    try:
        resp = requests.post(
            "https://onesignal.com/api/v1/apps",
            headers={
                "Authorization": f"User {ONESIGNAL_USER_AUTH_KEY}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=15
        )
        data = resp.json()

        if resp.status_code in (200, 201):
            app_id = data.get("id")
            api_key = data.get("basic_auth_key")
            print(f"OneSignal app criado para loja {store_id}: {app_id}")
            return {"onesignal_app_id": app_id, "onesignal_api_key": api_key}
        else:
            print(f"OneSignal erro {resp.status_code}: {resp.text}")
            return {}
    except Exception as e:
        print(f"OneSignal exception: {e}")
        return {}


def registrar_webhooks_nuvemshop(store_id: str, access_token: str):
    """
    Registra automaticamente os webhooks necessários na Nuvemshop.
    Eventos em PLURAL conforme exigido pela API v1.
    """
    webhook_base_url = f"{BACKEND_URL}/webhooks/nuvemshop/order/{store_id}"

    # ✅ CORREÇÃO: Nomes no plural
    eventos = [
        "orders/paid",
        "orders/packed",
        "orders/shipped",
        "orders/delivered",
        "orders/cancelled",
    ]

    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "AppBuilder (Builder)",
    }

    apis = [
        f"https://api.tiendanube.com/v1/{store_id}/webhooks",
        f"https://api.nuvemshop.com.br/v1/{store_id}/webhooks",
    ]

    webhooks_existentes = set()
    for api_url in apis:
        try:
            check = requests.get(api_url, headers=headers, timeout=10)
            if check.status_code == 200:
                existentes = check.json()
                if isinstance(existentes, list):
                    for w in existentes:
                        if isinstance(w, dict):
                            webhooks_existentes.add(w.get("event", ""))
                break
        except Exception:
            continue

    for evento in eventos:
        if evento in webhooks_existentes:
            continue

        payload = {
            "event": evento,
            "url": webhook_base_url,
        }

        for api_url in apis:
            try:
                res = requests.post(api_url, json=payload, headers=headers, timeout=10)
                if res.status_code in (200, 201):
                    print(f"[WEBHOOK] '{evento}' registrado com sucesso.")
                    break
                elif res.status_code == 404:
                    continue
                else:
                    print(f"[WEBHOOK] Erro {res.status_code} em {evento}: {res.text}")
                    break
            except Exception as e:
                print(f"[WEBHOOK] Erro: {e}")


def create_landing_page_internal(store_id: str, access_token: str, theme_color: str):
    urls = [
        f"https://api.tiendanube.com/v1/{store_id}/pages",
        f"https://api.nuvemshop.com.br/v1/{store_id}/pages"
    ]
    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "AppBuilder (Builder)"
    }
    payload = {
        "page": {
            "publish": True,
            "i18n": {
                "pt_BR": {
                    "title": "Baixar App",
                    "content": "<h1>Baixe Nosso App</h1>",
                    "handle": "app",
                    "seo_title": "Baixe o app da loja",
                    "seo_description": "Instale o app da nossa loja no seu celular"
                }
            }
        }
    }
    for url in urls:
        try:
            res = requests.post(url, json=payload, headers=headers)
            if res.status_code == 201:
                return
        except Exception:
            pass


def inject_script_tag(store_id: str, access_token: str):
    url = f"https://api.tiendanube.com/v1/{store_id}/scripts"
    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "AppBuilder (Builder)"
    }
    payload = {
        "src": f"{BACKEND_URL}/loader.js?store_id={store_id}",
        "event": "onload"
    }
    try:
        check = requests.get(url, headers=headers)
        if check.status_code == 200:
            scripts = check.json()
            if isinstance(scripts, list):
                for s in scripts:
                    if isinstance(s, dict) and "loader.js" in s.get("src", ""):
                        return
        requests.post(url, json=payload, headers=headers)
    except Exception:
        pass


@router.get("/install")
def install():
    if not CLIENT_ID:
        return JSONResponse(status_code=500, content={"error": "CLIENT_ID nao configurado"})
    
    REDIRECT_URI = f"{BACKEND_URL}/auth/callback"
    
    # ✅ CORREÇÃO: Adicionado 'read_orders' e 'write_webhooks'
    scope = "read_products,read_orders,write_scripts,write_content,write_webhooks"
    
    auth_url = (
        "https://www.nuvemshop.com.br/apps/authorize/"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(auth_url, status_code=303)


@router.get("/callback")
def callback(code: str = Query(None), db: Session = Depends(get_db)):
    if not code:
        return RedirectResponse(f"{FRONTEND_URL}?error=no_code")

    try:
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code
        }
        res = requests.post("https://www.nuvemshop.com.br/apps/authorize/token", json=payload)

        if res.status_code != 200:
            return JSONResponse(status_code=400, content={"error": "Falha na autenticacao"})

        data = res.json()
        store_id = str(data["user_id"])
        raw_token = data["access_token"]

        # Busca info da loja
        store_url = ""
        store_domain = ""
        store_name = "Minha Loja"
        try:
            r = requests.get(
                f"https://api.tiendanube.com/v1/{store_id}/store",
                headers={"Authentication": f"bearer {raw_token}"}
            )
            if r.status_code == 200:
                info = r.json()
                store_url = info.get("url_with_protocol") or f"https://{info.get('main_domain')}"
                store_domain = info.get("main_domain")
                name_field = info.get("name")
                store_name = name_field.get("pt") if isinstance(name_field, dict) else name_field
        except Exception:
            pass

        # Salva no Banco
        encrypted = encrypt_token(raw_token)
        loja = db.query(Loja).filter(Loja.store_id == store_id).first()
        if not loja:
            loja = Loja(store_id=store_id, access_token=encrypted, url=store_url)
            db.add(loja)
        else:
            loja.access_token = encrypted

        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
        is_new_store = config is None
        if not config:
            config = AppConfig(store_id=store_id, app_name=store_name)
            db.add(config)

        db.commit()

        # OneSignal
        if is_new_store or not config.onesignal_app_id:
            os_result = criar_app_onesignal_sync(store_id, store_domain, store_name)
            if os_result.get("onesignal_app_id"):
                config.onesignal_app_id = os_result["onesignal_app_id"]
                config.onesignal_api_key = os_result["onesignal_api_key"]
                db.commit()

        # Webhooks
        registrar_webhooks_nuvemshop(store_id, raw_token)
        
        # Scripts e Paginas
        inject_script_tag(store_id, raw_token)
        create_landing_page_internal(store_id, raw_token, "#000000")

        jwt_token = create_jwt_token(store_id)
        return RedirectResponse(f"{FRONTEND_URL}/admin?token={jwt_token}", status_code=303)

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

@router.get("/auth/callback")
def auth_callback_alias(code: str = Query(None), db: Session = Depends(get_db)):
    return callback(code=code, db=db)

@router.get("/admin/reregister-webhooks")
def reregister_webhooks(store_id: str, db: Session = Depends(get_db)):
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja: return {"error": "Loja nao encontrada"}
    from app.auth import decrypt_token
    raw_token = decrypt_token(loja.access_token)
    registrar_webhooks_nuvemshop(store_id, raw_token)
    return {"status": "ok", "message": "Tentativa de registro concluida. Veja os logs."}
