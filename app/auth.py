# auth.py
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from cryptography.fernet import Fernet
from jose import JWTError, jwt

# --- CONFIGURAÇÃO ---
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    print("⚠️ AVISO: Usando chave temporária. Configure ENCRYPTION_KEY no Railway.")
    ENCRYPTION_KEY = Fernet.generate_key().decode()

cipher_suite = Fernet(ENCRYPTION_KEY)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- FUNÇÕES DE CRIPTOGRAFIA (BANCO DE DADOS) ---
def encrypt_token(token: str) -> str:
    return cipher_suite.encrypt(token.encode()).decode()

def decrypt_token(encrypted_token: str) -> Optional[str]:
    try:
        return cipher_suite.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        print(f"Erro Decrypt: {e}")
        return None

# --- FUNÇÕES JWT (LOGIN DO FRONTEND) ---
def create_jwt_token(store_id: str) -> str:
    """Cria o crachá de acesso válido por 24h"""
    expiration = datetime.utcnow() + timedelta(hours=24)
    data = {"sub": store_id, "exp": expiration}
    return jwt.encode(data, CLIENT_SECRET, algorithm="HS256")

def get_current_store(token: str = Depends(oauth2_scheme)) -> str:
    """Verifica se o crachá é válido"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, CLIENT_SECRET, algorithms=["HS256"])
        store_id: str = payload.get("sub")
        if store_id is None:
            raise credentials_exception
        return store_id
    except JWTError:
        raise credentials_exception
