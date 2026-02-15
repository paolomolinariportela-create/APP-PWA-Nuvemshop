import os
import requests
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet # Para criptografar o token (se usado)

# --- IMPORTS INTERNOS ---
from app.database import get_db
from app.models import Loja, AppConfig # Importamos AppConfig para criar a config inicial
# Assumindo que CLIENT_ID e SECRET estão em variáveis de ambiente ou config
# Se não tiver um arquivo config.py, defina aqui ou importe de onde estiver
try:
    from app.config import CLIENT_ID, CLIENT_SECRET
except ImportError:
    CLIENT_ID = os.getenv("NUVEMSHOP_CLIENT_ID")
    CLIENT_SECRET = os.getenv("NUVEMSHOP_CLIENT_SECRET")

# Funções auxiliares de Token (Se você já tem um arquivo auth.py, mantenha o import)
# Caso contrário, simplifiquei aqui para funcionar direto
def encrypt_token(token: str) -> str:
    # Simulação: Em produção use criptografia real!
    return token 

def create_jwt_token(store_id: str) -> str:
    # Simulação: Retorna um token simples para o frontend
    # Em produção use JWT real (PyJWT)
    return f"temp_jwt_{store_id}"

router = APIRouter(tags=["Auth"])

# URLs do Ambiente
FRONTEND_URL = os.getenv("FRONTEND_URL") or "http://localhost:5173"
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")

# Garante HTTPS e remove barra final
if FRONTEND_URL and not FRONTEND_URL.startswith("http"): FRONTEND_URL = f"https://{FRONTEND_URL}"
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"
if BACKEND_URL.endswith("/"): BACKEND_URL = BACKEND_URL[:-1]


# --- FUNÇÃO AUXILIAR: CRIA PÁGINA NA LOJA ---
def create_landing_page_internal(store_id: str, access_token: str, theme_color: str):
    """
    Cria a página /pages/app na loja do cliente via API da Nuvemshop.
    """
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/pages"
    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "AppBuilder (Builder)"
    }
    
    html_content = f"""
    <div style="text-align: center; padding: 40px; font-family: sans-serif;">
        <h1 style="color: {theme_color};">Baixe Nosso App Oficial 📱</h1>
        <p style="color: #666; font-size: 18px;">Ofertas exclusivas direto no seu celular.</p>
        
        <div style="margin: 30px 0;">
            <!-- O Script Loader vai transformar isso num botão nativo -->
            <button id="pwa-install-btn" style="background: {theme_color}; color: #fff; padding: 15px 30px; border: none; border-radius: 50px; font-size: 18px; cursor: pointer;">
                📲 Instalar Agora
            </button>
        </div>
        <p style="font-size: 14px; color: #999;">Compatível com Android e iOS</p>
    </div>
    """

    payload = {
        "body": html_content,
        "title": "Baixar App",
        "url": "app",  # Cria /pages/app
        "published": True,
        "type": "raw"
    }

    try:
        # Verifica se a página já existe antes de criar (para não duplicar)
        check = requests.get(url, headers=headers)
        if check.status_code == 200:
            pages = check.json()
            for p in pages:
                if p.get("handle") == "app" or p.get("url") == "app":
                    print(f"⚠️ Página 'app' já existe na loja {store_id}. Pulando criação.")
                    return

        # Cria a página
        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 201:
            print(f"✅ Página '/pages/app' criada com sucesso na loja {store_id}")
        else:
            print(f"❌ Falha ao criar página: {res.text}")
    except Exception as e:
        print(f"❌ Erro de conexão ao criar página: {e}")

# --- FUNÇÃO AUXILIAR: INJETA SCRIPT ---
def inject_script_tag(store_id: str, access_token: str):
    """
    Injeta o loader.js na loja (ScriptTag).
    """
    url = f"https://api.nuvemshop.com.br/v1/{store_id}/scripts"
    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json"
    }
    payload = {
        "src": f"{BACKEND_URL}/loader.js", # Aponta para nosso backend
        "event": "onload"
    }
    try:
        requests.post(url, json=payload, headers=headers)
        print(f"✅ Script injetado na loja {store_id}")
    except Exception as e:
        print(f"❌ Erro ao injetar script: {e}")


# --- ROTAS DE AUTENTICAÇÃO ---

@router.get("/install")
def install():
    """
    Inicia o fluxo OAuth.
    """
    # Monta a URL de Callback baseada no ambiente
    REDIRECT_URI = f"{BACKEND_URL}/auth/callback"
    
    auth_url = (
        f"https://www.nuvemshop.com.br/apps/authorize/"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&scope=read_products,write_scripts,write_content" # Permissões necessárias
        f"&redirect_uri={REDIRECT_URI}" 
    )
    
    return RedirectResponse(auth_url, status_code=303)


@router.get("/callback") # Mudei para GET padrão, mas suporta POST se precisar
def callback(code: str = Query(None), db: Session = Depends(get_db)):
    """
    Recebe o código da Nuvemshop, troca por token e salva no banco.
    """
    if not code:
        return RedirectResponse(f"{FRONTEND_URL}?error=no_code")
    
    try:
        # 1. Troca CODE por TOKEN
        res = requests.post("https://www.nuvemshop.com.br/apps/authorize/token", json={
            "client_id": CLIENT_ID, 
            "client_secret": CLIENT_SECRET, 
            "grant_type": "authorization_code", 
            "code": code
        })
        
        if res.status_code != 200:
            print(f"Erro Token: {res.text}")
            return JSONResponse(status_code=400, content={"error": "Falha Login Nuvemshop"})

        data = res.json()
        store_id = str(data["user_id"])
        raw_token = data["access_token"]
        
        # 2. Busca info da loja (URL, Email)
        store_url = ""
        email = ""
        try:
            r = requests.get(f"https://api.nuvemshop.com.br/v1/{store_id}/store", headers={"Authentication": f"bearer {raw_token}"})
            if r.status_code == 200: 
                store_info = r.json()
                # Pega a URL HTTPS principal
                store_url = store_info.get("url_with_protocol") or f"https://{store_info.get('main_domain')}"
                email = store_info.get("email")
        except: 
            pass

        # 3. Salva/Atualiza no Banco (Tabela Loja)
        # encrypt_token é opcional, se não usar criptografia, salve raw_token direto
        encrypted_token = encrypt_token(raw_token) 
        
        loja = db.query(Loja).filter(Loja.store_id == store_id).first()
        if not loja: 
            loja = Loja(store_id=store_id, access_token=encrypted_token, url=store_url, email=email)
            db.add(loja)
        else: 
            loja.access_token = encrypted_token
            loja.url = store_url
            loja.email = email
        
        # Cria config inicial se não existir
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
        if not config:
            db.add(AppConfig(store_id=store_id, app_name="Minha Loja", theme_color="#000000"))
            
        db.commit()

        # 4. Executa Serviços (Cria página e Injeta Script)
        # Importante: Passamos o raw_token (descriptografado) para a API da Nuvemshop
        inject_script_tag(store_id, raw_token)
        create_landing_page_internal(store_id, raw_token, "#000000")

        # 5. Gera JWT e Redireciona para o Painel
        jwt = create_jwt_token(store_id)
        
        # Redireciona para a página de Admin com o token na URL
        return RedirectResponse(f"{FRONTEND_URL}/admin?token={jwt}", status_code=303)

    except Exception as e:
        print(f"Erro Crítico Callback: {e}")
        return JSONResponse(status_code=500, content={"error": "Erro Interno no Servidor"})
