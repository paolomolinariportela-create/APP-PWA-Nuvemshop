import os
import requests
import json
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, Body
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import text

# Importações internas
from .database import get_db
from .models import Loja, Produto, HistoryLog
from .services import sync_full_store_data
from .schemas import ChatMessage, ApplyChangesPayload
from .executor import execute_nuvemshop_update
from .security import verify_token_access, create_access_token # <--- Importamos o Criador de Token também

# === IMPORTAÇÕES DOS AGENTES (CÉREBROS) ===
import app.ai_consultant as ai_consultant
import app.ai_operator as ai_operator
import app.ai_price as ai_price
import app.ai_content as ai_content 
import app.ai_inventory as ai_inventory
import app.ai_promo as ai_promo
import app.ai_tags as ai_tags
import app.ai_description as ai_description 
import app.ai_brand as ai_brand
import app.ai_status as ai_status
import app.ai_code as ai_code 
import app.ai_logistics as ai_logistics
import app.ai_demographics as ai_demographics
import app.ai_related as ai_related
import app.ai_seo as ai_seo 
import app.ai_category as ai_category
import app.ai_variants as ai_variants

# Configurações
router = APIRouter()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://front-end-new-skin-lab-editor-production.up.railway.app")
NUVEMSHOP_TOKEN_URL = "https://www.tiendanube.com/apps/authorize/token"

# ==============================================================================
# 🔒 MAPA DE ROTEAMENTO (MANTIDO INTACTO)
# ==============================================================================
AGENT_MAP = {
    # TÍTULO (Conteúdo)
    "title": ai_content, "titulo": ai_content, "content": ai_content, 
    "name": ai_content,

    # SEO 
    "seo": ai_seo, 
    "otimizacao": ai_seo, 
    "keywords": ai_seo,
    "metatags": ai_seo,
    "busca": ai_seo,

    # DESCRIÇÃO
    "description": ai_description, 
    "descrição": ai_description,
    "descricao": ai_description,

    # PREÇO
    "price": ai_price, "preço": ai_price, "valor": ai_price, "cost": ai_price,

    # PROMOÇÃO
    "compare at": ai_promo, "compare_at": ai_promo, "promo": ai_promo, 
    "promocao": ai_promo, "oferta": ai_promo,

    # ESTOQUE
    "inventory": ai_inventory, "estoque": ai_inventory, 
    "stock": ai_inventory, "quantity": ai_inventory,

    # TAGS
    "tag": ai_tags, "tags": ai_tags, "etiqueta": ai_tags, "etiquetas": ai_tags,

    # MARCAS
    "brand": ai_brand,
    "marca": ai_brand,
    "marcas": ai_brand,      
    "vendor": ai_brand,      
    "fabricante": ai_brand,

    # STATUS (Visibilidade)
    "status": ai_status,
    "visibilidade": ai_status,
    "ativo": ai_status,
    "publicado": ai_status,

    # === CÓDIGO
    "code": ai_code,
    "codigo": ai_code,
    "sku": ai_code,
    "códigos": ai_code,    
    "codigos": ai_code,
    "codes": ai_code,

    # === LOGÍSTICA
    "logistics": ai_logistics,      
    "logistica": ai_logistics,      
    "logística": ai_logistics,      
    "peso": ai_logistics,
    "frete": ai_logistics,

    # === DADOS TÉCNICOS 
    "demographics": ai_demographics,
    "tecnico": ai_demographics,
    "google_shopping": ai_demographics, 
    "mpn": ai_demographics,
    "genero": ai_demographics,
    "sexo": ai_demographics,
    "faixa etaria": ai_demographics,
    "idade": ai_demographics,
    "adulto": ai_demographics,
    "google": ai_demographics,  
    
    # === VARIAÇÃO ===
    "variacao": ai_variants,
    "grade": ai_variants,
    "tamanho": ai_variants,
    "cor": ai_variants,
    "variants": ai_variants,

    # === RELACIONADOS (CROSS-SELL) ===
    "relacionados": ai_related,
    "related": ai_related,
    "cross sell": ai_related,
    "compre junto": ai_related,
    "sugestoes": ai_related,

    # CATEGORIAS
    "categoria": ai_category,
    "categorias": ai_category,
    "category": ai_category,
    "colecao": ai_category,
      

    # GERAL
    "dashboard": ai_consultant, "geral": ai_consultant
}

