from sqlalchemy import create_engine, Column, Integer, String, Boolean, Float, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
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

# --- TABELAS ---

class Loja(Base):
    __tablename__ = "lojas"
    store_id = Column(String, primary_key=True, index=True)
    access_token = Column(String)
    nome_loja = Column(String)
    email = Column(String, nullable=True)

class Produto(Base):
    __tablename__ = "produtos"
    id = Column(String, primary_key=True, index=True)
    store_id = Column(String, index=True)
    name = Column(String)
    price = Column(Float)
    stock = Column(Integer, default=0)
    sku = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
    product_url = Column(String, nullable=True)
    categories_json = Column(JSON, nullable=True)
    variants_json = Column(JSON, nullable=True)
    tags = Column(String, nullable=True) # Novo para PWA (filtros)

# --- A NOVIDADE: CONFIGURAÇÃO DO PWA ---
class AppConfig(Base):
    __tablename__ = "app_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True) # Um App por Loja
    
    app_name = Column(String, default="Minha Loja")
    theme_color = Column(String, default="#000000") # Cor do topo do celular
    logo_url = Column(String, nullable=True) # URL da logo
    
    whatsapp_number = Column(String, nullable=True) # Para botão flutuante
    instagram_url = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True) # Controle de pagamento
