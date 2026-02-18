# services.py
import os
import json
import requests
from .auth import decrypt_token

# URLs Globais
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"):
    BACKEND_URL = f"https://{BACKEND_URL}"

# URL do seu site de vendas (para o backlink SEO)
SEU_SITE_VENDAS = "https://www.seusite.com.br"

# --- CONFIGURAÇÃO PUSH (BLINDADA PARA BUILD) ---
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")

raw_claims = os.getenv("VAPID_CLAIMS", '{"sub": "mailto:admin@seuapp.com"}')
try:
    VAPID_CLAIMS = json.loads(raw_claims)
except:
    VAPID_CLAIMS = {"sub": "mailto:admin@seuapp.com"}


def inject_script_tag(store_id: str, encrypted_access_token: str):
    """
    Injeta o loader.js na loja da Nuvemshop.
    Este script carrega o PWA, o Botão Flutuante e pede permissão de Push.
    """
    access_token = decrypt_token(encrypted_access_token)
    if not access_token:
        return

    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/scripts"
        headers = {
            "Authentication": f"bearer {access_token}",
            "User-Agent": "App PWA Builder",
        }

        script_url = f"{BACKEND_URL}/loader.js?store_id={store_id}"

        payload = {
            "name": "PWA Loader Pro",
            "description": "App PWA + Push + Analytics",
            "html": f"<script src='{script_url}' async></script>",
            "event": "onload",
            "where": "store",
        }

        # 1. Verifica se já existe para não duplicar
        check = requests.get(url, headers=headers)
        if check.status_code == 200:
            scripts = check.json()
            if isinstance(scripts, list):
                for script in scripts:
                    if "PWA Loader" in script.get("name", ""):
                        print(f"⚠️ Script já existe na loja {store_id}")
                        return

        # 2. Injeta o novo script
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 201:
            print(f"✅ Script injetado com sucesso na loja {store_id}")
        else:
            print(f"❌ Erro ao injetar script: {res.text}")

    except Exception as e:
        print(f"❌ Exceção no Script: {e}")


