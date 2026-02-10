from sqlalchemy import Column, Integer, String, Float, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base

class Loja(Base):
    __tablename__ = "lojas"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)
    access_token = Column(String)
    nome_loja = Column(String)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Produto(Base):
    __tablename__ = "produtos"
    id = Column(Integer, primary_key=True, index=True) # ID interno do banco
    nuvemshop_id = Column(String, unique=True, index=True) # ID da Nuvemshop
    store_id = Column(String, index=True)
    name = Column(String)
    sku = Column(String, nullable=True)
    price = Column(Float, nullable=True)
    promotional_price = Column(Float, nullable=True)
    stock = Column(Integer, nullable=True)
    image_url = Column(String, nullable=True)
    
    # --- NOVO CAMPO AQUI ---
    categories_json = Column(Text, nullable=True) # Vai guardar: "Tênis, Lebron, Basquete"
    # -----------------------

    variants_json = Column(Text, nullable=True) 
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class HistoryLog(Base):
    __tablename__ = "history_logs"
    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String)
    action_summary = Column(String)
    full_command = Column(Text)
    affected_count = Column(Integer)
    status = Column(String) # SUCCESS, ERROR, REVERTED
    created_at = Column(DateTime(timezone=True), server_default=func.now())
