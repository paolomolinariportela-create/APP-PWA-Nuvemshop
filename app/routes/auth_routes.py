from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse, JSONResponse
from sqlalchemy.orm import Session
import requests
import os

from ..database import get_db
from ..models import Loja
from ..auth import CLIENT_ID, CLIENT_SECRET, encrypt_token, create_jwt_token
from ..services import inject_script_tag, create_landing_page_internal

router = APIRouter(tags=["Auth"])

FRONTEND_URL = os.getenv("FRONTEND_URL")
if FRONTEND_URL and not FRONTEND_URL.startswith("http"): FRONTEND_URL = f"https://{FRONTEND_URL}"

# Em app/routes/auth_routes.py

@router.get("/install")
def install():
    # URL do seu backend no Railway (SEM BARRA NO FINAL)
    # Exemplo: https://web-production-xxxx.up.railway.app
    BASE_URL = "https://web-production-0b509.up.railway.app" 
    
    # URL para onde a Nuvemshop vai devolver o código
    REDIRECT_URI = f"{BASE_URL}/auth/callback"
    
    auth_url = (
        f"https://www.nuvemshop.com.br/apps/authorize/"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&scope=read_products,write_scripts,write_content"
        f"&redirect_uri={REDIRECT_URI}"  # <--- FALTAVA ISSO!
    )
    
    return RedirectResponse(auth_url, status_code=303)


@router.api_route("/callback", methods=["GET", "POST"])
def callback(code: str = Query(None), db: Session = Depends(get_db)):
    if not code: return RedirectResponse(FRONTEND_URL)
    
    try:
        # 1. Troca CODE por TOKEN
        res = requests.post("https://www.tiendanube.com/apps/authorize/token", json={
            "client_id": CLIENT_ID, "client_secret": CLIENT_SECRET, 
            "grant_type": "authorization_code", "code": code
        })
        if res.status_code != 200:
            return JSONResponse(status_code=400, content={"error": "Falha Login Nuvemshop", "debug": res.text})

        data = res.json()
        store_id = str(data["user_id"])
        raw_token = data["access_token"]
        
        # 2. Salva no Banco
        encrypted = encrypt_token(raw_token)
        loja = db.query(Loja).filter(Loja.store_id == store_id).first()
        
        store_url = ""
        try:
            r = requests.get(f"https://api.tiendanube.com/v1/{store_id}/store", headers={"Authentication": f"bearer {raw_token}"})
            if r.status_code == 200: store_url = r.json().get("url", {}).get("http", "")
        except: pass

        if not loja: db.add(Loja(store_id=store_id, access_token=encrypted, url=store_url))
        else: loja.access_token = encrypted; loja.url = store_url
        db.commit()

        # 3. Executa Serviços
        inject_script_tag(store_id, encrypted)
        create_landing_page_internal(store_id, encrypted, "#000000")

        # 4. Redireciona
        jwt = create_jwt_token(store_id)
        return RedirectResponse(f"{FRONTEND_URL}/admin?token={jwt}", status_code=303)

    except Exception as e:
        print(f"Erro Crítico Callback: {e}")
        return JSONResponse(status_code=500, content={"error": "Erro Interno"})
