import os
from fastapi import APIRouter, Response, Request

router = APIRouter()

@router.get("/loader.js")
def get_loader_script(request: Request):
    """
    Script Mágico: Este arquivo será injetado na Nuvemshop.
    Ele descobre o ID da loja e ativa o PWA automaticamente.
    """
    # Descobre a URL do seu backend automaticamente
    base_url = str(request.base_url).rstrip("/")
    
    js_content = f"""
    (function() {{
        console.log("🚀 PWA Builder Iniciado...");

        // 1. Tenta descobrir o ID da Loja (Nuvemshop coloca isso no window.LS)
        var storeId = null;
        if (window.LS && window.LS.store && window.LS.store.id) {{
            storeId = window.LS.store.id;
        }}

        if (!storeId) {{
            console.warn("⚠️ PWA: Não foi possível identificar a loja.");
            return;
        }}

        console.log("✅ Loja Identificada: " + storeId);

        // 2. Injeta o Manifesto no HTML
        var link = document.createElement('link');
        link.rel = 'manifest';
        link.href = '{base_url}/pwa/manifest/' + storeId + '.json'; // Aponta para a rota que criamos
        document.head.appendChild(link);

        // 3. Registra o Service Worker
        if ('serviceWorker' in navigator) {{
            navigator.serviceWorker.register('{base_url}/pwa/service-worker.js')
            .then(function(reg) {{
                console.log('✅ Service Worker registrado com sucesso:', reg.scope);
            }})
            .catch(function(err) {{
                console.error('❌ Falha ao registrar Service Worker:', err);
            }});
        }}

        // 4. (Opcional) Botão Flutuante de Instalação
        // Podemos adicionar lógica aqui depois para mostrar um botão "Baixar App"
    }})();
    """
    return Response(content=js_content, media_type="application/javascript")