# ==============================================================================
# 🔒 ROTA DE CHAT (BLINDADA COM TOKEN)
# ==============================================================================
@router.post("/chat")
async def chat_endpoint(
    dados: ChatMessage, 
    # 🔒 AQUI ESTÁ A SEGURANÇA: O ID vem do Token, não do corpo da requisição
    store_id_secure: str = Depends(verify_token_access),
    db: Session = Depends(get_db)
):
    if not OPENAI_API_KEY: return {"response": "Erro: API Key não configurada."}
    
    # Usa o ID seguro extraído do token
    target_store_id = store_id_secure
    context_key = dados.context.lower().strip() if dados.context else "dashboard"
    
    print(f"🔒 [SECURE CHAT] Contexto: '{context_key}' | Loja: {target_store_id}")

    # 1. SELEÇÃO DIRETA
    ai_module = AGENT_MAP.get(context_key, ai_operator)
    
    # 2. CARREGA AS FERRAMENTAS
    try:
        tools = ai_module.TOOLS
        sys_prompt = ai_module.SYSTEM_PROMPT
    except AttributeError:
        # Fallback se o módulo estiver quebrado
        ai_module = ai_operator
        tools = ai_module.TOOLS
        sys_prompt = ai_module.SYSTEM_PROMPT
    
    # ==========================================================================
    # 🛑 DEFINIÇÃO RÍGIDA DA FUNÇÃO ESPERADA
    # ==========================================================================
    if ai_module == ai_consultant:
        tool_name_expected = "consult_database"
    elif ai_module == ai_tags:
        tool_name_expected = "manage_tags"
    elif ai_module == ai_content:
        tool_name_expected = "manage_content"
    elif ai_module == ai_description:            
        tool_name_expected = "manage_description" 
    elif ai_module == ai_brand:         
        tool_name_expected = "manage_brand"     
    elif ai_module == ai_logistics:
        tool_name_expected = "manage_logistics" 
    elif ai_module == ai_demographics:
        tool_name_expected = "manage_demographics"  
    elif ai_module == ai_related:
        tool_name_expected = "manage_related" 
    elif ai_module == ai_category:
        tool_name_expected = "manage_categories"
    elif ai_module == ai_variants:
        tool_name_expected = "manage_variants"
    elif ai_module == ai_status:
        tool_name_expected = "manage_status"  
    elif ai_module == ai_seo:
        tool_name_expected = "manage_seo"
    
    # === TRAVA PARA CÓDIGO ===
    elif ai_module == ai_code:
        tool_name_expected = "manage_code"      
    # =========================

    elif ai_module == ai_promo:
        tool_name_expected = "propose_bulk_action"
    else:
        # Padrão genérico
        tool_name_expected = "propose_bulk_action"

    print(f"✅ Agente: {ai_module.__name__} | Função Obrigatória: '{tool_name_expected}'")

    # 3. CHAMADA OPENAI
    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": dados.message}],
        "temperature": 0,
        "tools": tools,
        "tool_choice": "auto" 
    }

    try:
        res = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json=payload)
        data = res.json()
        
        if "error" in data: return {"response": f"Erro OpenAI: {data['error']['message']}"}
        
        ai_msg = data['choices'][0]['message']

        if ai_msg.get('tool_calls'):
            tool_call = ai_msg['tool_calls'][0]
            fn_name = tool_call['function']['name']
            args = json.loads(tool_call['function']['arguments'])

            # Aceitamos se for o esperado
            if fn_name == tool_name_expected or fn_name == "propose_bulk_action":
                result = ai_module.run_logic(db, target_store_id, args)
                
                if ai_module == ai_consultant:
                    payload['messages'].append(ai_msg)
                    payload['messages'].append({"role": "tool", "tool_call_id": tool_call['id'], "content": str(result)})
                    res2 = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json=payload)
                    return {"response": res2.json()['choices'][0]['message']['content']}
                else:
                    return {
                        "response": result.get('plan_summary', "Plano gerado."),
                        "command": result.get('command', args) 
                    }
        
        return {"response": ai_msg['content']}
        
    except Exception as e: 
        return {"response": f"Erro técnico: {str(e)}"}

# =========================
# ROTAS OPERACIONAIS (BLINDADAS)
# =========================

