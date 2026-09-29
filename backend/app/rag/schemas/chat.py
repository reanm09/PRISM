from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    title: Optional[str] = "New Investigation Chat"


class ChatSessionResponse(BaseModel):
    id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class ChatMessageCreate(BaseModel):
    session_id: str
    role: str
    content: str
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict)


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    user_id: str
    role: str
    content: str
    retrieval_metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
