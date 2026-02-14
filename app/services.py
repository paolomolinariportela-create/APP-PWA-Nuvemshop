# services.py
import os
import requests
from .auth import decrypt_token # Importa do arquivo que acabamos de criar

# URLs
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"

def inject_script_tag(store_id: str, encrypted_access_token: str):
    """Injeta o loader.js na loja"""
    access_token = decrypt_token(encrypted_access_token)
    if not access_token: return

    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/scripts"
        headers = { "Authentication": f"bearer {access_token}", "User-Agent": "App PWA Builder" }
        
        script_url = f"{BACKEND_URL}/loader.js?store_id={store_id}"
        payload = { 
            "name": "PWA Loader Pro", 
            "description": "App PWA",
            "html": f"<script src='{script_url}' async></script>", 
            "event": "onload", 
            "where": "store" 
        }

        # Verifica se já existe para não duplicar
        check = requests.get(url, headers=headers)
        if check.status_code == 200:
            scripts = check.json()
            if isinstance(scripts, list):
                for script in scripts:
                    if "PWA Loader" in script.get("name", ""):
                        return

        requests.post(url, json=payload, headers=headers)
        print(f"✅ Script injetado na loja {store_id}")
    except Exception as e:
        print(f"❌ Erro Script: {e}")

def create_landing_page_internal(store_id: str, encrypted_access_token: str, color: str):
    """Cria a página /pages/app"""
    access_token = decrypt_token(encrypted_access_token)
    if not access_token: return

    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/pages"
        headers = { "Authentication": f"bearer {access_token}", "User-Agent": "App PWA Builder" }
        
        html_body = f"""
        <div style="text-align: center; padding: 40px 20px; font-family: sans-serif;">
            <div style="background: #f9f9f9; padding: 30px; border-radius: 20px; display: inline-block; max-width: 400px; width: 100%; box-shadow: 0 4px 15px rgba(0,0,0,0.05);">
                <h1 style="margin: 0 0 10px 0; color: #333;">Baixe Nosso App 📲</h1>
                <p style="color: #666; margin-bottom: 25px;">Navegue mais rápido e receba ofertas exclusivas.</p>
                <button onclick="if(window.installPWA) {{ window.installPWA() }} else {{ alert('Abra esta página no celular para instalar!') }}" style="background-color: {color}; color: white; border: none; padding: 15px 30px; font-size: 18px; border-radius: 50px; cursor: pointer; width: 100%; font-weight: bold; box-shadow: 0 4px 10px rgba(0,0,0,0.2);">Instalar Agora ⬇️</button>
                <p style="font-size: 12px; color: #999; margin-top: 15px;">Disponível para Android e iOS</p>
            </div>
        </div>
        """
        
        # Cria a página
        requests.post(url, json={"title":"Baixe o App", "body":html_body, "published":True, "handle":"app"}, headers=headers)
        print(f"✅ Página criada na loja {store_id}")
    except Exception as e:
        print(f"❌ Erro Page: {e}")
