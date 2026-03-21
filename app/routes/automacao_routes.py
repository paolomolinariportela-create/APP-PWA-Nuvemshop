import httpx
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models import AutomacaoConfig, CarrinhoAbandonado, VendaApp, AppConfig
from app.auth import get_current_store

router = APIRouter(prefix="/automacao", tags=["Automacao"])


# =============================================
# SCHEMAS
# =============================================

class AutomacaoPayload(BaseModel):
    passo1_ativo: bool = True
    passo1_horas: float = 1.0
    passo1_titulo: str = "Seus itens estao te esperando!"
    passo1_mensagem: str = "Voce deixou alguns itens no carrinho. Que tal finalizar sua compra?"

    passo2_ativo: bool = True
    passo2_horas: float = 24.0
    passo2_titulo: str = "Seus itens estao acabando!"
    passo2_mensagem: str = "O estoque e limitado! Garanta os seus itens antes que esgotem."

    passo3_ativo: bool = False
    passo3_horas: float = 48.0
    passo3_titulo: str = "Ultimo aviso! Oferta especial para voce."
    passo3_mensagem: str = "Seu carrinho ainda esta salvo. Use o cupom abaixo para ganhar desconto!"
    passo3_cupom: Optional[str] = None


# =============================================
# HELPERS
# =============================================

def get_scheduler(request: Request):
    return request.app.state.scheduler


def get_onesignal_credentials(store_id: str, db: Session):
    config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
    if not config:
        return None, None
    return getattr(config, "onesignal_app_id", None), getattr(config, "onesignal_api_key", None)


def cliente_ja_comprou(store_id: str, visitor_id: str, db: Session) -> bool:
    venda = db.query(VendaApp).filter(
        VendaApp.store_id == store_id,
        VendaApp.visitor_id == visitor_id,
    ).first()
    return venda is not None


def carrinho_ainda_ativo(store_id: str, visitor_id: str, db: Session) -> bool:
    carrinho = db.query(CarrinhoAbandonado).filter(
        CarrinhoAbandonado.store_id == store_id,
        CarrinhoAbandonado.visitor_id == visitor_id,
        CarrinhoAbandonado.status == "ativo",
    ).first()
    return carrinho is not None and (carrinho.cart_count or 0) > 0


async def disparar_push_carrinho(
    app_id: str,
    api_key: str,
    external_id: str,
    titulo: str,
    mensagem: str,
    cupom: Optional[str] = None,
):
    """Dispara push de carrinho abandonado via OneSignal external_id."""
    if cupom:
        mensagem = f"{mensagem} Cupom: {cupom}"

    headers = {
        "Authorization": f"Basic {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "app_id": app_id,
        "headings": {"en": titulo, "pt": titulo},
        "contents": {"en": mensagem, "pt": mensagem},
        "url": "/carrinho",
        "include_aliases": {"external_id": [external_id]},
        "target_channel": "push",
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            "https://onesignal.com/api/v1/notifications",
            headers=headers,
            json=payload,
        )
        return resp.json()


# =============================================
# FUNÇÃO DO JOB — executada pelo APScheduler
# =============================================

def executar_push_carrinho(
    store_id: str,
    visitor_id: str,
    external_id: str,
    passo: int,
    db_url: str,
):
    """
    Função executada pelo APScheduler nos horários configurados.
    Verifica se o cliente ainda tem carrinho ativo e não comprou.
    Se sim, dispara o push. Se não, cancela silenciosamente.
    """
    import asyncio
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    # Cria sessão própria pois o APScheduler roda em thread separada
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    db = SessionLocal()

    try:
        print(f"[SCHEDULER] Passo {passo} para visitor {visitor_id} da loja {store_id}")

        # Verificacao anti-mico
        if cliente_ja_comprou(store_id, visitor_id, db):
            print(f"[SCHEDULER] Cliente {visitor_id} ja comprou — cancelando push passo {passo}")
            _marcar_carrinho_comprado(store_id, visitor_id, db)
            return

        if not carrinho_ainda_ativo(store_id, visitor_id, db):
            print(f"[SCHEDULER] Carrinho {visitor_id} nao esta mais ativo — cancelando")
            return

        # Busca config de automacao da loja
        config_automacao = db.query(AutomacaoConfig).filter(
            AutomacaoConfig.store_id == store_id
        ).first()

        if not config_automacao:
            print(f"[SCHEDULER] Sem config de automacao para loja {store_id}")
            return

        # Seleciona template do passo correto
        if passo == 1 and config_automacao.passo1_ativo:
            titulo = config_automacao.passo1_titulo
            mensagem = config_automacao.passo1_mensagem
            cupom = None
        elif passo == 2 and config_automacao.passo2_ativo:
            titulo = config_automacao.passo2_titulo
            mensagem = config_automacao.passo2_mensagem
            cupom = None
        elif passo == 3 and config_automacao.passo3_ativo:
            titulo = config_automacao.passo3_titulo
            mensagem = config_automacao.passo3_mensagem
            cupom = config_automacao.passo3_cupom
        else:
            print(f"[SCHEDULER] Passo {passo} desativado para loja {store_id}")
            return

        # Busca credenciais OneSignal
        app_config = db.query(AppConfig).filter(AppConfig.store_id == store_id).first()
        if not app_config or not app_config.onesignal_app_id:
            print(f"[SCHEDULER] OneSignal nao configurado para loja {store_id}")
            return

        # Dispara o push
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            disparar_push_carrinho(
                app_id=app_config.onesignal_app_id,
                api_key=app_config.onesignal_api_key,
                external_id=external_id,
                titulo=titulo,
                mensagem=mensagem,
                cupom=cupom,
            )
        )
        loop.close()
        print(f"[SCHEDULER] Push passo {passo} enviado para {external_id}: {result}")

    except Exception as e:
        print(f"[SCHEDULER] Erro no passo {passo} para {visitor_id}: {e}")
    finally:
        db.close()


