# app/auth.py
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from cryptography.fernet import Fernet
from jose import JWTError, jwt

# --- CONFIGURAÇÃO ---
# Tenta pegar NUVEMSHOP_CLIENT_ID (Railway) ou CLIENT_ID (Local/Outros)
CLIENT_ID = os.getenv("NUVEMSHOP_CLIENT_ID") or os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("NUVEMSHOP_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

# Validação Crítica
if not CLIENT_ID or not CLIENT_SECRET:
    print("❌ ERRO CRÍTICO: CLIENT_ID ou CLIENT_SECRET não encontrados! Verifique as variáveis de ambiente.")

if not ENCRYPTION_KEY:
    print("⚠️ AVISO: Usando chave temporária. Configure ENCRYPTION_KEY no Railway para persistência.")
    ENCRYPTION_KEY = Fernet.generate_key().decode()

cipher_suite = Fernet(ENCRYPTION_KEY)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- FUNÇÕES DE CRIPTOGRAFIA (BANCO DE DADOS) ---
def encrypt_token(token: str) -> str:
    """Criptografa o token antes de salvar no banco"""
    if not token: return ""
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> Optional[str]:
    """Descriptografa o token para usar na API da Nuvemshop"""
    try:
        return cipher_suite.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        print(f"Erro Decrypt: {e}")
        return None

# --- FUNÇÕES JWT (LOGIN DO FRONTEND) ---
def create_jwt_token(store_id: str) -> str:
    """Cria o crachá de acesso válido por 24h"""
    # Se CLIENT_SECRET for None (erro de config), usa uma string fallback para não quebrar (apenas dev)
    secret = CLIENT_SECRET or "fallback_secret_dev_only"
    
    expiration = datetime.utcnow() + timedelta(hours=24)
    data = {"sub": store_id, "exp": expiration}
    return jwt.encode(data, secret, algorithm="HS256")

def get_current_store(token: str = Depends(oauth2_scheme)) -> str:
    """Verifica se o crachá é válido"""
    secret = CLIENT_SECRET or "fallback_secret_dev_only"
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        store_id: str = payload.get("sub")
        if store_id is None:
            raise credentials_exception
        return store_id
    except JWTError:
        raise credentials_exception
