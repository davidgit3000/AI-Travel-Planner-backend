from pydantic import BaseModel
from typing import Any, Dict

class WebhookRequest(BaseModel):
    """Model for the webhook request body"""
    data: Dict[str, Any]  # This will accept any JSON data structure