def _marcar_carrinho_comprado(store_id: str, visitor_id: str, db: Session):
    carrinho = db.query(CarrinhoAbandonado).filter(
        CarrinhoAbandonado.store_id == store_id,
        CarrinhoAbandonado.visitor_id == visitor_id,
    ).first()
    if carrinho:
        carrinho.status = "comprou"
        carrinho.atualizado_em = datetime.now().isoformat()
        db.commit()


# =============================================
# FUNÇÃO CENTRAL: Agendar recuperação de carrinho
# Chamada pelo analytics_routes quando detecta carrinho
# =============================================

def agendar_recuperacao_carrinho(
    store_id: str,
    visitor_id: str,
    external_id: str,
    cart_count: int,
    cart_total: Optional[float],
    scheduler,
    db: Session,
    db_url: str,
):
    """
    Agenda os 3 passos de recuperação de carrinho abandonado.
    Chamada sempre que o loader.js detectar cart_items_count > 0.
    """
    now = datetime.now()

    # Busca ou cria registro do carrinho
    carrinho = db.query(CarrinhoAbandonado).filter(
        CarrinhoAbandonado.store_id == store_id,
        CarrinhoAbandonado.visitor_id == visitor_id,
    ).first()

    if not carrinho:
        carrinho = CarrinhoAbandonado(
            store_id=store_id,
            visitor_id=visitor_id,
            external_id=external_id,
            cart_count=cart_count,
            cart_total=cart_total,
            status="ativo",
            criado_em=now.isoformat(),
            atualizado_em=now.isoformat(),
        )
        db.add(carrinho)
    else:
        # Atualiza carrinho existente
        carrinho.cart_count = cart_count
        carrinho.cart_total = cart_total
        carrinho.status = "ativo"
        carrinho.atualizado_em = now.isoformat()
        if external_id:
            carrinho.external_id = external_id

    db.commit()

    if not external_id:
        print(f"[AUTOMACAO] Visitante {visitor_id} anonimo — nao e possivel agendar push sem email")
        return

    # Busca config de automacao
    config = db.query(AutomacaoConfig).filter(AutomacaoConfig.store_id == store_id).first()
    if not config:
        # Cria config padrao para a loja
        config = AutomacaoConfig(
            store_id=store_id,
            criado_em=now.isoformat(),
            atualizado_em=now.isoformat(),
        )
        db.add(config)
        db.commit()

    job_kwargs = dict(
        store_id=store_id,
        visitor_id=visitor_id,
        external_id=external_id,
        db_url=db_url,
    )

    # Cancela jobs anteriores desse visitor para evitar duplicatas
    for job_id in [carrinho.job1_id, carrinho.job2_id, carrinho.job3_id]:
        if job_id:
            try:
                scheduler.remove_job(job_id)
            except Exception:
                pass

    # Agenda Passo 1
    if config.passo1_ativo:
        run_time_1 = now + timedelta(hours=config.passo1_horas)
        job1 = scheduler.add_job(
            executar_push_carrinho,
            "date",
            run_date=run_time_1,
            kwargs={**job_kwargs, "passo": 1},
            id=f"carrinho_{store_id}_{visitor_id}_p1",
            replace_existing=True,
        )
        carrinho.job1_id = job1.id
        print(f"[AUTOMACAO] Passo 1 agendado para {run_time_1} — visitor {visitor_id}")

    # Agenda Passo 2
    if config.passo2_ativo:
        run_time_2 = now + timedelta(hours=config.passo2_horas)
        job2 = scheduler.add_job(
            executar_push_carrinho,
            "date",
            run_date=run_time_2,
            kwargs={**job_kwargs, "passo": 2},
            id=f"carrinho_{store_id}_{visitor_id}_p2",
            replace_existing=True,
        )
        carrinho.job2_id = job2.id
        print(f"[AUTOMACAO] Passo 2 agendado para {run_time_2} — visitor {visitor_id}")

    # Agenda Passo 3
    if config.passo3_ativo:
        run_time_3 = now + timedelta(hours=config.passo3_horas)
        job3 = scheduler.add_job(
            executar_push_carrinho,
            "date",
            run_date=run_time_3,
            kwargs={**job_kwargs, "passo": 3},
            id=f"carrinho_{store_id}_{visitor_id}_p3",
            replace_existing=True,
        )
        carrinho.job3_id = job3.id
        print(f"[AUTOMACAO] Passo 3 agendado para {run_time_3} — visitor {visitor_id}")

    db.commit()


