from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Importações internas do projeto
from .database import engine, Base
# ❌ REMOVIDO: from .routes import router (O arquivo antigo)
# ✅ ADICIONADO: Os novos roteadores modulares
from .routers import products, chat, history
from .fix_db import fix_database
from . import webhooks
from . import auth 

# ==========================================
# ⚙️ CICLO DE VIDA (LIFESPAN)
# ==========================================
# Isso garante que o banco seja criado/corrigido ANTES do app começar a responder.
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 [STARTUP] Inicializando Banco de Dados...")
    try:
        # 1. Cria as tabelas se não existirem
        Base.metadata.create_all(bind=engine)
        
        # 2. Aplica correções de esquema (se houver)
        fix_database()
        print("✅ [STARTUP] Banco de Dados verificado e pronto.")
    except Exception as e:
        print(f"❌ [STARTUP] Erro crítico no banco: {e}")
    
    yield # O sistema roda aqui
    
    print("🛑 [SHUTDOWN] Sistema desligando...")

# ==========================================
# CONFIGURAÇÃO DO APP
# ==========================================

app = FastAPI(
    title="NewSkin Lab API",
    description="Sistema Inteligente de Gestão para Nuvemshop (Secured & Modular)",
    version="1.4.0",
    lifespan=lifespan # <--- Conectamos o ciclo de vida aqui
)

# ==========================================
# 🛡️ A MURALHA DIGITAL (CORS)
# ==========================================
# Lista estrita de origens permitidas
origins = [
    "https://front-end-new-skin-lab-editor-production.up.railway.app",
    # "http://localhost:3000", # Descomente apenas se for testar localmente
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Permite GET, POST, PUT, DELETE, etc.
    allow_headers=["*"], # Permite Authorization, Content-Type, etc.
)

# ==========================================
# 🚦 ROTAS DO SISTEMA (MODULARIZADO)
# ==========================================

# 1. Autenticação (Login e Token)
app.include_router(auth.router, prefix="/auth", tags=["Autenticação"])

# 2. Webhooks (Notificações da Nuvemshop)
app.include_router(webhooks.router, prefix="/webhooks", tags=["Webhooks"])

# 3. Rotas de Produtos (Listagem, Status, Sync)
app.include_router(products.router, tags=["Produtos"])

# 4. Rotas de Chat (IA e Comandos)
app.include_router(chat.router, tags=["IA & Chat"])

# 5. Rotas de Histórico (Logs e Reversão)
app.include_router(history.router, tags=["Histórico"])

# ==========================================
# ❤️ HEALTH CHECK (Monitoramento)
# ==========================================
@app.get("/")
def health_check():
    return {
        "status": "online", 
        "security": "active",
        "auth": "ready",
        "structure": "modular",
        "version": "1.4.0"
    }
