from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import PlainTextResponse
from typing import List, Dict, Any
from prisma import Json
from app.auth import get_global_auth
from app.database import prisma
from app.models.integration import (
    IntegrationCreate, IntegrationUpdate, IntegrationResponse,
    IntegrationType, IntegrationStatus, WhatsAppWebhook, TelegramUpdate
)
from app.services.integration_service import IntegrationService

router = APIRouter()

integration_service = IntegrationService()


@router.post("/", response_model=IntegrationResponse)
async def create_integration(
    integration_data: IntegrationCreate,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        existing = await prisma.botintegration.find_first(
            where={
                "botId": bot_id,
                "platform": integration_data.platform.value
            }
        )
        
        if existing:
            raise HTTPException(
                status_code=409, 
                detail=f"{integration_data.platform.value} integration already exists"
            )

        integration = await prisma.botintegration.create(
            data={
                "botId": bot_id,
                "platform": integration_data.platform.value,
                "config": Json(integration_data.config),
                "is_active": False
            }
        )
        
        return IntegrationResponse.model_validate(integration)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create integration: {str(e)}")


@router.get("/", response_model=List[IntegrationResponse])
async def list_integrations(
    bot_id: str = Query(..., description="Bot ID"),
    platform: IntegrationType = Query(None, description="Filter by platform"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        where_clause = {"botId": bot_id}
        if platform:
            where_clause["platform"] = platform.value
        
        integrations = await prisma.botintegration.find_many(
            where=where_clause,
            order={"createdAt": "desc"}
        )
        
        return [IntegrationResponse.model_validate(integration) for integration in integrations]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch integrations: {str(e)}")


@router.get("/{integration_id}", response_model=IntegrationResponse)
async def get_integration(
    integration_id: str,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        integration = await prisma.botintegration.find_first(
            where={
                "id": integration_id,
                "botId": bot_id
            }
        )
        
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        return IntegrationResponse.model_validate(integration)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch integration: {str(e)}")


@router.put("/{integration_id}", response_model=IntegrationResponse)
async def update_integration(
    integration_id: str,
    integration_data: IntegrationUpdate,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        existing = await prisma.botintegration.find_first(
            where={
                "id": integration_id,
                "botId": bot_id
            }
        )
        
        if not existing:
            raise HTTPException(status_code=404, detail="Integration not found")

        update_data = {}
        if integration_data.config is not None:
            update_data["config"] = Json(integration_data.config)
        if integration_data.is_active is not None:
            update_data["is_active"] = integration_data.is_active
        
        integration = await prisma.botintegration.update(
            where={"id": integration_id},
            data=update_data
        )
        
        return IntegrationResponse.model_validate(integration)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update integration: {str(e)}")


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: str,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        integration = await prisma.botintegration.find_first(
            where={
                "id": integration_id,
                "botId": bot_id
            }
        )
        
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")
        
        await prisma.botintegration.delete(where={"id": integration_id})
        
        return {"message": f"Integration {integration_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete integration: {str(e)}")


@router.post("/webhook/whatsapp/{bot_id}")
async def whatsapp_webhook(bot_id: str, request: Request):
    try:
        body = await request.json()

        response = await integration_service.process_webhook_event(
            IntegrationType.WHATSAPP,
            bot_id,
            body
        )
        
        return {"status": "ok", "processed": response is not None}
        
    except Exception as e:
        print(f"WhatsApp webhook error: {e}")
        return {"status": "error", "message": str(e)}


@router.get("/webhook/whatsapp/{bot_id}")
async def whatsapp_webhook_verify(
    bot_id: str,
    hub_mode: str = Query(alias="hub.mode"),
    hub_challenge: str = Query(alias="hub.challenge"),
    hub_verify_token: str = Query(alias="hub.verify_token")
):
    try:
        if hub_mode == "subscribe":
            challenge = await integration_service.verify_whatsapp_webhook(
                hub_verify_token,
                hub_challenge
            )
            
            if challenge:
                return PlainTextResponse(challenge)
        
        raise HTTPException(status_code=403, detail="Verification failed")
        
    except Exception as e:
        print(f"WhatsApp webhook verification error: {e}")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook/telegram/{bot_id}")
async def telegram_webhook(bot_id: str, update: TelegramUpdate):
    try:
        response = await integration_service.process_webhook_event(
            IntegrationType.TELEGRAM,
            bot_id,
            update.model_dump()
        )
        
        return {"status": "ok", "processed": response is not None}
        
    except Exception as e:
        print(f"Telegram webhook error: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/{integration_id}/webhook/setup")
async def setup_webhook(
    integration_id: str,
    webhook_url: str = Query(..., description="Webhook URL"),
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        integration = await prisma.botintegration.find_first(
            where={
                "id": integration_id,
                "botId": bot_id
            }
        )
        
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        success = False
        platform = integration.platform
        
        if platform == IntegrationType.WHATSAPP.value:
            success = await integration_service.setup_whatsapp_webhook(bot_id, webhook_url)
        elif platform == IntegrationType.TELEGRAM.value:
            success = await integration_service.setup_telegram_webhook(bot_id, webhook_url)
        
        if success:
            return {"message": f"Webhook setup successful for {platform}"}
        else:
            raise HTTPException(status_code=500, detail="Webhook setup failed")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook setup failed: {str(e)}")


@router.get("/{integration_id}/stats")
async def get_integration_stats(
    integration_id: str,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        integration = await prisma.botintegration.find_first(
            where={
                "id": integration_id,
                "botId": bot_id
            }
        )
        
        if not integration:
            raise HTTPException(status_code=404, detail="Integration not found")

        platform = IntegrationType(integration.platform)
        stats = await integration_service.get_integration_stats(bot_id, platform)
        
        return {
            "integration_id": integration_id,
            "bot_id": bot_id,
            "is_active": integration.is_active,
            **stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/stats/overview")
async def get_integrations_overview(
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        integrations = await prisma.botintegration.find_many(
            where={"botId": bot_id}
        )
        
        overview = {
            "bot_id": bot_id,
            "total_integrations": len(integrations),
            "active_integrations": sum(1 for i in integrations if i.is_active),
            "platforms": {}
        }
        
        for integration in integrations:
            platform = IntegrationType(integration.platform)
            stats = await integration_service.get_integration_stats(bot_id, platform)
            
            overview["platforms"][integration.platform] = {
                "integration_id": integration.id,
                "is_active": integration.is_active,
                "created_at": integration.createdAt,
                **stats
            }
        
        return overview
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get overview: {str(e)}")


@router.get("/platforms/available")
async def get_available_platforms():
    return {
        "platforms": [
            {
                "name": "whatsapp",
                "display_name": "WhatsApp Business",
                "description": "WhatsApp Business API integration",
                "required_config": [
                    "access_token",
                    "verify_token", 
                    "phone_number_id"
                ]
            },
            {
                "name": "telegram",
                "display_name": "Telegram Bot",
                "description": "Telegram Bot API integration",
                "required_config": [
                    "bot_token"
                ]
            }
        ]
    }