def cancelar_recuperacao_carrinho(
    store_id: str,
    visitor_id: str,
    scheduler,
    db: Session,
):
    """Cancela todos os jobs quando cliente compra ou esvazia carrinho."""
    carrinho = db.query(CarrinhoAbandonado).filter(
        CarrinhoAbandonado.store_id == store_id,
        CarrinhoAbandonado.visitor_id == visitor_id,
    ).first()

    if not carrinho:
        return

    for job_id in [carrinho.job1_id, carrinho.job2_id, carrinho.job3_id]:
        if job_id:
            try:
                scheduler.remove_job(job_id)
                print(f"[AUTOMACAO] Job {job_id} cancelado")
            except Exception:
                pass

    carrinho.status = "expirado"
    carrinho.job1_id = None
    carrinho.job2_id = None
    carrinho.job3_id = None
    carrinho.atualizado_em = datetime.now().isoformat()
    db.commit()


# =============================================
# ROTAS — Configuração de Automações pelo lojista
# =============================================

@router.get("/config")
def get_automacao_config(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    config = db.query(AutomacaoConfig).filter(AutomacaoConfig.store_id == store_id).first()
    if not config:
        # Retorna defaults sem criar no banco
        return AutomacaoPayload().dict()

    return {
        "passo1_ativo": config.passo1_ativo,
        "passo1_horas": config.passo1_horas,
        "passo1_titulo": config.passo1_titulo,
        "passo1_mensagem": config.passo1_mensagem,
        "passo2_ativo": config.passo2_ativo,
        "passo2_horas": config.passo2_horas,
        "passo2_titulo": config.passo2_titulo,
        "passo2_mensagem": config.passo2_mensagem,
        "passo3_ativo": config.passo3_ativo,
        "passo3_horas": config.passo3_horas,
        "passo3_titulo": config.passo3_titulo,
        "passo3_mensagem": config.passo3_mensagem,
        "passo3_cupom": config.passo3_cupom,
    }


@router.post("/config")
def save_automacao_config(
    payload: AutomacaoPayload,
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    now = datetime.now().isoformat()
    config = db.query(AutomacaoConfig).filter(AutomacaoConfig.store_id == store_id).first()

    if not config:
        config = AutomacaoConfig(store_id=store_id, criado_em=now)
        db.add(config)

    config.passo1_ativo = payload.passo1_ativo
    config.passo1_horas = payload.passo1_horas
    config.passo1_titulo = payload.passo1_titulo
    config.passo1_mensagem = payload.passo1_mensagem
    config.passo2_ativo = payload.passo2_ativo
    config.passo2_horas = payload.passo2_horas
    config.passo2_titulo = payload.passo2_titulo
    config.passo2_mensagem = payload.passo2_mensagem
    config.passo3_ativo = payload.passo3_ativo
    config.passo3_horas = payload.passo3_horas
    config.passo3_titulo = payload.passo3_titulo
    config.passo3_mensagem = payload.passo3_mensagem
    config.passo3_cupom = payload.passo3_cupom
    config.atualizado_em = now

    db.commit()
    return {"status": "ok"}


@router.get("/carrinhos")
def listar_carrinhos(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    """Lista carrinhos abandonados ativos da loja — para o dashboard."""
    carrinhos = db.query(CarrinhoAbandonado).filter(
        CarrinhoAbandonado.store_id == store_id,
        CarrinhoAbandonado.status == "ativo",
    ).order_by(CarrinhoAbandonado.id.desc()).limit(50).all()

    return [
        {
            "visitor_id": c.visitor_id,
            "external_id": c.external_id,
            "cart_count": c.cart_count,
            "cart_total": c.cart_total,
            "criado_em": c.criado_em,
            "atualizado_em": c.atualizado_em,
        }
        for c in carrinhos
    ]
