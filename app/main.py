import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- IMPORTS INTERNOS ---
from app.database import engine, Base

# --- MIGRAÇÃO SIMPLES DO app_config E lojas ---
import psycopg2
from psycopg2 import sql


def get_db_url():
    # Ajuste os nomes se seu projeto usar outra variável no Railway
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("PGDATABASE_URL")
    )


def ensure_app_config_table_and_columns():
    db_url = get_db_url()
    if not db_url:
        print("[DB MIGRATION] DATABASE_URL não encontrado nas variáveis de ambiente.")
        return

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    print("[DB MIGRATION] Verificando tabela app_config...")

    # 1) Garante que a tabela app_config exista (mínimo)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS app_config (
            id SERIAL PRIMARY KEY,
            store_id VARCHAR(255) NOT NULL UNIQUE,
            app_name VARCHAR(255),
            theme_color VARCHAR(50),
            logo_url TEXT,
            whatsapp_number VARCHAR(50)
        );
    """)

    # 2) TODAS as colunas que queremos garantir (incluindo novas)
    desired_columns = {
        # FAB
        "fab_position": "VARCHAR",
        "fab_icon": "VARCHAR",
        "fab_animation": "BOOLEAN DEFAULT TRUE",
        "fab_delay": "INTEGER DEFAULT 0",
        "fab_enabled": "BOOLEAN DEFAULT FALSE",
        "fab_text": "VARCHAR DEFAULT 'Baixar App'",
        "fab_color": "VARCHAR DEFAULT '#2563EB'",
        "fab_size": "VARCHAR DEFAULT 'medium'",

        # TOP/BOTTOM BAR (banner / barra do widget)
        "topbar_enabled": "BOOLEAN DEFAULT FALSE",
        "topbar_text": "VARCHAR DEFAULT 'Baixe nosso app'",
        "topbar_button_text": "VARCHAR DEFAULT 'Baixar'",
        "topbar_icon": "VARCHAR DEFAULT '📲'",
        "topbar_position": "VARCHAR DEFAULT 'bottom'",
        "topbar_color": "VARCHAR DEFAULT '#111827'",
        "topbar_text_color": "VARCHAR DEFAULT '#FFFFFF'",
        "topbar_size": "VARCHAR DEFAULT 'medium'",

        # NOVOS CAMPOS – cores independentes do botão da barra
        "topbar_button_bg_color": "VARCHAR DEFAULT '#FBBF24'",
        "topbar_button_text_color": "VARCHAR DEFAULT '#111827'",

        # BOTTOM BAR DO APP (PWA)
        "bottom_bar_bg": "VARCHAR DEFAULT '#FFFFFF'",
        "bottom_bar_icon_color": "VARCHAR DEFAULT '#6B7280'",
    }

    # 3) Colunas existentes hoje
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'app_config'
          AND table_schema = 'public';
    """)
    existing_cols = {row[0] for row in cur.fetchall()}

    # 4) Cria só o que estiver faltando
    for col_name, col_type in desired_columns.items():
        if col_name not in existing_cols:
            alter_stmt = sql.SQL(
                "ALTER TABLE app_config ADD COLUMN {name} {ctype};"
            ).format(
                name=sql.Identifier(col_name),
                ctype=sql.SQL(col_type)
            )
            print(f"[DB MIGRATION] Adicionando coluna: {col_name} ({col_type})")
            try:
                cur.execute(alter_stmt)
            except Exception as e:
                print(f"[DB MIGRATION] Erro ao adicionar coluna {col_name}: {e}")
        else:
            print(f"[DB MIGRATION] Coluna já existe: {col_name}")

    cur.close()
    conn.close()
    print("[DB MIGRATION] app_config OK.")


def ensure_lojas_logo_column():
    db_url = get_db_url()
    if not db_url:
        print("[DB MIGRATION] DATABASE_URL não encontrado nas variáveis de ambiente.")
        return

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    print("[DB MIGRATION] Verificando coluna logo_url em lojas...")

    # Verifica se a tabela lojas existe
    cur.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'lojas'
              AND table_schema = 'public'
        );
    """)
    exists = cur.fetchone()[0]
    if not exists:
        print("[DB MIGRATION] Tabela lojas não existe, nada a fazer.")
        cur.close()
        conn.close()
        return

    # Verifica se a coluna logo_url já existe
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'lojas'
          AND table_schema = 'public';
    """)
    existing_cols = {row[0] for row in cur.fetchall()}

    if "logo_url" not in existing_cols:
        print("[DB MIGRATION] Adicionando coluna logo_url em lojas...")
        try:
            cur.execute("ALTER TABLE lojas ADD COLUMN logo_url VARCHAR;")
            print("[DB MIGRATION] Coluna logo_url criada com sucesso.")
        except Exception as e:
            print(f"[DB MIGRATION] Erro ao adicionar coluna logo_url: {e}")
    else:
        print("[DB MIGRATION] Coluna logo_url já existe em lojas.")

    cur.close()
    conn.close()
    print("[DB MIGRATION] lojas.logo_url OK.")


def run_all_migrations():
    ensure_app_config_table_and_columns()
    ensure_lojas_logo_column()


# --- IMPORT DAS ROTAS ---
from app.routes import (
    auth_routes,
    admin_routes,
    loader_routes,
    push_routes,
    analytics_routes,
    pwa_routes,
)

# 1) Roda as migrações simples antes de criar as tabelas do SQLAlchemy
run_all_migrations()

# 2) Inicializa as tabelas do Banco de Dados gerenciadas pelo SQLAlchemy
Base.metadata.create_all(bind=engine)

# Cria a aplicação FastAPI
app = FastAPI(
    title="App Builder Pro API",
    description="API Modular para criação de PWAs, Push Notifications e Analytics.",
    version="2.0.0",
)

# --- CONFIGURAÇÃO DE CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, ideal restringir aos domínios dos clientes
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- REGISTRO DAS ROTAS (ROUTERS) ---

# 1. Autenticação e Admin
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)

# 2. Funcionalidades do App
app.include_router(loader_routes.router, tags=["Loader"])
app.include_router(push_routes.router)
app.include_router(analytics_routes.router)
app.include_router(pwa_routes.router, tags=["PWA"])


# --- ROTA DE SAÚDE (HEALTH CHECK) ---
@app.get("/health", tags=["System"])
def health_check():
    return {"status": "Online 🚀", "service": "App Builder Pro - Modular API"}


# --- SERVINDO O FRONTEND (Sempre por último) ---
frontend_path = None
if os.path.exists("frontend/dist"):
    frontend_path = "frontend/dist"
elif os.path.exists("dist"):
    frontend_path = "dist"

if frontend_path:
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
    print(f"✅ Frontend servido de: {frontend_path}")
else:
    print("⚠️ Aviso: Pasta do Frontend não encontrada (API rodando em modo headless)")
