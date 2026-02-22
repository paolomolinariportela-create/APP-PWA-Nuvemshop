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

    # Logo padrão da loja (vinda da Nuvemshop)
    logo_url = Column(String, nullable=True)


# Tabela de Configuração (Cores, Nome do App e Widgets)
class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)

    app_name = Column(String, default="Minha Loja")
    theme_color = Column(String, default="#000000")
    logo_url = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)

    # FAB (botão flutuante "Baixar App")
    fab_position = Column(String, default="right")   # 'left' ou 'right'
    fab_icon = Column(String, default="📲")          # emoji ou URL
    fab_animation = Column(Boolean, default=True)    # Ativar pulso?
    fab_delay = Column(Integer, default=0)           # Segundos para aparecer
    fab_enabled = Column(Boolean, default=False)     # Botão Flutuante 'Baixar App'
    fab_text = Column(String, default="Baixar App")
    fab_color = Column(String, default="#2563EB")    # cor do botão
    fab_size = Column(String, default="medium")      # 'small' | 'medium' | 'large'

    # TOP/BOTTOM BAR (banner / barra inferior do widget)
    topbar_enabled = Column(Boolean, default=False)          # habilita banner/barra
    topbar_text = Column(String, default="Baixe nosso app")  # texto principal
    topbar_button_text = Column(String, default="Baixar")    # texto do botão
    topbar_icon = Column(String, default="📲")               # ícone/emoji
    topbar_position = Column(String, default="bottom")       # 'top' ou 'bottom'
    topbar_color = Column(String, default="#111827")         # cor de fundo
    topbar_text_color = Column(String, default="#FFFFFF")    # cor do texto
    topbar_size = Column(String, default="medium")           # tamanho

    # NOVOS CAMPOS – cores independentes do botão da barra
    topbar_button_bg_color = Column(String, default="#FBBF24", nullable=True)
    topbar_button_text_color = Column(String, default="#111827", nullable=True)

    # BOTTOM BAR DO APP (barra de navegação inferior do PWA)
    bottom_bar_bg = Column(String, default="#FFFFFF")          # Fundo da barra
    bottom_bar_icon_color = Column(String, default="#6B7280")  # Cor ícones/labels


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
    endpoint = Column(Text, nullable=False)  # URL única do navegador
    p256dh = Column(String, nullable=False)  # Chave Pública 1
    auth = Column(String, nullable=False)    # Chave de Auth 2

    created_at = Column(String)


# Histórico de Push
class PushHistory(Base):
    __tablename__ = "push_history"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    title = Column(String)
    message = Column(String)
    url = Column(String)
    clicks = Column(Integer, default=0)       # Para contar cliques no futuro
    sent_count = Column(Integer, default=0)   # Quantas pessoas receberam
    created_at = Column(String)               # Data de envio (ISO Format)


# Eventos de mudança de variante
class VariantEvent(Base):
    __tablename__ = "variant_events"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    visitor_id = Column(String, index=True)
    product_id = Column(String, index=True)
    variant_id = Column(String, index=True)
    variant_name = Column(String, nullable=True)
    price = Column(String, nullable=True)   # mantendo string como em VendaApp
    stock = Column(Integer, nullable=True)
    data = Column(String)  # datetime em ISO
