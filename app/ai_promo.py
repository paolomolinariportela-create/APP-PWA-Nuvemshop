from typing import Dict, Any
from sqlalchemy.orm import Session
from .models import Produto
from .utils import get_filtered_products

# ==============================================================================
# 🛠️ DEFINIÇÃO DAS FERRAMENTAS (Interface com a IA)
# ==============================================================================
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "propose_bulk_action",
            "description": "Gerencia campanhas de promoção, descontos e preços De/Por.",
            "parameters": {
                "type": "object",
                "properties": {
                    "plan_summary": {
                        "type": "string",
                        "description": "Resumo curto e persuasivo do que será feito para o usuário aprovar."
                    },
                    "scope": {
                        "type": "string",
                        "enum": ["PRODUCT", "VARIANT"],
                        "description": "Use 'PRODUCT' para aplicar em tudo ou 'VARIANT' para filtrar por cor/tamanho."
                    },
                    "find_product": {
                        "type": "object",
                        "properties": {
                            "title_contains": {"type": "string", "description": "Nome do produto ou Marca (ex: Nike, Camiseta)"},
                            "category_contains": {"type": "string", "description": "Categoria exata da loja"},
                            "collection_id": {"type": "string", "description": "ID numérico de uma coleção específica"}
                        }
                    },
                    "action": {
                        "type": "string",
                        "enum": ["APPLY_DISCOUNT", "CLEAR_PROMOTION"],
                        "description": "APPLY_DISCOUNT: Cria oferta (De/Por). CLEAR_PROMOTION: Remove oferta (Volta ao preço original)."
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["PERCENT", "FIXED_PRICE", "FIXED_DISCOUNT"],
                        "description": "PERCENT: -20%. FIXED_PRICE: Tudo por R$ 99. FIXED_DISCOUNT: -R$ 10 reais."
                    },
                    "value": {
                        "type": "string",
                        "description": "O valor numérico do desconto ou preço final (ex: '20', '99.90')."
                    },
                    "rounding": {
                        "type": "string",
                        "enum": ["NONE", "0.90", "0.99"],
                        "description": "Estratégia de arredondamento psicológico (Charm Pricing)."
                    }
                },
                "required": ["plan_summary", "scope", "find_product", "action"]
            }
        }
    }
]

# ==============================================================================
# 🧠 CÉREBRO DA IA (Regras de Negócio e Marketing)
# ==============================================================================
SYSTEM_PROMPT = """
Você é o Gerente de Marketing Sênior e Estrategista de Preços da Loja.
Sua missão é criar campanhas de vendas agressivas, inteligentes e seguras.

SUAS CAPACIDADES E REGRAS DE OURO:

1. 🏷️ TIPOS DE DESCONTO ("APPLY_DISCOUNT"):
   - Percentual: "20% off em toda a loja" -> mode="PERCENT", value="20".
   - Preço Fixo (Outlet): "Tudo por R$ 99" -> mode="FIXED_PRICE", value="99".
   - Abatimento (Cupom): "R$ 10 reais a menos" -> mode="FIXED_DISCOUNT", value="10".
   - *Nota:* Ao aplicar desconto, o sistema cria automaticamente o "Preço De" (riscado).

2. 🧠 ARREDONDAMENTO INTELIGENTE (Charm Pricing):
   - Se o usuário não especificar, SUGIRA arredondar para .90 ou .99 para aumentar a conversão.
   - Use o campo 'rounding' para isso. Ex: De 84.32 para 84.90.

3. 🛡️ SEGURANÇA E FILTROS:
   - Se o usuário disser "na Nike", use find_product.title_contains="Nike".
   - Se disser "na coleção Verão", tente identificar o ID ou use filtro por categoria.
   - Se o desconto for muito agressivo (>50%), adicione um aviso no 'plan_summary'.

4. 🚨 BOTÃO DE PÂNICO ("CLEAR_PROMOTION"):
   - Use quando o usuário pedir "Acabar com a promoção", "Voltar ao normal" ou "Limpar preços".
   - Isso remove o preço promocional e mantém apenas o preço original.

5. RESUMO (plan_summary):
   - Escreva um resumo profissional. Ex: "Aplicando 20% OFF em 50 produtos da categoria Tênis, com arredondamento para .90."
"""

# ==============================================================================
# ⚙️ LÓGICA DE EXECUÇÃO (O Motor)
# ==============================================================================
def run_logic(db: Session, store_id: str, args: Dict[str, Any]):
    try:
        # 1. Recupera o plano da IA
        plan = args
        
        # 2. Busca os produtos no banco para criar a "amostra"
        products = get_filtered_products(db, store_id, plan)
        affected_count = 0
        samples = []
        
        # 3. Gera estatísticas rápidas
        for p in products:
            # Se for por variante, a contagem seria mais complexa, aqui simplificamos para produtos
            affected_count += 1
            if len(samples) < 5: samples.append(f"• {p.name}")

        # 4. Tradução Visual para o Chat (Feedback para o Lojista)
        act = plan.get('action')
        val = plan.get('value', '0')
        mode = plan.get('mode', '')
        rounding = plan.get('rounding', 'NONE')
        
        txt_acao = ""
        if act == 'CLEAR_PROMOTION':
            txt_acao = "🗑️ **Fim da Oferta:** Removendo preços promocionais. Voltando ao valor original."
        elif act == 'APPLY_DISCOUNT':
            if mode == 'PERCENT': txt_acao = f"🔥 **Oferta:** Desconto de **{val}%**."
            elif mode == 'FIXED_PRICE': txt_acao = f"🔥 **Outlet:** Tudo por **R$ {val}**."
            elif mode == 'FIXED_DISCOUNT': txt_acao = f"🔥 **Bonus:** Abater **R$ {val}** do preço."
            
            if rounding != 'NONE':
                txt_acao += f" (Arredondando para final **{rounding}**)"

        resumo_chat = (
            f"📢 **Planejamento de Campanha:**\n\n"
            f"{txt_acao}\n"
            f"🎯 **Alcance:** {affected_count} produtos selecionados\n\n"
            f"📝 **Amostra dos afetados:**\n" + "\n".join(samples)
        )

        # 5. ADAPTAÇÃO CRÍTICA PARA O EXECUTOR
        # O executor_math.py espera uma lista 'changes' com a instrução exata.
        # Aqui convertemos o plano de marketing em instrução matemática.
        plan['changes'] = [{
            'field': 'promotional_price',
            'action': act,
            'value': val,
            'mode': mode,
            'rounding': rounding
        }]

        # 6. Retorno Final
        return {
            "total_affected": affected_count,
            "samples": samples,
            "plan_summary": resumo_chat, # Texto bonito para o chat
            "plan_json": plan            # Comando técnico para o botão "Aprovar"
        }

    except Exception as e:
        return {
            "plan_summary": f"⚠️ Erro ao calcular proposta: {str(e)}",
            "error": str(e)
        }
