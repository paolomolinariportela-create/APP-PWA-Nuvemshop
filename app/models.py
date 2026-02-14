from sqlalchemy import Column, Integer, String
from .database import Base

# Tabela de Lojas (Login e Token)
class Loja(Base):
    __tablename__ = "lojas"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)
    access_token = Column(String)
    email = Column(String, nullable=True)
    url = Column(String, nullable=True)

# Tabela de Configuração (Cores e Nome do App)
class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)
    app_name = Column(String, default="Minha Loja")
    theme_color = Column(String, default="#000000")
    logo_url = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    
class VendaApp(Base):
    __tablename__ = "vendas_app"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    valor = Column(String) # Ex: "150.00"
    data = Column(String)  # Data da venda

class VisitaApp(Base):
    __tablename__ = "visitas_app"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    data = Column(String) # Vamos guardar ISO format
    pagina = Column(String) # Ex: "/" ou "/produto-x"
    is_pwa = Column(Boolean, default=False) # Se está acessando pelo App ou Site
