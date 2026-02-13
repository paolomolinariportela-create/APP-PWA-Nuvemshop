from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- SÓ RESTARAM ESSAS DUAS TABELAS ---

class Loja(Base):
    __tablename__ = "lojas"
    store_id = Column(String, primary_key=True, index=True)
    access_token = Column(String)
    email = Column(String, nullable=True)

class AppConfig(Base):
    __tablename__ = "app_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True) 
    
    app_name = Column(String, default="Minha Loja")
    theme_color = Column(String, default="#000000")
    logo_url = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
