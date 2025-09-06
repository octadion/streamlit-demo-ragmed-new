from fastapi import APIRouter, HTTPException, Depends
from typing import List
from app.database import get_db, prisma
from app.models.bot import BotCreate, BotUpdate, BotResponse, BotListResponse
from app.auth import get_global_auth

router = APIRouter()


@router.post("/", response_model=BotResponse)
async def create_bot(bot_data: BotCreate, db=Depends(get_db), auth=Depends(get_global_auth)):
    try:
        bot = await prisma.bot.create(data=bot_data.model_dump())
        return BotResponse.model_validate(bot)
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create bot: {str(e)}")


@router.get("/", response_model=List[BotListResponse])
async def list_bots(db=Depends(get_db), auth=Depends(get_global_auth)):
    try:
        bots = await prisma.bot.find_many(
            order={"createdAt": "desc"}
        )
        
        return [BotListResponse.model_validate(bot) for bot in bots]
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bots: {str(e)}")


@router.get("/{bot_id}", response_model=BotResponse)
async def get_bot(bot_id: str, db=Depends(get_db), auth=Depends(get_global_auth)):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        return BotResponse.model_validate(bot)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bot: {str(e)}")


@router.put("/{bot_id}", response_model=BotResponse)
async def update_bot(bot_id: str, bot_data: BotUpdate, db=Depends(get_db), auth=Depends(get_global_auth)):
    try:
        existing_bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not existing_bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        update_data = {k: v for k, v in bot_data.model_dump().items() if v is not None}
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No valid fields to update")
        
        bot = await prisma.bot.update(
            where={"id": bot_id},
            data=update_data
        )
        
        return BotResponse.model_validate(bot)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update bot: {str(e)}")


@router.delete("/{bot_id}")
async def delete_bot(bot_id: str, db=Depends(get_db), auth=Depends(get_global_auth)):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        await prisma.bot.delete(where={"id": bot_id})
        
        return {"message": f"Bot {bot_id} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete bot: {str(e)}")


@router.get("/{bot_id}/stats")
async def get_bot_stats(bot_id: str, db=Depends(get_db), auth=Depends(get_global_auth)):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        documents_count = await prisma.botdocument.count(where={"botId": bot_id})
        sources_count = await prisma.botsource.count(where={"botId": bot_id})
        chat_history_count = await prisma.chathistory.count(where={"botId": bot_id})
        integrations_count = await prisma.botintegration.count(where={"botId": bot_id})
        
        return {
            "bot_id": bot_id,
            "bot_name": bot.name,
            "documents_count": documents_count,
            "sources_count": sources_count,
            "chat_history_count": chat_history_count,
            "integrations_count": integrations_count,
            "created_at": bot.createdAt
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch bot stats: {str(e)}")