# services.py
import os
import requests
from .auth import decrypt_token # Importa do arquivo que já existe

# URLs Globais (Mantendo a lógica original)
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"

def inject_script_tag(store_id: str, encrypted_access_token: str):
    """Injeta o loader.js na loja"""
    access_token = decrypt_token(encrypted_access_token)
    if not access_token: return

    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/scripts"
        headers = { "Authentication": f"bearer {access_token}", "User-Agent": "App PWA Builder" }
        
        # O script aponta para o seu backend
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
                    # Se já existe um script nosso, não cria outro
                    if "PWA Loader" in script.get("name", ""):
                        print(f"⚠️ Script já existe na loja {store_id}")
                        return

        # Cria o script se não existir
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 201:
            print(f"✅ Script injetado na loja {store_id}")
        else:
            print(f"⚠️ Falha ao injetar script: {res.text}")
            
    except Exception as e:
        print(f"❌ Erro Script: {e}")

def create_landing_page_internal(store_id: str, encrypted_access_token: str, color: str):
    """
    Cria ou atualiza a página /pages/app com um Template Otimizado para Conversão.
    Detecta se é iPhone ou Android e mostra instruções específicas.
    """
    access_token = decrypt_token(encrypted_access_token)
    if not access_token: return

    try:
        url = f"https://api.tiendanube.com/v1/{store_id}/pages"
        headers = { "Authentication": f"bearer {access_token}", "User-Agent": "App PWA Builder" }
        
        # --- HTML OTIMIZADO PARA ALTA CONVERSÃO ---
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
        </style>

        <div class="app-landing-wrapper">
            <div class="app-landing-card">
                <!-- Ícone Genérico (Será substituído pelo real se o JS conseguir ler o manifesto) -->
                <div class="app-icon-placeholder">📱</div>
                
                <h1 class="app-title-main">Baixe Nosso App</h1>
                <p class="app-desc-main">Instale agora para acessar ofertas exclusivas e comprar com mais agilidade.</p>
                
                <button onclick="startInstall()" class="install-btn-action">
                    INSTALAR AGORA ⬇️
                </button>

                <!-- Tutorial iOS (Escondido por padrão) -->
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

                <!-- Tutorial Android (Escondido por padrão) -->
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
            </div>
            
            <script>
                // Detecta SO
                var ua = window.navigator.userAgent.toLowerCase();
                var isIOS = /iphone|ipad|ipod/.test(ua);
                var isAndroid = /android/.test(ua);
                
                function startInstall() {{
                    if (window.installPWA) {{
                        window.installPWA();
                    }} else {{
                        // Se a função global do loader.js não estiver disponível
                        if(isIOS) {{
                            document.getElementById('ios-instructions').style.display = 'block';
                            alert("Siga as instruções abaixo para instalar 👇");
                        }} else {{
                            // Assume Android ou Desktop
                            document.getElementById('android-instructions').style.display = 'block';
                        }}
                    }}
                }}
                
                // Se for iOS, mostra instruções logo de cara se o usuário clicar
                if(isIOS) {{
                   // Pode-se optar por mostrar logo ou só no clique.
                   // Deixamos oculto para manter o design limpo até a interação.
                }}
            </script>
        </div>
        """
        
        # Payload para a Nuvemshop
        # handle: "app" força a URL a ser /pages/app
        payload = {
            "title": "Baixe o App", 
            "body": html_body, 
            "published": True, 
            "handle": "app" 
        }
        
        # POST cria uma nova página.
        # Nota: Se já existir uma página com handle "app", a Nuvemshop pode criar "app-1".
        # Idealmente, o lojista deve apagar a antiga antes de "Recriar" pelo painel.
        res = requests.post(url, json=payload, headers=headers)
        
        if res.status_code == 201:
            print(f"✅ Página APP criada na loja {store_id}")
        else:
            print(f"⚠️ Aviso ao criar página: {res.text}")
            
    except Exception as e:
        print(f"❌ Erro Page: {e}")
