from pydantic import BaseModel
from typing import Optional, Dict, Any

class ChatMessage(BaseModel):
    message: str
    store_id: str 
    context: Optional[str] = "dashboard"

class ApplyChangesPayload(BaseModel):
    store_id: str
    command: Dict[str, Any]
