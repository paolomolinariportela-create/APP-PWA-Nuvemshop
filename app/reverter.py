import json
import requests
from sqlalchemy.orm import Session
from .models import HistoryLog, Produto, Loja
from .executor import _handle_product_content, _handle_variant_math

def process_reversal(log_id: int, db: Session):
    # 1. Busca o que foi feito no passado
    log = db.query(HistoryLog).filter(HistoryLog.id == log_id).first()
    if not log:
        return {"error": "Histórico não encontrado."}

    # 2. Recupera o comando original
    original_plan = json.loads(log.full_command)
    store_id = log.store_id
    loja = db.query(Loja).filter(Loja.store_id == store_id).first()
    
    headers = {
        "Authentication": f"bearer {loja.access_token}",
        "Content-Type": "application/json"
    }

    # 3. CRIA O PLANO INVERSO (O Segredo)
    change = original_plan['changes'][0]
    reverse_change = change.copy()

    # Inverte Lógica de Título
    if change['field'] == 'title':
        if change['action'] == 'APPEND':
            reverse_change['action'] = 'REPLACE'
            reverse_change['replace_this'] = change['value']
            reverse_change['value'] = "" # Remove o que foi adicionado
        elif change['action'] == 'REPLACE':
            # Se trocou 'A' por 'B', a reversão troca 'B' por 'A'
            reverse_change['action'] = 'REPLACE'
            reverse_change['replace_this'] = change['value']
            reverse_change['value'] = change.get('replace_this', "")

    # Inverte Lógica de Preço (Matemática)
    elif change['field'] in ['price', 'promotional_price']:
        val = float(change['value'])
        if change['action'] == 'INCREASE_PERCENT':
            # Para desfazer um aumento de 5%, não basta tirar 5% (matemática)
            # Simplificamos forçando o valor antigo se tivéssemos salvo, 
            # ou aplicando a redução inversa
            reverse_change['action'] = 'DECREASE_PERCENT'
            reverse_change['value'] = str(val)

    # 4. EXECUTA A VOLTA
    from .executor import execute_nuvemshop_update
    reverse_plan = original_plan.copy()
    reverse_plan['changes'] = [reverse_change]
    
    # Chamamos o executor que já criamos e está funcionando!
    execute_nuvemshop_update(store_id, reverse_plan, db)
    
    return {"status": "reverted", "affected": log.affected_count}
