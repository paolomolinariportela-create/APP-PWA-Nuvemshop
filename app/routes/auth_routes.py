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
    Cada loja recebe webhooks apontando para a URL com seu store_id.
    Eventos: order/paid, order/packed, order/shipped, order/delivered, order/cancelled
    """
    webhook_base_url = f"{BACKEND_URL}/webhooks/nuvemshop/order/{store_id}"

    # Eventos de pedido que queremos monitorar
    eventos = [
        "order/paid",
        "order/packed",
        "order/fulfilled",
        "order/cancelled",
    ]

    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "AppBuilder (Builder)",
    }

    # Tenta nas duas URLs da API (tiendanube e nuvemshop)
    apis = [
        f"https://api.tiendanube.com/v1/{store_id}/webhooks",
        f"https://api.nuvemshop.com.br/v1/{store_id}/webhooks",
    ]

    # Verifica webhooks já registrados para evitar duplicatas
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

    print(f"[WEBHOOK REGISTER] Webhooks ja existentes para loja {store_id}: {webhooks_existentes}")

    # Registra apenas os que ainda nao existem
    for evento in eventos:
        if evento in webhooks_existentes:
            print(f"[WEBHOOK REGISTER] Evento '{evento}' ja registrado, pulando.")
            continue

        payload = {
            "event": evento,
            "url": webhook_base_url,
        }

        sucesso = False
        for api_url in apis:
            try:
                res = requests.post(api_url, json=payload, headers=headers, timeout=10)
                if res.status_code in (200, 201):
                    print(f"[WEBHOOK REGISTER] '{evento}' registrado para loja {store_id}")
                    sucesso = True
                    break
                elif res.status_code == 404:
                    continue
                else:
                    print(f"[WEBHOOK REGISTER] Erro {res.status_code} para '{evento}': {res.text[:200]}")
                    break
            except Exception as e:
                print(f"[WEBHOOK REGISTER] Exception para '{evento}': {e}")

        if not sucesso:
            print(f"[WEBHOOK REGISTER] Falhou ao registrar '{evento}' para loja {store_id}")


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
                print(f"Pagina criada para loja {store_id}")
                return
            elif res.status_code == 404:
                continue
        except Exception as e:
            print(f"Erro ao criar pagina: {e}")


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
                        print(f"Script ja injetado na loja {store_id}. Pulando.")
                        return
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 404:
            url_alt = f"https://api.nuvemshop.com.br/v1/{store_id}/scripts"
            res = requests.post(url_alt, json=payload, headers=headers)
        if res.status_code == 201:
            print(f"Script injetado na loja {store_id}")
        else:
            print(f"Erro ao injetar script: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Erro ao injetar script: {e}")


@router.get("/install")
def install():
    if not CLIENT_ID:
        return JSONResponse(status_code=500, content={"error": "CLIENT_ID nao configurado"})
    REDIRECT_URI = f"{BACKEND_URL}/auth/callback"
    auth_url = (
        "https://www.nuvemshop.com.br/apps/authorize/"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&scope=read_products,write_scripts,write_content,write_webhooks"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(auth_url, status_code=303)


@router.get("/callback")
@router.post("/callback")
def callback(code: str = Query(None), db: Session = Depends(get_db)):
    if not code:
        return RedirectResponse(f"{FRONTEND_URL}?error=no_code")

    try:
        # 1. Troca CODE por TOKEN
        payload = {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code
        }
        res = requests.post("https://www.nuvemshop.com.br/apps/authorize/token", json=payload)

        if res.status_code != 200:
            print(f"Erro Nuvemshop ({res.status_code}): {res.text}")
            return JSONResponse(status_code=400, content={"error": "Falha na autenticacao", "details": res.text})

        data = res.json()
        if "user_id" not in data or "access_token" not in data:
            return JSONResponse(status_code=400, content={"error": "Resposta invalida da Nuvemshop"})

        store_id = str(data["user_id"])
        raw_token = data["access_token"]
        print(f"Loja autenticada: {store_id}")

        # 2. Busca info da loja
        store_url = ""
        store_domain = ""
        store_name = "Minha Loja"
        email = ""
        try:
            r = requests.get(
                f"https://api.tiendanube.com/v1/{store_id}/store",
                headers={"Authentication": f"bearer {raw_token}"}
            )
            if r.status_code == 200:
                info = r.json()
                store_url = info.get("url_with_protocol") or f"https://{info.get('main_domain')}"
                store_domain = info.get("main_domain") or store_url.replace("https://", "")
                email = info.get("email") or ""
                name_field = info.get("name")
                if isinstance(name_field, dict):
                    store_name = name_field.get("pt") or name_field.get("es") or "Minha Loja"
                elif isinstance(name_field, str):
                    store_name = name_field
        except Exception as e:
            print(f"Falha ao obter detalhes da loja: {e}")

        # 3. Salva no Banco
        encrypted = encrypt_token(raw_token)
        loja = db.query(Loja).filter(Loja.store_id == store_id).first()
        if not loja:
            loja = Loja(store_id=store_id, access_token=encrypted, url=store_url, email=email)
            db.add(loja)
        else:
            loja.access_token = encrypted
            loja.url = store_url
            if email:
                loja.email = email

        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
        is_new_store = config is None
        if not config:
            config = AppConfig(store_id=store_id, app_name=store_name, theme_color="#000000")
            db.add(config)

        db.commit()
        db.refresh(config)

        # 4. Cria app OneSignal se necessario
        if is_new_store or not config.onesignal_app_id:
            print(f"Criando app OneSignal para loja {store_id}...")
            os_result = criar_app_onesignal_sync(store_id, store_domain, store_name)
            if os_result.get("onesignal_app_id"):
                config.onesignal_app_id = os_result["onesignal_app_id"]
                config.onesignal_api_key = os_result["onesignal_api_key"]
                db.commit()
                print(f"OneSignal salvo para loja {store_id}")
        else:
            print(f"Loja {store_id} ja tem OneSignal: {config.onesignal_app_id}")

        # 5. Registra webhooks automaticamente para esta loja
        print(f"Registrando webhooks para loja {store_id}...")
        registrar_webhooks_nuvemshop(store_id, raw_token)

        # 6. Pos-install
        create_landing_page_internal(store_id, raw_token, "#000000")

        # 7. Redireciona para o Painel
        jwt_token = create_jwt_token(store_id)
        return RedirectResponse(f"{FRONTEND_URL}/admin?token={jwt_token}", status_code=303)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": "Erro Interno", "msg": str(e)})


@router.get("/auth/callback")
@router.post("/auth/callback")
def auth_callback_alias(code: str = Query(None), db: Session = Depends(get_db)):
    return callback(code=code, db=db)


@router.get("/force-page")
def force_page(token: str):
    return {"msg": "Use /auth/force-page-real?store_id=X&token=Y"}


@router.get("/force-page-real")
def force_page_real(store_id: str, token: str):
    create_landing_page_internal(store_id, token, "#000000")
    return {"status": "Tentativa feita. Olhe os logs do terminal."}


# ✅ Rota de reregistro manual de webhooks (util para lojas antigas)
@router.get("/admin/reregister-webhooks")
def reregister_webhooks(store_id: str, db: Session = Depends(get_db)):
    """
    Registra/atualiza webhooks para uma loja ja existente.
    Util para lojas instaladas antes dessa funcionalidade existir.
    Chame via: /admin/reregister-webhooks?store_id=6913785
    """
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja:
        return {"error": "Loja nao encontrada"}

    from app.auth import decrypt_token
    raw_token = decrypt_token(loja.access_token)
    if not raw_token:
        return {"error": "Token invalido"}

    registrar_webhooks_nuvemshop(store_id, raw_token)
    return {"status": "ok", "store_id": store_id, "message": "Webhooks registrados. Verifique os logs."}
