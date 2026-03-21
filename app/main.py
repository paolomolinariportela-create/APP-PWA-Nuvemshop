import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import engine, Base

import psycopg2
from psycopg2 import sql


def get_db_url():
    return (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("PGDATABASE_URL")
    )


def ensure_app_config_table_and_columns():
    db_url = get_db_url()
    if not db_url:
        return

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()
    print("[DB MIGRATION] Verificando tabela app_config...")
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

    desired_columns = {
        "fab_position": "VARCHAR",
        "fab_icon": "VARCHAR",
        "fab_animation": "BOOLEAN DEFAULT TRUE",
        "fab_delay": "INTEGER DEFAULT 0",
        "fab_enabled": "BOOLEAN DEFAULT FALSE",
        "fab_text": "VARCHAR DEFAULT 'Baixar App'",
        "fab_color": "VARCHAR DEFAULT '#2563EB'",
        "fab_size": "VARCHAR DEFAULT 'medium'",
        "fab_background_image_url": "TEXT",
        "topbar_enabled": "BOOLEAN DEFAULT FALSE",
        "topbar_text": "VARCHAR DEFAULT 'Baixe nosso app'",
        "topbar_button_text": "VARCHAR DEFAULT 'Baixar'",
        "topbar_icon": "VARCHAR DEFAULT '📲'",
        "topbar_position": "VARCHAR DEFAULT 'bottom'",
        "topbar_color": "VARCHAR DEFAULT '#111827'",
        "topbar_text_color": "VARCHAR DEFAULT '#FFFFFF'",
        "topbar_size": "VARCHAR DEFAULT 'medium'",
        "topbar_button_bg_color": "VARCHAR DEFAULT '#FBBF24'",
        "topbar_button_text_color": "VARCHAR DEFAULT '#111827'",
        "topbar_background_image_url": "TEXT",
        "popup_enabled": "BOOLEAN DEFAULT FALSE",
        "popup_image_url": "TEXT",
        "bottom_bar_bg": "VARCHAR DEFAULT '#FFFFFF'",
        "bottom_bar_icon_color": "VARCHAR DEFAULT '#6B7280'",
        "onesignal_app_id": "VARCHAR(100)",
        "onesignal_api_key": "VARCHAR(200)",
    }

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'app_config' AND table_schema = 'public';
    """)
    existing_cols = {row[0] for row in cur.fetchall()}

    for col_name, col_type in desired_columns.items():
        if col_name not in existing_cols:
            alter_stmt = sql.SQL(
                "ALTER TABLE app_config ADD COLUMN {name} {ctype};"
            ).format(name=sql.Identifier(col_name), ctype=sql.SQL(col_type))
            try:
                cur.execute(alter_stmt)
                print(f"[DB MIGRATION] Adicionando coluna: {col_name}")
            except Exception as e:
                print(f"[DB MIGRATION] Erro ao adicionar coluna {col_name}: {e}")

    cur.close()
    conn.close()
    print("[DB MIGRATION] app_config OK.")


def ensure_lojas_logo_column():
    db_url = get_db_url()
    if not db_url:
        return

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'lojas' AND table_schema = 'public'
        );
    """)
    if not cur.fetchone()[0]:
        cur.close()
        conn.close()
        return

    cur.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'lojas' AND table_schema = 'public';
    """)
    existing_cols = {row[0] for row in cur.fetchall()}

    if "logo_url" not in existing_cols:
        try:
            cur.execute("ALTER TABLE lojas ADD COLUMN logo_url VARCHAR;")
            print("[DB MIGRATION] Coluna logo_url criada em lojas.")
        except Exception as e:
            print(f"[DB MIGRATION] Erro: {e}")

    cur.close()
    conn.close()
    print("[DB MIGRATION] lojas.logo_url OK.")


def run_all_migrations():
    ensure_app_config_table_and_columns()
    ensure_lojas_logo_column()


# IMPORT DAS ROTAS
from app.routes import (
    auth_routes,
    admin_routes,
    loader_routes,
    push_routes,
    analytics_routes,
    pwa_routes,
    stats_routes,
    webhook_routes,
    automacao_routes,
)

# Migracoes + criacao de tabelas
run_all_migrations()
Base.metadata.create_all(bind=engine)

# ✅ SCHEDULER — APScheduler com persistencia no Postgres
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

def criar_scheduler():
    db_url = get_db_url()
    if not db_url:
        print("[SCHEDULER] DATABASE_URL nao encontrado — scheduler sem persistencia")
        jobstores = {}
    else:
        jobstores = {
            "default": SQLAlchemyJobStore(url=db_url)
        }

    scheduler = BackgroundScheduler(
        jobstores=jobstores,
        job_defaults={
            "coalesce": True,       # se atrasou, roda só 1 vez
            "max_instances": 1,     # evita duplicatas
            "misfire_grace_time": 3600,  # tolera 1h de atraso (ex: deploy)
        },
        timezone="America/Sao_Paulo",
    )
    return scheduler

scheduler = criar_scheduler()
scheduler.start()
print("[SCHEDULER] APScheduler iniciado com SQLAlchemyJobStore")

app = FastAPI(
    title="App Builder Pro API",
    description="API Modular para PWAs, Push Notifications, Analytics e Automacoes.",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Disponibiliza o scheduler para as rotas via app.state
app.state.scheduler = scheduler

# Todas as rotas ANTES do StaticFiles
app.include_router(auth_routes.router)
app.include_router(admin_routes.router)
app.include_router(loader_routes.router, tags=["Loader"])
app.include_router(push_routes.router)
app.include_router(analytics_routes.router)
app.include_router(pwa_routes.router, tags=["PWA"])
app.include_router(stats_routes.router)
app.include_router(webhook_routes.router)
app.include_router(automacao_routes.router)


@app.get("/health", tags=["System"])
def health_check():
    jobs = scheduler.get_jobs()
    return {
        "status": "Online",
        "service": "App Builder Pro",
        "scheduler": "running",
        "jobs_agendados": len(jobs),
    }


@app.on_event("shutdown")
def shutdown_scheduler():
    scheduler.shutdown(wait=False)
    print("[SCHEDULER] APScheduler encerrado.")


# Frontend estatico — SEMPRE por ultimo
frontend_path = None
if os.path.exists("frontend/dist"):
    frontend_path = "frontend/dist"
elif os.path.exists("dist"):
    frontend_path = "dist"

if frontend_path:
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
    print(f"Frontend servido de: {frontend_path}")
else:
    print("Aviso: Frontend nao encontrado (modo headless)")
