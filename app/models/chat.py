from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class Platform(str, Enum):
    API = "api"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    WEB = "web"


class ChatMessage(BaseModel):
    role: ChatRole
    content: str
    
    class Config:
        use_enum_values = True


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message")
    user_id: str = Field(..., description="User identifier")
    session_id: Optional[str] = Field(None, description="Chat session ID")
    platform: Platform = Field(default=Platform.API, description="Platform source")
    
    use_history: Optional[bool] = Field(None, description="Include chat history")
    max_history: Optional[int] = Field(None, ge=0, le=50, description="Max history messages")
    
    metadata: Optional[Dict[str, Any]] = Field(default={}, description="Additional metadata")


class ChatResponse(BaseModel):
    message: str
    sources: List[Dict[str, Any]] = Field(default=[], description="Retrieved sources")
    session_id: str
    trace_id: Optional[str] = None
    
    metadata: Dict[str, Any] = Field(default={})
    processing_time: Optional[float] = None
    tokens_used: Optional[int] = None


class ChatHistoryItem(BaseModel):
    id: str
    user_id: str
    session_id: Optional[str]
    platform: str
    human_message: str
    ai_message: str
    sources: Optional[List[Dict[str, Any]]]
    metadata: Dict[str, Any]
    trace_id: Optional[str]
    createdAt: datetime
    
    class Config:
        from_attributes = True


class ChatSession(BaseModel):
    session_id: str
    user_id: str
    platform: str
    bot_id: str
    message_count: int
    last_activity: datetime
    metadata: Dict[str, Any] = Field(default={})


class StreamingChatRequest(ChatRequest):
    stream: bool = Field(default=True, description="Enable streaming response")


class StreamingChunk(BaseModel):
    content: str
    is_final: bool = False
    sources: Optional[List[Dict[str, Any]]] = None
    metadata: Optional[Dict[str, Any]] = None