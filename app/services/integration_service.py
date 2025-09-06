import httpx
import json
from typing import Dict, Any, Optional
from datetime import datetime

from app.database import prisma
from app.models.integration import (
    IntegrationType, IntegrationStatus, WebhookEvent,
    WhatsAppMessage, TelegramMessage, TelegramUpdate
)
from app.models.chat import ChatRequest, Platform
from app.services.chat_service import ChatService


class IntegrationService:
    def __init__(self):
        self.chat_service = ChatService()
    
    async def process_webhook_event(self, platform: IntegrationType, bot_id: str, raw_data: Dict[str, Any]) -> Optional[str]:
        try:
            if platform == IntegrationType.WHATSAPP:
                return await self._process_whatsapp_webhook(bot_id, raw_data)
            elif platform == IntegrationType.TELEGRAM:
                return await self._process_telegram_webhook(bot_id, raw_data)
            else:
                raise ValueError(f"Unsupported platform: {platform}")
                
        except Exception as e:
            print(f"Webhook processing error: {e}")
            return None
    
    async def _process_whatsapp_webhook(self, bot_id: str, raw_data: Dict[str, Any]) -> Optional[str]:
        try:
            if "entry" not in raw_data:
                return None
            
            for entry in raw_data["entry"]:
                if "changes" not in entry:
                    continue
                    
                for change in entry["changes"]:
                    if change.get("field") != "messages":
                        continue
                    
                    value = change.get("value", {})
                    messages = value.get("messages", [])
                    
                    for message in messages:
                        from_number = message.get("from")
                        message_type = message.get("type", "text")
                        timestamp = message.get("timestamp")

                        if message_type == "text":
                            text_content = message.get("text", {}).get("body", "")
                            
                            if text_content and from_number:
                                chat_request = ChatRequest(
                                    message=text_content,
                                    user_id=from_number,
                                    platform=Platform.WHATSAPP,
                                    metadata={
                                        "whatsapp_message_id": message.get("id"),
                                        "timestamp": timestamp,
                                        "raw_data": message
                                    }
                                )

                                response = await self.chat_service.chat_with_bot(bot_id, chat_request)

                                await self._send_whatsapp_message(bot_id, from_number, response.message)
                                
                                return response.message
            
            return None
            
        except Exception as e:
            print(f"WhatsApp webhook processing error: {e}")
            return None
    
    async def _process_telegram_webhook(self, bot_id: str, raw_data: Dict[str, Any]) -> Optional[str]:
        try:
            update = TelegramUpdate.model_validate(raw_data)
            
            if not update.message:
                return None
            
            message = update.message
            
            if not message.text:
                return None
            
            user_id = str(message.from_user.id) if message.from_user else str(message.chat["id"])
            chat_id = message.chat["id"]

            chat_request = ChatRequest(
                message=message.text,
                user_id=user_id,
                platform=Platform.TELEGRAM,
                metadata={
                    "telegram_message_id": message.message_id,
                    "chat_id": chat_id,
                    "update_id": update.update_id,
                    "from_user": message.from_user.model_dump() if message.from_user else None,
                    "raw_data": raw_data
                }
            )

            response = await self.chat_service.chat_with_bot(bot_id, chat_request)

            await self._send_telegram_message(bot_id, chat_id, response.message)
            
            return response.message
            
        except Exception as e:
            print(f"Telegram webhook processing error: {e}")
            return None
    
    async def _send_whatsapp_message(self, bot_id: str, to_number: str, message: str) -> bool:
        try:
            integration = await prisma.botintegration.find_first(
                where={
                    "botId": bot_id,
                    "platform": IntegrationType.WHATSAPP.value,
                    "is_active": True
                }
            )
            
            if not integration:
                print("WhatsApp integration not found or inactive")
                return False
            
            config = integration.config
            access_token = config.get("access_token")
            phone_number_id = config.get("phone_number_id")
            
            if not access_token or not phone_number_id:
                print("WhatsApp configuration missing")
                return False

            url = f"https://graph.facebook.com/v18.0/{phone_number_id}/messages"
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "messaging_product": "whatsapp",
                "to": to_number,
                "type": "text",
                "text": {
                    "body": message
                }
            }

            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    print(f"WhatsApp message sent successfully to {to_number}")
                    return True
                else:
                    print(f"WhatsApp API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            print(f"WhatsApp send error: {e}")
            return False
    
    async def _send_telegram_message(self, bot_id: str, chat_id: int, message: str) -> bool:
        try:
            integration = await prisma.botintegration.find_first(
                where={
                    "botId": bot_id,
                    "platform": IntegrationType.TELEGRAM.value,
                    "is_active": True
                }
            )
            
            if not integration:
                print("Telegram integration not found or inactive")
                return False
            
            config = integration.config
            bot_token = config.get("bot_token")
            
            if not bot_token:
                print("Telegram bot token missing")
                return False

            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            
            payload = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown" 
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                
                if response.status_code == 200:
                    print(f"Telegram message sent successfully to chat {chat_id}")
                    return True
                else:
                    print(f"Telegram API error: {response.status_code} - {response.text}")
                    return False
                    
        except Exception as e:
            print(f"Telegram send error: {e}")
            return False
    
    async def setup_whatsapp_webhook(self, bot_id: str, webhook_url: str) -> bool:
        try:
            integration = await prisma.botintegration.find_first(
                where={
                    "botId": bot_id,
                    "platform": IntegrationType.WHATSAPP.value
                }
            )
            
            if integration:
                config = integration.config
                config["webhook_url"] = webhook_url
                
                await prisma.botintegration.update(
                    where={"id": integration.id},
                    data={"config": config}
                )
                
                return True
            
            return False
            
        except Exception as e:
            print(f"WhatsApp webhook setup error: {e}")
            return False
    
    async def setup_telegram_webhook(self, bot_id: str, webhook_url: str) -> bool:
        try:
            integration = await prisma.botintegration.find_first(
                where={
                    "botId": bot_id,
                    "platform": IntegrationType.TELEGRAM.value
                }
            )
            
            if not integration:
                return False
            
            config = integration.config
            bot_token = config.get("bot_token")
            
            if not bot_token:
                return False

            url = f"https://api.telegram.org/bot{bot_token}/setWebhook"
            
            payload = {
                "url": webhook_url,
                "allowed_updates": ["message", "edited_message"]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload)
                
                if response.status_code == 200:
                    config["webhook_url"] = webhook_url
                    
                    await prisma.botintegration.update(
                        where={"id": integration.id},
                        data={"config": config}
                    )
                    
                    print(f"Telegram webhook set successfully: {webhook_url}")
                    return True
                else:
                    print(f"Telegram webhook setup error: {response.text}")
                    return False
                    
        except Exception as e:
            print(f"Telegram webhook setup error: {e}")
            return False
    
    async def verify_whatsapp_webhook(self, verify_token: str, challenge: str) -> Optional[str]:
        if verify_token and challenge:
            return challenge
        return None
    
    async def get_integration_stats(self, bot_id: str, platform: IntegrationType) -> Dict[str, Any]:
        try:
            total_messages = await prisma.chathistory.count(
                where={
                    "botId": bot_id,
                    "platform": platform.value
                }
            )
            
            unique_users = await prisma.query_raw(
                "SELECT COUNT(DISTINCT user_id) as count FROM chat_history WHERE \"botId\" = $1 AND platform = $2",
                bot_id, platform.value
            )
            
            messages_today = await prisma.query_raw(
                "SELECT COUNT(*) as count FROM chat_history WHERE \"botId\" = $1 AND platform = $2 AND \"createdAt\" > CURRENT_DATE",
                bot_id, platform.value
            )
            
            last_activity = await prisma.chathistory.find_first(
                where={
                    "botId": bot_id,
                    "platform": platform.value
                },
                order={"createdAt": "desc"},
                select={"createdAt": True}
            )
            
            return {
                "platform": platform.value,
                "total_messages": total_messages,
                "unique_users": unique_users[0]["count"] if unique_users else 0,
                "messages_today": messages_today[0]["count"] if messages_today else 0,
                "last_activity": last_activity.createdAt if last_activity else None,
                "status": IntegrationStatus.ACTIVE
            }
            
        except Exception as e:
            print(f"Integration stats error: {e}")
            return {
                "platform": platform.value,
                "total_messages": 0,
                "unique_users": 0,
                "messages_today": 0,
                "last_activity": None,
                "status": IntegrationStatus.ERROR,
                "error": str(e)
            }