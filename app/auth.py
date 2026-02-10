import os
import requests
from fastapi import APIRouter, Depends, HTTPException, Body, Query, BackgroundTasks
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

# Importações internas essenciais
from .database import get_db
from .models import Loja
from .security import create_access_token
from .services import sync_full_store_data # <--- O Robô que baixa os produtos

router = APIRouter()

# ==========================================================
# CONFIGURAÇÕES DE AMBIENTE
# ==========================================================
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://front-end-new-skin-lab-editor-production.up.railway.app")

# URL oficial da Nuvemshop para troca de token
NUVEMSHOP_TOKEN_URL = "https://www.tiendanube.com/apps/authorize/token"

# IMPORTANTE: Esta URL deve ser idêntica à cadastrada no painel da Nuvemshop
# Se no painel estiver ".../auth/callback", aqui também deve estar.
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://web-production-4b8a.up.railway.app/auth/callback")

# ==========================================================
# 1. ROTA PARA GERAR O LINK DE LOGIN
# ==========================================================
@router.get("/nuvemshop/url")
def get_nuvemshop_auth_url():
    """
    O Frontend chama isso para saber para onde mandar o usuário (Login OAuth).
    """
    if not CLIENT_ID:
        raise HTTPException(status_code=500, detail="CLIENT_ID não configurado no servidor.")
    
    # Monta a URL de autorização oficial
    url = f"https://www.tiendanube.com/apps/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}"
    return {"url": url}

# ==========================================================
# 2. ROTA DE CALLBACK (INSTALAÇÃO + SYNC + LOGIN)
# ==========================================================
@router.get("/callback")
def callback(
    code: str = Query(...), 
    background_tasks: BackgroundTasks = None, # Para rodar o sync em segundo plano
    db: Session = Depends(get_db)
):
    """
    Recebe o código da Nuvemshop, autentica a loja, salva no banco,
    DISPARA A SINCRONIZAÇÃO DE PRODUTOS e redireciona para o Dashboard.
    """
    
    # A. Troca o 'code' temporário pelo 'access_token' permanente
    payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code
    }
    
    try:
        res = requests.post(NUVEMSHOP_TOKEN_URL, json=payload)
        data = res.json()
    except Exception as e:
        return {"error": "Erro de conexão com Nuvemshop", "details": str(e)}
    
    if "user_id" not in data or "access_token" not in data:
        # Se falhar, retorna erro claro para debug
        return {"error": "Falha na autenticação Nuvemshop (Verifique Client ID/Secret e Redirect URI)", "details": data}

    store_id = str(data["user_id"])
    access_token_nuvem = data["access_token"]
    
    # B. Tenta pegar o nome da loja (Cosmético, para ficar bonito no painel)
    nome_loja = f"Loja {store_id}"
    try:
        r = requests.get(f"https://api.nuvemshop.com.br/v1/{store_id}/store", headers={"Authentication": f"bearer {access_token_nuvem}"})
        if r.status_code == 200:
            nome_loja = r.json().get('name', {}).get('pt', nome_loja)
    except: 
        pass # Se falhar, usa o ID mesmo
    
    # C. Salva ou Atualiza a Loja no Banco de Dados
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    
    if not loja:
        # Cria nova loja
        loja = Loja(store_id=store_id, access_token=access_token_nuvem, nome_loja=nome_loja)
        db.add(loja)
    else:
        # Atualiza tokens de loja existente
        loja.access_token = access_token_nuvem
        loja.nome_loja = nome_loja
    
    db.commit() # Salva tudo
    
    # D. 🚀 GATILHO DE SINCRONIZAÇÃO (A mágica que faltava)
    # Assim que logar, o robô começa a baixar os produtos em segundo plano.
    if background_tasks:
        print(f"🔄 [AUTH] Login sucesso! Iniciando sincronização automática para Loja {store_id}...")
        background_tasks.add_task(sync_full_store_data, store_id, db)

    # E. Gera o Token Seguro (JWT) para o nosso Frontend
    secure_token = create_access_token(store_id)
    
    # F. Redireciona para o Frontend com o Token na URL
    # O React vai ler isso, salvar no localStorage e liberar o acesso.
    return RedirectResponse(url=f"{FRONTEND_URL}/?token={secure_token}&store_id={store_id}")

# ==========================================================
# 3. LOGIN MANUAL (Opcional, para debug ou acesso direto)
# ==========================================================
@router.post("/login")
def login_store(
    payload: dict = Body(...), 
    db: Session = Depends(get_db)
):
    store_id = str(payload.get("store_id"))
    
    # Verifica se a loja existe no banco
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    if not loja:
        raise HTTPException(status_code=401, detail="Loja não encontrada. Faça a instalação via Nuvemshop primeiro.")
    
    # Gera o token
    access_token = create_access_token(store_id)
    
    return {
        "access_token": access_token, 
        "store_id": store_id,
        "message": "Login realizado."
    }
