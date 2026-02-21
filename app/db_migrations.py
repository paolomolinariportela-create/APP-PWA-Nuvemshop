# db_migrations.py
import os
import psycopg2
from psycopg2 import sql

def get_db_url():
    # Ajuste estes nomes conforme as variáveis que o Railway expõe no seu projeto
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

    # 2) Lista de colunas que queremos garantir
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

        # BOTTOM BAR DO APP (PWA)
        "bottom_bar_bg": "VARCHAR DEFAULT '#FFFFFF'",
        "bottom_bar_icon_color": "VARCHAR DEFAULT '#6B7280'",
    }

    # 3) Descobre quais colunas já existem na tabela
    cur.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'app_config'
          AND table_schema = 'public';
    """)
    existing_cols = {row[0] for row in cur.fetchall()}

    # 4) Cria apenas as colunas que estiverem faltando
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
