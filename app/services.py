import os
import requests
from sqlalchemy.orm import Session
from app.models import Loja
from .auth import decrypt_token

BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

NUVEMSHOP_API_URL = "https://api.nuvemshop.com.br/v1"


def inject_script_tag(store_id: str, access_token: str):
    """Injeta o loader.js na loja via API da Nuvemshop."""
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
                        print(f"Script já injetado na loja {store_id}. Pulando.")
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


def create_landing_page_internal(store_id: str, access_token: str, theme_color: str):
    """Cria página de download do app na loja."""
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
                print(f"Página criada para loja {store_id}")
                return
            elif res.status_code == 404:
                continue
        except Exception as e:
            print(f"Erro ao criar página: {e}")
    print(f"Falha ao criar página para loja {store_id}")


def sync_store_logo_from_nuvemshop(db: Session, loja: Loja) -> None:
    """Busca a logo da loja na Nuvemshop e salva em Loja.logo_url."""
    if not loja or not loja.access_token or not loja.store_id:
        print("SYNC LOGO: loja, access_token ou store_id ausente")
        return

    raw_token = decrypt_token(loja.access_token)
    if not raw_token:
        print("SYNC LOGO: não conseguiu descriptografar o token")
        return

    try:
        url = f"{NUVEMSHOP_API_URL}/{loja.store_id}/store"
        resp = requests.get(
            url,
            headers={
                "Authentication": f"bearer {raw_token}",
                "User-Agent": "AppBuilder (you@example.com)",
            },
            timeout=5,
        )
        if resp.status_code != 200:
            return

        data = resp.json()
        raw_logo = data.get("logo")
        if raw_logo:
            logo_url = raw_logo if raw_logo.startswith("http") else f"https:{raw_logo}"
            loja.logo_url = logo_url
            db.commit()
            print(f"SYNC LOGO: salvo logo_url = {logo_url}")
    except Exception as e:
        print(f"SYNC LOGO: erro: {e}")