@router.post("/apply-changes")
async def apply_changes_endpoint(
    payload: ApplyChangesPayload, 
    background_tasks: BackgroundTasks, 
    # 🔒 SEGURANÇA
    store_id_secure: str = Depends(verify_token_access), 
    db: Session = Depends(get_db)
):
    # Usa o ID seguro para executar
    background_tasks.add_task(execute_nuvemshop_update, store_id_secure, payload.command, db)
    return {"status": "queued", "message": "Comando enviado para fila segura!"}

@router.get("/products")
def list_products(
    limit: int = 100, 
    # 🔒 SEGURANÇA
    store_id_secure: str = Depends(verify_token_access), 
    db: Session = Depends(get_db)
):
    # Filtra obrigatoriamente pelo ID do token
    return db.query(Produto).filter(Produto.store_id == store_id_secure).limit(limit).all()

@router.get("/admin/status")
def check_sync_status(
    # 🔒 SEGURANÇA
    store_id_secure: str = Depends(verify_token_access), 
    db: Session = Depends(get_db)
):
    loja = db.query(Loja).filter(Loja.store_id == store_id_secure).first()
    if not loja: raise HTTPException(404, detail="Loja não encontrada")
    
    total = db.query(Produto).filter(Produto.store_id == store_id_secure).count()
    return {"loja_nome": loja.nome_loja, "total_produtos_banco": total}

@router.post("/sync")
async def sync_products(
    force: bool = False, 
    background_tasks: BackgroundTasks = None, 
    # 🔒 SEGURANÇA
    store_id_secure: str = Depends(verify_token_access), 
    db: Session = Depends(get_db)
):
    # Sync apenas da loja do token
    if background_tasks:
        background_tasks.add_task(sync_full_store_data, store_id_secure, db, force)
    else:
        # Fallback se não vier background_tasks (raro)
        await sync_full_store_data(store_id_secure, db, force)
        
    return {"status": "ok", "message": "Sincronização iniciada com segurança."}

@router.get("/history")
def get_history(
    # 🔒 SEGURANÇA
    store_id_secure: str = Depends(verify_token_access), 
    db: Session = Depends(get_db)
):
    # Histórico blindado
    return db.query(HistoryLog).filter(HistoryLog.store_id == store_id_secure).order_by(text("created_at desc")).limit(20).all()

@router.post("/history/revert/{log_id}")
async def revert_history(
    log_id: int, 
    background_tasks: BackgroundTasks, 
    # 🔒 SEGURANÇA
    store_id_secure: str = Depends(verify_token_access), 
    db: Session = Depends(get_db)
):
    # Garante que o log pertence à loja que está pedindo
    log = db.query(HistoryLog).filter(HistoryLog.id == log_id, HistoryLog.store_id == store_id_secure).first()
    
    if not log: 
        raise HTTPException(404, detail="Log não encontrado ou acesso negado.")
        
    if log.status == "REVERTED": 
        return {"status": "error", "message": "Já revertido"}
        
    try:
        original = json.loads(log.full_command)
        # Lógica de reversão (simplificada para brevidade, mantida igual ao original)
        # ... (Mantendo sua lógica de reversão intacta)
        if 'changes' in original and original['changes']:
            change = original['changes'][0]
            revert_plan = original.copy()
            inverse_map = {"INCREASE_FIXED": "DECREASE_FIXED", "DECREASE_FIXED": "INCREASE_FIXED", "INCREASE_PERCENT": "DECREASE_PERCENT", "DECREASE_PERCENT": "INCREASE_PERCENT"}
            
            if change['field'] == 'title':
                revert_plan['changes'][0]['action'] = 'REPLACE'
                revert_plan['changes'][0]['replace_this'] = change['value']
                revert_plan['changes'][0]['value'] = change.get('replace_this', "")
            elif change['action'] in inverse_map:
                revert_plan['changes'][0]['action'] = inverse_map[change['action']]
            else: 
                # Se não souber reverter, tenta pelo menos rodar o oposto genérico ou falha
                pass 

            background_tasks.add_task(execute_nuvemshop_update, log.store_id, revert_plan, db)
            log.status = "REVERTED"
            db.commit()
            return {"status": "ok"}
        return {"status": "error", "message": "Formato de log não suportado para reversão"}

    except Exception as e: 
        return {"status": "error", "message": str(e)}

# =========================
# NOTA: A ROTA DE CALLBACK FOI MOVIDA PARA app/auth.py
# (Isso evita conflito de rotas e centraliza a autenticação)
# =========================
