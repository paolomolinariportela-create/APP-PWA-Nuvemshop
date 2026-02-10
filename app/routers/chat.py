import os
import json
import requests
from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from app.database import get_db
from app.security import verify_token_access
from app.schemas import ChatMessage, ApplyChangesPayload
from app.executor import execute_nuvemshop_update

# Importações dos Agentes
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

router = APIRouter()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") 

AGENT_MAP = {
    "title": ai_content, "titulo": ai_content, "content": ai_content, "name": ai_content,
    "seo": ai_seo, "otimizacao": ai_seo, "keywords": ai_seo, "metatags": ai_seo,
    "description": ai_description, "descricao": ai_description, "descrição": ai_description,
    "price": ai_price, "preço": ai_price, "valor": ai_price, "cost": ai_price,
    "promo": ai_promo, "promocao": ai_promo, "oferta": ai_promo,
    "inventory": ai_inventory, "estoque": ai_inventory, "stock": ai_inventory,
    "tag": ai_tags, "tags": ai_tags,
    "brand": ai_brand, "marca": ai_brand, "fabricante": ai_brand,
    "status": ai_status, "visibilidade": ai_status, "ativo": ai_status,
    "code": ai_code, "codigo": ai_code, "sku": ai_code,
    "logistics": ai_logistics, "logistica": ai_logistics, "peso": ai_logistics,
    "demographics": ai_demographics, "tecnico": ai_demographics, "genero": ai_demographics,
    "variacao": ai_variants, "grade": ai_variants, "tamanho": ai_variants,
    "related": ai_related, "relacionados": ai_related, "cross sell": ai_related,
    "categoria": ai_category, "categorias": ai_category,
    "dashboard": ai_consultant, "geral": ai_consultant
}

@router.post("/chat")
async def chat_endpoint(dados: ChatMessage, store_id_secure: str = Depends(verify_token_access), db: Session = Depends(get_db)):
    if not OPENAI_API_KEY: return {"response": "Erro: API Key não configurada."}
    
    context_key = dados.context.lower().strip() if dados.context else "dashboard"
    ai_module = AGENT_MAP.get(context_key, ai_operator)
    
    try:
        tools = ai_module.TOOLS
        sys_prompt = ai_module.SYSTEM_PROMPT
    except AttributeError:
        ai_module = ai_operator
        tools = ai_module.TOOLS
        sys_prompt = ai_module.SYSTEM_PROMPT
    
    # Define tool_name_expected (simplificado para brevidade)
    tool_name_expected = "propose_bulk_action"
    if ai_module == ai_consultant: tool_name_expected = "consult_database"
    # ... (Adicione os outros ifs se precisar de validação estrita, ou deixe o genérico)

    payload = {
        "model": "gpt-4o-mini",
        "messages": [{"role": "system", "content": sys_prompt}, {"role": "user", "content": dados.message}],
        "temperature": 0, "tools": tools, "tool_choice": "auto" 
    }

    try:
        res = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json=payload)
        data = res.json()
        if "error" in data: return {"response": f"Erro OpenAI: {data['error']['message']}"}
        
        ai_msg = data['choices'][0]['message']
        if ai_msg.get('tool_calls'):
            tool_call = ai_msg['tool_calls'][0]
            args = json.loads(tool_call['function']['arguments'])
            
            result = ai_module.run_logic(db, store_id_secure, args)
            
            if ai_module == ai_consultant:
                payload['messages'].append(ai_msg)
                payload['messages'].append({"role": "tool", "tool_call_id": tool_call['id'], "content": str(result)})
                res2 = requests.post("https://api.openai.com/v1/chat/completions", headers={"Authorization": f"Bearer {OPENAI_API_KEY}"}, json=payload)
                return {"response": res2.json()['choices'][0]['message']['content']}
            else:
                return {"response": result.get('plan_summary', "Plano gerado."), "command": result.get('command', args)}
        
        return {"response": ai_msg['content']}
    except Exception as e: return {"response": f"Erro técnico: {str(e)}"}

@router.post("/apply-changes")
async def apply_changes_endpoint(payload: ApplyChangesPayload, background_tasks: BackgroundTasks, store_id_secure: str = Depends(verify_token_access), db: Session = Depends(get_db)):
    background_tasks.add_task(execute_nuvemshop_update, store_id_secure, payload.command, db)
    return {"status": "queued", "message": "Comando enviado!"}
