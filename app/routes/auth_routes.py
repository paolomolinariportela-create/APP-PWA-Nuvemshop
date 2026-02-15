import os
import requests
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

# --- IMPORTS INTERNOS ---
from app.database import get_db
from app.models import Loja, AppConfig

# IMPORTAÇÃO CORRETA DAS VARIÁVEIS DE AMBIENTE (AUTH.PY)
from app.auth import CLIENT_ID, CLIENT_SECRET, encrypt_token, create_jwt_token

router = APIRouter(tags=["Auth"])

# URLs do Ambiente
FRONTEND_URL = os.getenv("FRONTEND_URL") or "http://localhost:5173"
BACKEND_URL = os.getenv("PUBLIC_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")

# Normalização de URLs
if FRONTEND_URL and not FRONTEND_URL.startswith("http"): FRONTEND_URL = f"https://{FRONTEND_URL}"
if BACKEND_URL and not BACKEND_URL.startswith("http"): BACKEND_URL = f"https://{BACKEND_URL}"
if BACKEND_URL and BACKEND_URL.endswith("/"): BACKEND_URL = BACKEND_URL[:-1]


# --- FUNÇÃO AUXILIAR: CRIA PÁGINA NA LOJA (CORRIGIDA) ---
def create_landing_page_internal(store_id: str, access_token: str, theme_color: str):
    """
    Cria a página /pages/app na loja do cliente via API da Nuvemshop.
    CORREÇÃO APLICADA: Usa api.tiendanube.com e estrutura JSON correta.
    """
    url = f"https://api.tiendanube.com/v1/{store_id}/pages"
    
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

    # ESTRUTURA JSON CORRETA PARA NUVEMSHOP
    payload = {
        "page": {
            "title": "Baixar App",
            "content": html_content,
            "url": "app",  # Cria a url /pages/app
            "published": True
        }
    }

    try:
        # Verifica se a página já existe (GET antes do POST)
        check = requests.get(url, headers=headers)
        if check.status_code == 200:
            pages = check.json()
            for p in pages:
                if p.get("url") == "app" or p.get("handle") == "app":
                    print(f"⚠️ Página 'app' já existe na loja {store_id}. Pulando.")
                    return

        # Cria a página (POST)
        res = requests.post(url, json=payload, headers=headers)
        
        if res.status_code == 201:
            print(f"✅ Página '/pages/app' criada com sucesso na loja {store_id}")
        else:
            print(f"❌ Falha ao criar página: {res.status_code} - {res.text}")
            
    except Exception as e:
        print(f"❌ Erro de conexão ao criar página: {e}")


# --- FUNÇÃO AUXILIAR: INJETA SCRIPT ---
def inject_script_tag(store_id: str, access_token: str):
    """
    Injeta o loader.js na loja (ScriptTag).
    """
    url = f"https://api.tiendanube.com/v1/{store_id}/scripts" # Usando tiendanube.com por segurança
    
    headers = {
        "Authentication": f"bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": "AppBuilder (Builder)"
    }
    
    payload = {
        "src": f"{BACKEND_URL}/loader.js", 
        "event": "onload"
    }
    
    try:
        # Verifica scripts existentes para não duplicar
        check = requests.get(url, headers=headers)
        if check.status_code == 200:
            scripts = check.json()
            for s in scripts:
                if "loader.js" in s.get("src", ""):
                    print(f"⚠️ Script já injetado na loja {store_id}. Pulando.")
                    return

        res = requests.post(url, json=payload, headers=headers)
        if res.status_code == 201:
            print(f"✅ Script injetado na loja {store_id}")
        else:
            print(f"❌ Erro ao injetar script: {res.text}")
            
    except Exception as e:
        print(f"❌ Erro ao injetar script: {e}")


# --- ROTAS DE AUTENTICAÇÃO ---

@router.get("/install")
def install():
    """
    Inicia o fluxo OAuth.
    """
    if not CLIENT_ID:
        return JSONResponse(status_code=500, content={"error": "CLIENT_ID não configurado no servidor"})

    REDIRECT_URI = f"{BACKEND_URL}/auth/callback"
    
    auth_url = (
        f"https://www.nuvemshop.com.br/apps/authorize/"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&scope=read_products,write_scripts,write_content" # write_content é vital para criar páginas!
        f"&redirect_uri={REDIRECT_URI}" 
    )
    
    return RedirectResponse(auth_url, status_code=303)


@router.get("/callback")
def callback(code: str = Query(None), db: Session = Depends(get_db)):
    """
    Callback Blindado: Trata erros da Nuvemshop e evita quebra do servidor.
    """
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
            return JSONResponse(status_code=400, content={
                "error": "Falha na autenticação com a Nuvemshop", 
                "details": res.text
            })

        data = res.json()
        
        # VERIFICA SE OS CAMPOS EXISTEM
        if "user_id" not in data or "access_token" not in data:
            print(f"❌ Resposta incompleta: {data}")
            return JSONResponse(status_code=400, content={"error": "Resposta inválida da Nuvemshop"})

        store_id = str(data["user_id"])
        raw_token = data["access_token"]
        
        print(f"✅ Sucesso! Loja: {store_id}")
        
        # 2. Busca info da loja
        store_url = ""
        email = ""
        try:
            r = requests.get(f"https://api.tiendanube.com/v1/{store_id}/store", headers={"Authentication": f"bearer {raw_token}"})
            if r.status_code == 200: 
                info = r.json()
                store_url = info.get("url_with_protocol") or f"https://{info.get('main_domain')}"
                email = info.get("email")
        except Exception as e: 
            print(f"⚠️ Aviso: Falha ao obter detalhes da loja: {e}")

        # 3. Salva no Banco
        encrypted = encrypt_token(raw_token)
        loja = db.query(Loja).filter(Loja.store_id == store_id).first()
        
        if not loja: 
            loja = Loja(store_id=store_id, access_token=encrypted, url=store_url, email=email)
            db.add(loja)
        else: 
            loja.access_token = encrypted
            loja.url = store_url
            if email: loja.email = email
            
        # Garante Config Inicial
        config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
        if not config:
             db.add(AppConfig(store_id=store_id, app_name="Minha Loja", theme_color="#000000"))
             
        db.commit()

        # 4. Executa Serviços (Página e Scripts)
        print("🚀 Executando configuração pós-install...")
        create_landing_page_internal(store_id, raw_token, "#000000")
        inject_script_tag(store_id, raw_token)

        # 5. Redireciona para o Painel
        jwt = create_jwt_token(store_id)
        return RedirectResponse(f"{FRONTEND_URL}/admin?token={jwt}", status_code=303)

    except Exception as e:
        import traceback
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"error": "Erro Interno no Servidor", "msg": str(e)})
