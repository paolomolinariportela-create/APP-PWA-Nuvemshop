from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# Pega a URL do banco do Railway
DATABASE_URL = os.getenv("DATABASE_URL")

# --- CORREÇÃO IMPORTANTE PARA O RAILWAY ---
# O Railway fornece "postgres://", mas o Python novo exige "postgresql://"
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Cria a conexão
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependência para pegar o banco
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
