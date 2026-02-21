@router.get("/dashboard")
def get_dashboard_stats(
    store_id: str = Depends(get_current_store),
    db: Session = Depends(get_db),
):
    # janelas de tempo
    agora = datetime.now()
    sete_dias_atras = agora - timedelta(days=7)
    quatorze_dias_atras = agora - timedelta(days=14)

    # VENDAS / RECEITA
    vendas = db.query(VendaApp).filter(VendaApp.store_id == store_id).all()
    total_receita = sum(float(v.valor) for v in vendas)
    qtd_vendas = len(vendas)

    # VISITANTES ÚNICOS (todos, app + site)
    visitantes_unicos = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(VisitaApp.store_id == store_id)
        .scalar()
        or 0
    )

    # NOVO: VISITAS PWA vs WEB
    visitas_pwa = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
        )
        .scalar()
        or 0
    )
    visitas_web = max(0, visitantes_unicos - visitas_pwa)

    # NOVO: VENDAS PWA vs SITE
    vendas_pwa = (
        db.query(func.count(VendaApp.id))
        .filter(
            VendaApp.store_id == store_id,
            VendaApp.visitor_id.in_(
                db.query(VisitaApp.visitor_id).filter(
                    VisitaApp.store_id == store_id,
                    VisitaApp.is_pwa == True,
                )
            ),
        )
        .scalar()
        or 0
    )
    vendas_site = max(0, qtd_vendas - vendas_pwa)

    # CHECKOUT / CARRINHO
    qtd_checkout = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            (
                VisitaApp.pagina.contains("checkout")
                | VisitaApp.pagina.contains("carrinho")
            ),
        )
        .scalar()
        or 0
    )

    abandonos = max(0, qtd_checkout - qtd_vendas)
    ticket_medio = total_receita / max(1, qtd_vendas) if qtd_vendas > 0 else 0

    # CLIENTES RECORRENTES (2+ compras)
    subquery = (
        db.query(VendaApp.visitor_id)
        .filter(VendaApp.store_id == store_id)
        .group_by(VendaApp.visitor_id)
        .having(func.count(VendaApp.id) > 1)
        .subquery()
    )
    recorrentes = db.query(func.count(subquery.c.visitor_id)).scalar() or 0

    # PAGEVIEWS E TOP PÁGINAS
    visitas_qs = db.query(VisitaApp).filter(VisitaApp.store_id == store_id)
    pageviews = visitas_qs.count()

    top_paginas = [
        p[0]
        for p in db.query(
            VisitaApp.pagina,
            func.count(VisitaApp.pagina).label("total"),
        )
        .filter(VisitaApp.store_id == store_id)
        .group_by(VisitaApp.pagina)
        .order_by(desc("total"))
        .limit(5)
        .all()
    ]

    # CRESCIMENTO DE INSTALAÇÕES (PWA) NOS ÚLTIMOS 7 DIAS
    installs_7d = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.data >= sete_dias_atras.isoformat(),
        )
        .scalar()
        or 0
    )

    installs_7d_antes = (
        db.query(func.count(distinct(VisitaApp.visitor_id)))
        .filter(
            VisitaApp.store_id == store_id,
            VisitaApp.is_pwa == True,
            VisitaApp.data >= quatorze_dias_atras.isoformat(),
            VisitaApp.data < sete_dias_atras.isoformat(),
        )
        .scalar()
        or 0
    )

    if installs_7d_antes > 0:
        crescimento_instalacoes_7d = round(
            (installs_7d - installs_7d_antes) / installs_7d_antes * 100,
            1,
        )
    else:
        crescimento_instalacoes_7d = 0.0

    # TEMPO MÉDIO NO APP (PWA) – SESSÃO MÁX 5 MIN ENTRE PÁGINAS
    from datetime import datetime as _dt

    visitas_pwa_list = (
        visitas_qs.filter(
            VisitaApp.is_pwa == True,
            VisitaApp.visitor_id.isnot(None),
        )
        .order_by(VisitaApp.visitor_id, VisitaApp.data)
        .all()
    )

    total_segundos = 0
    total_sessoes = 0

    ultimo_visitante = None
    ultima_data = None

    LIMITE_SESSAO = 5 * 60  # 5 minutos

    for v in visitas_pwa_list:
        try:
            dt = _dt.fromisoformat(v.data)
        except Exception:
            continue

        if v.visitor_id != ultimo_visitante:
            ultimo_visitante = v.visitor_id
            ultima_data = dt
            total_sessoes += 1
        else:
            diff = (dt - ultima_data).total_seconds()
            if 0 < diff <= LIMITE_SESSAO:
                total_segundos += diff
            ultima_data = dt

    if total_sessoes > 0 and total_segundos > 0:
        media_segundos = total_segundos / total_sessoes
        media_minutos = media_segundos / 60
        tempo_medio_str = f"{media_minutos:.1f} min".replace(".", ",")
    else:
        tempo_medio_str = "--"

    return {
        "receita": total_receita,
        "vendas": qtd_vendas,
        # aqui você pode decidir: manter instalacoes = visitantes_unicos ou = visitas_pwa
        "instalacoes": visitantes_unicos,
        "crescimento_instalacoes_7d": crescimento_instalacoes_7d,
        "carrinhos_abandonados": {
            "valor": abandonos * ticket_medio,
            "qtd": abandonos,
        },
        "visualizacoes": {
            "pageviews": pageviews,
            "tempo_medio": tempo_medio_str,
            "top_paginas": top_paginas,
        },
        "funil": {
            "visitas": visitantes_unicos,
            "carrinho": qtd_checkout,
            "checkout": qtd_vendas,
        },
        "recorrencia": {
            "clientes_2x": recorrentes,
            "taxa_recompra": round(
                (recorrentes / max(1, qtd_vendas) * 100),
                1,
            ),
        },
        "ticket_medio": {"app": round(ticket_medio, 2), "site": 0.0},
        "taxa_conversao": {
            "app": round(
                (vendas_pwa / max(1, visitas_pwa) * 100),
                1,
            )
            if visitas_pwa > 0
            else 0.0,
            "site": round(
                (vendas_site / max(1, visitas_web) * 100),
                1,
            )
            if visitas_web > 0
            else 0.0,
        },
        "economia_ads": visitantes_unicos * 0.50,
        # opcional: se no futuro quiser consumir no front
        "visitas": {
            "app": visitas_pwa,
            "site": visitas_web,
            "total": visitantes_unicos,
        },
    }
