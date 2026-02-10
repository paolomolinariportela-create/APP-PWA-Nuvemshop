import hmac
import hashlib
import os
import jwt
import datetime
import uuid
from fastapi import HTTPException, Header

# ==============================================================================
# CONFIGURAÇÕES DE SEGURANÇA (BLINDAGEM)
# ==============================================================================

CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
JWT_SECRET = os.getenv("JWT_SECRET", "")
# Define o algoritmo como constante para evitar ataques de troca de algoritmo
ALGORITHM = "HS256"

# 1. VALIDAÇÃO DE INICIALIZAÇÃO (Check-up de Segurança)
if not CLIENT_SECRET or not JWT_SECRET:
    print("🚨 [SEGURANÇA] ERRO CRÍTICO: Variáveis CLIENT_SECRET ou JWT_SECRET estão vazias!")
    # Em produção real, poderíamos forçar o encerramento do app aqui, 
    # mas vamos apenas alertar para não derrubar o servidor agora.
elif len(JWT_SECRET) < 32:
    print("⚠️ [SEGURANÇA] ALERTA: Sua JWT_SECRET é muito curta! Recomenda-se usar pelo menos 32 caracteres aleatórios.")

# 2. VERIFICADOR DE WEBHOOK (Assinatura Digital)
def verify_nuvemshop_signature(body_bytes: bytes, received_hmac: str) -> bool:
    """
    Verifica se a notificação veio realmente da Nuvemshop comparando as assinaturas HMAC.
    """
    if not CLIENT_SECRET:
        return False
    if not received_hmac:
        return False

    signature = hmac.new(
        key=CLIENT_SECRET.encode('utf-8'),
        msg=body_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()

    # Usa compare_digest para evitar ataques de tempo (Timing Attacks)
    return hmac.compare_digest(signature, received_hmac)

# 3. CRIADOR DE TOKEN (A Fábrica de Crachás)
def create_access_token(store_id: str):
    """
    Gera um token JWT assinado contendo a identidade da loja.
    """
    if not JWT_SECRET:
        raise ValueError("Servidor mal configurado: JWT_SECRET ausente.")

    now = datetime.datetime.now(datetime.timezone.utc)
    expiration = now + datetime.timedelta(hours=24) # Validade de 24h
    
    payload = {
        "sub": store_id,          # Subject: Padrão JWT para identificar o dono
        "store_id": store_id,     # Custom Claim: Para facilitar nosso uso
        "exp": expiration,        # Expiration: Quando expira
        "iat": now,               # Issued At: Quando foi criado
        "jti": str(uuid.uuid4())  # JWT ID: Identificador único deste token específico
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=ALGORITHM)
    return token

# 4. VALIDADOR DE TOKEN (O Porteiro)
def verify_token_access(authorization: str = Header(None)):
    """
    Valida o token Bearer recebido e retorna o store_id se for legítimo.
    """
    # Verificação de Sanidade do Servidor
    if not JWT_SECRET:
        print("🚫 [AUTH] Erro Crítico: JWT_SECRET não carregada no servidor.")
        raise HTTPException(status_code=500, detail="Erro de configuração interna.")

    # Verificação da Presença do Token
    if not authorization:
        raise HTTPException(status_code=401, detail="Token de autenticação ausente.")

    try:
        parts = authorization.split()
        
        # Garante formato "Bearer <token>"
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            raise HTTPException(status_code=401, detail="Formato de token inválido. Use: Bearer <token>")
            
        token = parts[1]
        
        # Decodificação e Validação da Assinatura
        # leeway=30 dá uma tolerância de 30 segundos para relógios dessincronizados
        payload = jwt.decode(
            token, 
            JWT_SECRET, 
            algorithms=[ALGORITHM], # Força o uso de HS256 (Evita ataque 'None')
            leeway=30
        )
        
        store_id = payload.get("store_id")
        
        if not store_id:
            raise HTTPException(status_code=401, detail="Token inválido: Identidade da loja não encontrada.")
            
        return store_id

    except jwt.ExpiredSignatureError:
        # Token era válido, mas venceu
        raise HTTPException(status_code=401, detail="Sessão expirada. Por favor, recarregue a página.")
        
    except jwt.InvalidTokenError:
        # Token é falso, corrompido ou de outro servidor
        print(f"🚫 [AUTH] Tentativa de acesso com token inválido.")
        raise HTTPException(status_code=401, detail="Token inválido ou não autorizado.")
        
    except Exception as e:
        print(f"🚫 [AUTH] Erro desconhecido na validação: {str(e)}")
        raise HTTPException(status_code=401, detail="Erro na verificação de segurança.")