def create_landing_page_internal(store_id: str, encrypted_access_token: str, color: str):
    """
    Cria ou atualiza a página /pages/app com Template de Alta Conversão.
    Inclui detecção de iPhone/Android e Backlink SEO.
    """
    access_token = decrypt_token(encrypted_access_token)
    if not access_token:
        return

    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/pages"
        headers = {
            "Authentication": f"bearer {access_token}",
            "User-Agent": "App PWA Builder",
        }

        if not color:
            color = "#000000"

        html_body = f"""
        <style>
            .app-landing-wrapper {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; text-align: center; padding: 40px 20px; background-color: #ffffff; }}
            .app-landing-card {{ background: #fdfdfd; border-radius: 24px; padding: 40px 25px; max-width: 500px; margin: 0 auto; box-shadow: 0 10px 40px rgba(0,0,0,0.06); border: 1px solid #f0f0f0; }}
            
            .app-icon-placeholder {{ width: 80px; height: 80px; background-color: {color}; border-radius: 20px; margin: 0 auto 20px auto; display: flex; align-items: center; justify-content: center; font-size: 40px; color: white; box-shadow: 0 5px 15px rgba(0,0,0,0.1); }}
            
            .app-title-main {{ font-size: 26px; font-weight: 800; color: #111; margin: 0 0 10px 0; letter-spacing: -0.5px; }}
            .app-desc-main {{ font-size: 16px; color: #666; line-height: 1.5; margin-bottom: 30px; }}
            
            .install-btn-action {{ 
                background-color: {color}; color: #fff; border: none; padding: 16px 32px; 
                font-size: 16px; font-weight: bold; border-radius: 50px; cursor: pointer; 
                width: 100%; transition: transform 0.2s; 
                box-shadow: 0 4px 12px rgba(0,0,0,0.15); text-decoration: none; display: inline-block;
                text-transform: uppercase; letter-spacing: 0.5px;
            }}
            .install-btn-action:active {{ transform: scale(0.98); opacity: 0.9; }}
            
            .tutorial-box {{ background: #F8F9FA; border-radius: 16px; padding: 20px; margin-top: 25px; text-align: left; display: none; border: 1px solid #eee; }}
            .tutorial-step {{ display: flex; gap: 12px; margin-bottom: 12px; align-items: flex-start; }}
            .step-circle {{ background: #fff; color: #333; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; flex-shrink: 0; border: 1px solid #ddd; }}
            .step-text {{ font-size: 13px; color: #444; margin: 0; line-height: 1.4; padding-top: 2px; }}
            
            .features-list {{ margin-top: 30px; display: flex; justify-content: center; gap: 15px; font-size: 12px; color: #888; }}
            .feature-item {{ display: flex; align-items: center; gap: 5px; }}
            
            .app-footer-credits {{ margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px; font-size: 11px; color: #aaa; }}
            .app-footer-credits a {{ color: #888; text-decoration: none; transition: color 0.2s; }}
            .app-footer-credits a:hover {{ color: {color}; }}
        </style>

        <div class="app-landing-wrapper">
            <div class="app-landing-card">
                <div class="app-icon-placeholder">📱</div>
                
                <h1 class="app-title-main">Baixe Nosso App</h1>
                <p class="app-desc-main">Instale agora para acessar ofertas exclusivas e comprar com mais agilidade.</p>
                
                <button onclick="startInstall()" class="install-btn-action">
                    INSTALAR AGORA ⬇️
                </button>

                <div id="ios-instructions" class="tutorial-box">
                    <h3 style="margin:0 0 10px 0; font-size:14px; color:#333;">Como instalar no iPhone:</h3>
                    <div class="tutorial-step">
                        <span class="step-circle">1</span>
                        <p class="step-text">Toque no botão <strong>Compartilhar</strong> <span style="font-size:16px">⎋</span> na barra inferior.</p>
                    </div>
                    <div class="tutorial-step">
                        <span class="step-circle">2</span>
                        <p class="step-text">Role para baixo e toque em <strong>"Adicionar à Tela de Início"</strong> <span style="font-size:16px">⊞</span>.</p>
                    </div>
                </div>

                <div id="android-instructions" class="tutorial-box">
                    <h3 style="margin:0 0 10px 0; font-size:14px; color:#333;">Se não abrir automaticamente:</h3>
                    <div class="tutorial-step">
                        <span class="step-circle">1</span>
                        <p class="step-text">Toque nos <strong>Três Pontinhos</strong> no navegador.</p>
                    </div>
                    <div class="tutorial-step">
                        <span class="step-circle">2</span>
                        <p class="step-text">Selecione <strong>"Instalar aplicativo"</strong> ou "Adicionar à tela".</p>
                    </div>
                </div>
                
                <div class="features-list">
                    <div class="feature-item">⚡ Mais Rápido</div>
                    <div class="feature-item">🔒 Seguro</div>
                    <div class="feature-item">🔔 Notificações</div>
                </div>

                <div class="app-footer-credits">
                    <a href="{SEU_SITE_VENDAS}" target="_blank">
                        Desenvolvido por <strong>App Builder PRO</strong>
                    </a>
                </div>
            </div>
            
            <script>
                var ua = window.navigator.userAgent.toLowerCase();
                var isIOS = /iphone|ipad|ipod/.test(ua);
                
                function startInstall() {{
                    if (window.installPWA) {{
                        window.installPWA();
                    }} else {{
                        if(isIOS) {{
                            document.getElementById('ios-instructions').style.display = 'block';
                            alert("Siga as instruções abaixo para instalar 👇");
                        }} else {{
                            document.getElementById('android-instructions').style.display = 'block';
                        }}
                    }}
                }}
            </script>
        </div>
        """

        payload = {
            "title": "Baixe o App",
            "body": html_body,
            "published": True,
            "handle": "app",
        }

        res = requests.post(url, json=payload, headers=headers)

        if res.status_code == 201:
            print(f"✅ Página APP criada com sucesso na loja {store_id}")
        else:
            print(f"⚠️ Aviso ao criar página (talvez já exista): {res.text}")

    except Exception as e:
        print(f"❌ Exceção ao criar Página: {e}")
