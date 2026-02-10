from sqlalchemy import text
from .database import engine # Use o ponto (.) para indicar que está na mesma pasta

def fix_database(): # O nome TEM que ser fix_database
    print("⚠️  Iniciando reconstrução total e segura do Banco de Dados...")
    
    with engine.connect() as connection:
        # Iniciamos uma transação manual para o Postgres
        with connection.begin():
            try:
                print("➡️  Limpando tabelas antigas...")
                connection.execute(text("DROP TABLE IF EXISTS history_logs CASCADE;"))
                connection.execute(text("DROP TABLE IF EXISTS produtos CASCADE;"))
                connection.execute(text("DROP TABLE IF EXISTS lojas CASCADE;"))

                print("➡️  Criando tabelas com IDs Automáticos (SERIAL)...")
                
                connection.execute(text("""
                    CREATE TABLE lojas (
                        id SERIAL PRIMARY KEY,
                        store_id VARCHAR UNIQUE,
                        access_token VARCHAR,
                        nome_loja VARCHAR,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """))

                connection.execute(text("""
                    CREATE TABLE produtos (
                        id SERIAL PRIMARY KEY,
                        nuvemshop_id VARCHAR UNIQUE,
                        store_id VARCHAR,
                        name VARCHAR,
                        sku VARCHAR,
                        price FLOAT,
                        promotional_price FLOAT,
                        stock INTEGER,
                        image_url VARCHAR,
                        categories_json TEXT,
                        variants_json TEXT,
                        updated_at TIMESTAMP WITH TIME ZONE
                    );
                """))

                connection.execute(text("""
                    CREATE TABLE history_logs (
                        id SERIAL PRIMARY KEY,
                        store_id VARCHAR,
                        action_summary VARCHAR,
                        full_command TEXT,
                        affected_count INTEGER,
                        status VARCHAR,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """))

                print("✅ SUCESSO! Banco de dados novo e IDs corrigidos.")
                
            except Exception as e:
                print(f"❌ ERRO CRÍTICO NO RESET: {e}")
                raise e # Força o erro para sabermos se falhou

if __name__ == "__main__":
    fix_database()
