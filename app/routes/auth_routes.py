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


# ✅ Cria app OneSignal para a loja (síncrono)
def criar_app_onesignal_sync(store_id: str, store_domain: str, store_name: str) -> dict:
    if not ONESIGNAL_USER_AUTH_KEY or not ONESIGNAL_ORG_ID:
        print("⚠️ ONESIGNAL_USER_AUTH_KEY ou ONESIGNAL_ORG_ID não configurados")
        return {}

    # Remove protocolo para usar como subdomínio
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
            print(f"✅ OneSignal app criado para loja {store_id}: {app_id}")
            return {"onesignal_app_id": app_id, "onesignal_api_key": api_key}
        else:
            print(f"❌ OneSignal erro {resp.status_code}: {resp.text}")
            return {}
    except Exception as e:
        print(f"❌ OneSignal exception: {e}")
        return {}


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
    print(f"DEBUG: Tentando criar página para loja {store_id}...")
    for url in urls:
        try:
            print(f"--> Testando POST em: {url}")
            res = requests.post(url, json=payload, headers=headers)
            print(f"    Status: {res.status_code}")
            if res.status_code == 201:
                print("✅ SUCESSO! Página criada.")
                return
            elif res.status_code == 404:
                continue
            else:
                break
        except Exception as e:
            print(f"❌ Erro Exception: {e}")
    print("❌ Todas as tentativas de criar página falharam.")


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
                        print(f"⚠️ Script já injetado na loja {store_id}. Pulando.")
                        return
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 404:
            url_alt = f"https://api.nuvemshop.com.br/v1/{store_id}/scripts"
            res = requests.post(url_alt, json=payload, headers=headers)
        if res.status_code == 201:
            print(f"✅ Script injetado na loja {store_id}")
        else:
            print(f"❌ Erro ao injetar script: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Erro ao injetar script: {e}")


@router.get("/install")
def install():
    if not CLIENT_ID:
        return JSONResponse(status_code=500, content={"error": "CLIENT_ID não configurado no servidor"})
    REDIRECT_URI = f"{BACKEND_URL}/auth/callback"
    auth_url = (
        "https://www.nuvemshop.com.br/apps/authorize/"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&scope=read_products,write_scripts,write_content"
        f"&redirect_uri={REDIRECT_URI}"
    )
    return RedirectResponse(auth_url, status_code=303)


@router.get("/callback")
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
        print(f"DEBUG: Trocando code... CLIENT_ID={CLIENT_ID}")
        res = requests.post("https://www.nuvemshop.com.br/apps/authorize/token", json=payload)

        if res.status_code != 200:
            print(f"❌ Erro Nuvemshop ({res.status_code}): {res.text}")
            return JSONResponse(status_code=400, content={"error": "Falha na autenticação", "details": res.text})

        data = res.json()
        if "user_id" not in data or "access_token" not in data:
            print(f"❌ Resposta incompleta: {data}")
            return JSONResponse(status_code=400, content={"error": "Resposta inválida da Nuvemshop"})

        store_id = str(data["user_id"])
        raw_token = data["access_token"]
        print(f"✅ Sucesso! Loja: {store_id}")

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
                # Pega nome da loja (i18n)
                name_field = info.get("name")
                if isinstance(name_field, dict):
                    store_name = name_field.get("pt") or name_field.get("es") or "Minha Loja"
                elif isinstance(name_field, str):
                    store_name = name_field
        except Exception as e:
            print(f"⚠️ Falha ao obter detalhes da loja: {e}")

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

        # Garante Config Inicial
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
        is_new_store = config is None
        if not config:
            config = AppConfig(store_id=store_id, app_name=store_name, theme_color="#000000")
            db.add(config)

        db.commit()
        db.refresh(config)

        # ✅ Cria app OneSignal apenas se a loja for nova ou ainda não tiver app_id
        if is_new_store or not config.onesignal_app_id:
            print(f"🔔 Criando app OneSignal para loja {store_id}...")
            os_result = criar_app_onesignal_sync(store_id, store_domain, store_name)
            if os_result.get("onesignal_app_id"):
                config.onesignal_app_id = os_result["onesignal_app_id"]
                config.onesignal_api_key = os_result["onesignal_api_key"]
                db.commit()
                print(f"✅ OneSignal salvo para loja {store_id}")
        else:
            print(f"⚠️ Loja {store_id} já tem OneSignal: {config.onesignal_app_id}")

        # 4. Pós-install
        print("🚀 Executando configuração pós-install...")
        create_landing_page_internal(store_id, raw_token, "#000000")

        # 5. Redireciona para o Painel
        jwt_token = create_jwt_token(store_id)
        return RedirectResponse(f"{FRONTEND_URL}/admin?token={jwt_token}", status_code=303)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": "Erro Interno no Servidor", "msg": str(e)})


@router.get("/auth/callback")
def auth_callback_alias(code: str = Query(None), db: Session = Depends(get_db)):
    return callback(code=code, db=db)


@router.get("/force-page")
def force_page(token: str):
    return {"msg": "Use /auth/force-page-real?store_id=X&token=Y"}


@router.get("/force-page-real")
def force_page_real(store_id: str, token: str):
    create_landing_page_internal(store_id, token, "#000000")
    return {"status": "Tentativa feita. Olhe os logs do terminal."}
