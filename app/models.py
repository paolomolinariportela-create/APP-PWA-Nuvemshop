from sqlalchemy import Column, Integer, String, Boolean, Text, Float
from .database import Base


class Loja(Base):
    __tablename__ = "lojas"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)
    access_token = Column(String)
    email = Column(String, nullable=True)
    url = Column(String, nullable=True)
    logo_url = Column(String, nullable=True)


class AppConfig(Base):
    __tablename__ = "app_config"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)

    app_name = Column(String, default="Minha Loja")
    theme_color = Column(String, default="#000000")
    logo_url = Column(String, nullable=True)
    whatsapp_number = Column(String, nullable=True)

    # FAB
    fab_position = Column(String, default="right")
    fab_icon = Column(String, default="📲")
    fab_animation = Column(Boolean, default=True)
    fab_delay = Column(Integer, default=0)
    fab_enabled = Column(Boolean, default=False)
    fab_text = Column(String, default="Baixar App")
    fab_color = Column(String, default="#2563EB")
    fab_size = Column(String, default="medium")
    fab_background_image_url = Column(String, nullable=True)

    # TOP/BOTTOM BAR
    topbar_enabled = Column(Boolean, default=False)
    topbar_text = Column(String, default="Baixe nosso app")
    topbar_button_text = Column(String, default="Baixar")
    topbar_icon = Column(String, default="📲")
    topbar_position = Column(String, default="bottom")
    topbar_color = Column(String, default="#111827")
    topbar_text_color = Column(String, default="#FFFFFF")
    topbar_size = Column(String, default="medium")
    topbar_button_bg_color = Column(String, default="#FBBF24", nullable=True)
    topbar_button_text_color = Column(String, default="#111827", nullable=True)
    topbar_background_image_url = Column(String, nullable=True)

    # POPUP
    popup_enabled = Column(Boolean, default=False)
    popup_image_url = Column(String, nullable=True)

    # BOTTOM BAR DO PWA
    bottom_bar_bg = Column(String, default="#FFFFFF")
    bottom_bar_icon_color = Column(String, default="#6B7280")

    # ONESIGNAL
    onesignal_app_id = Column(String(100), nullable=True)
    onesignal_api_key = Column(String(200), nullable=True)


class VendaApp(Base):
    __tablename__ = "vendas_app"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    valor = Column(String)
    data = Column(String)
    visitor_id = Column(String, index=True, nullable=True)


class VisitaApp(Base):
    __tablename__ = "visitas_app"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    data = Column(String)
    pagina = Column(String)
    is_pwa = Column(Boolean, default=False)
    visitor_id = Column(String, index=True, nullable=True)


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    visitor_id = Column(String, index=True)
    endpoint = Column(Text, nullable=False)
    p256dh = Column(String, nullable=False)
    auth = Column(String, nullable=False)
    created_at = Column(String)


class PushHistory(Base):
    __tablename__ = "push_history"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    title = Column(String)
    message = Column(String)
    url = Column(String)
    clicks = Column(Integer, default=0)
    sent_count = Column(Integer, default=0)
    created_at = Column(String)


class VariantEvent(Base):
    __tablename__ = "variant_events"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    visitor_id = Column(String, index=True)
    product_id = Column(String, index=True)
    variant_id = Column(String, index=True)
    variant_name = Column(String, nullable=True)
    price = Column(String, nullable=True)
    stock = Column(Integer, nullable=True)
    data = Column(String)


# ✅ NOVO: Configuração de Automações por loja
# Cada loja tem 3 passos de recuperação de carrinho abandonado
class AutomacaoConfig(Base):
    __tablename__ = "automacao_config"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, unique=True, index=True)

    # Passo 1 — padrão: 1 hora
    passo1_ativo = Column(Boolean, default=True)
    passo1_horas = Column(Float, default=1.0)
    passo1_titulo = Column(String, default="Seus itens estao te esperando!")
    passo1_mensagem = Column(String, default="Voce deixou alguns itens no carrinho. Que tal finalizar sua compra?")

    # Passo 2 — padrão: 24 horas
    passo2_ativo = Column(Boolean, default=True)
    passo2_horas = Column(Float, default=24.0)
    passo2_titulo = Column(String, default="Seus itens estao acabando!")
    passo2_mensagem = Column(String, default="O estoque e limitado! Garanta os seus itens antes que esgotem.")

    # Passo 3 — padrão: 48 horas com cupom
    passo3_ativo = Column(Boolean, default=False)
    passo3_horas = Column(Float, default=48.0)
    passo3_titulo = Column(String, default="Ultimo aviso! Oferta especial para voce.")
    passo3_mensagem = Column(String, default="Seu carrinho ainda esta salvo. Use o cupom abaixo para ganhar desconto!")
    passo3_cupom = Column(String, nullable=True)

    criado_em = Column(String, nullable=True)
    atualizado_em = Column(String, nullable=True)


# ✅ NOVO: Rastreio de carrinhos abandonados ativos
# Guarda o estado atual do carrinho de cada visitor para o agendador verificar
class CarrinhoAbandonado(Base):
    __tablename__ = "carrinhos_abandonados"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(String, index=True)
    visitor_id = Column(String, index=True)
    external_id = Column(String, nullable=True)  # e-mail do cliente (OneSignal login)
    cart_count = Column(Integer, default=0)       # qtd de itens no carrinho
    cart_total = Column(Float, nullable=True)     # valor total do carrinho
    status = Column(String, default="ativo")      # ativo | comprou | expirado
    job1_id = Column(String, nullable=True)       # ID do job APScheduler passo 1
    job2_id = Column(String, nullable=True)       # ID do job APScheduler passo 2
    job3_id = Column(String, nullable=True)       # ID do job APScheduler passo 3
    criado_em = Column(String, nullable=True)
    atualizado_em = Column(String, nullable=True)
