from sqlalchemy import Column, Integer, String, Boolean, Text
from .database import Base

# Tabela de Lojas (Autenticação e Token)
class Loja(Base):
    __tablename__ = "lojas"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)
    access_token = Column(String)
    email = Column(String, nullable=True)
    url = Column(String, nullable=True)

# Tabela de Configuração (Cores, Nome do App e Widgets)
class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)
    app_name = Column(String, default="Minha Loja")
    theme_color = Column(String, default="#000000")
    logo_url = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)
    
    # --- WIDGETS DE CONVERSÃO ---
    fab_enabled = Column(Boolean, default=False) # Botão Flutuante 'Baixar App'
    fab_text = Column(String, default="Baixar App")

# Tabela de Vendas (Estatísticas)
class VendaApp(Base):
    __tablename__ = "vendas_app"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    valor = Column(String)
    data = Column(String)
    visitor_id = Column(String, index=True, nullable=True)

# Tabela de Visitas (Analytics)
class VisitaApp(Base):
    __tablename__ = "visitas_app"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    data = Column(String)
    pagina = Column(String)
    is_pwa = Column(Boolean, default=False)
    visitor_id = Column(String, index=True, nullable=True)

# Tabela de Notificações (Web Push)
class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    visitor_id = Column(String, index=True)
    
    # Dados técnicos do WebPush
    endpoint = Column(Text, nullable=False) # URL única do navegador
    p256dh = Column(String, nullable=False) # Chave Pública 1
    auth = Column(String, nullable=False)   # Chave de Auth 2
    
    created_at = Column(String)

# Adicione no final do app/models.py

class PushHistory(Base):
    __tablename__ = "push_history"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    title = Column(String)
    message = Column(String)
    url = Column(String)
    clicks = Column(Integer, default=0) # Para contar cliques no futuro
    sent_count = Column(Integer, default=0) # Quantas pessoas receberam
    created_at = Column(String) # Data de envio (ISO Format)

