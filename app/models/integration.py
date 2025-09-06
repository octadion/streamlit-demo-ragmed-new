from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class IntegrationType(str, Enum):
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"


class IntegrationStatus(str, Enum):
    INACTIVE = "inactive"
    ACTIVE = "active"
    ERROR = "error"
    PENDING = "pending"


class WhatsAppConfig(BaseModel):
    access_token: str = Field(..., description="WhatsApp Business API access token")
    verify_token: str = Field(..., description="Webhook verify token")
    phone_number_id: str = Field(..., description="WhatsApp phone number ID")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    business_account_id: Optional[str] = Field(None, description="Business account ID")


class WhatsAppMessage(BaseModel):
    from_number: str = Field(..., description="Sender phone number")
    to_number: str = Field(..., description="Recipient phone number") 
    message_type: str = Field(default="text", description="Message type")
    text: Optional[str] = Field(None, description="Text message content")
    media_url: Optional[str] = Field(None, description="Media URL")
    media_type: Optional[str] = Field(None, description="Media type")
    timestamp: Optional[str] = Field(None, description="Message timestamp")
    message_id: Optional[str] = Field(None, description="WhatsApp message ID")


class WhatsAppWebhook(BaseModel):
    object: str
    entry: list


class TelegramConfig(BaseModel):
    bot_token: str = Field(..., description="Telegram bot token")
    webhook_url: Optional[str] = Field(None, description="Webhook URL")
    webhook_secret: Optional[str] = Field(None, description="Webhook secret")
    allowed_updates: Optional[list] = Field(None, description="Allowed update types")


class TelegramUser(BaseModel):
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class TelegramMessage(BaseModel):
    message_id: int
    from_user: Optional[TelegramUser] = Field(None, alias="from")
    date: int
    text: Optional[str] = None
    chat: Dict[str, Any]
    reply_to_message: Optional[Dict[str, Any]] = None


class TelegramUpdate(BaseModel):
    update_id: int
    message: Optional[TelegramMessage] = None
    edited_message: Optional[TelegramMessage] = None
    callback_query: Optional[Dict[str, Any]] = None


class IntegrationCreate(BaseModel):
    platform: IntegrationType
    config: Dict[str, Any] = Field(..., description="Platform-specific configuration")


class IntegrationUpdate(BaseModel):
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class IntegrationResponse(BaseModel):
    id: str
    botId: str
    platform: str
    is_active: bool
    config: Dict[str, Any]
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True

class WebhookEvent(BaseModel):
    platform: IntegrationType
    bot_id: str
    user_id: str
    message: str
    timestamp: datetime
    raw_data: Dict[str, Any]
    message_id: Optional[str] = None


class IntegrationStats(BaseModel):
    platform: str
    total_messages: int
    unique_users: int
    messages_today: int
    last_activity: Optional[datetime]
    status: IntegrationStatus
    error_count: int = 0
    last_error: Optional[str] = None


class WhatsAppResponse(BaseModel):
    messaging_product: str = "whatsapp"
    to: str
    type: str = "text"
    text: Dict[str, Any]


class TelegramResponse(BaseModel):
    method: str = "sendMessage"
    chat_id: int
    text: str
    parse_mode: Optional[str] = None
    reply_markup: Optional[Dict[str, Any]] = None