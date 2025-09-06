from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from typing import List, Optional
import json
import asyncio

from app.auth import get_global_auth
from app.database import prisma
from app.models.chat import (
    ChatRequest, ChatResponse, ChatHistoryItem, 
    StreamingChatRequest, StreamingChunk, Platform
)
from app.services.chat_service import ChatService
from app.services.llm_service import LLMProviderFactory

router = APIRouter()

chat_service = ChatService()

@router.post("/", response_model=ChatResponse)
async def chat_with_bot(
    chat_request: ChatRequest,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        response = await chat_service.chat_with_bot(bot_id, chat_request)
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/stream")
async def stream_chat_with_bot(
    chat_request: StreamingChatRequest,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        async def generate_stream():
            try:
                if bot.use_advanced_rag:
                    advanced_result = await chat_service.advanced_rag_service.process_query(
                        bot=bot,
                        query=chat_request.message,
                        user_id=chat_request.user_id
                    )

                    final_chunk = StreamingChunk(
                        content=advanced_result["message"],
                        is_final=True,
                        sources=advanced_result["sources"],
                        metadata={**chat_request.metadata, **advanced_result["metadata"]}
                    )
                    yield f"data: {final_chunk.model_dump_json()}\n\n"

                    session_id = chat_request.session_id or "stream_session"
                    if bot.enable_chat_history:
                        await chat_service._save_chat_history(
                            bot_id,
                            chat_request.user_id,
                            session_id,
                            chat_request.platform,
                            chat_request.message,
                            advanced_result["message"],
                            advanced_result["sources"],
                            {**chat_request.metadata, **advanced_result["metadata"]},
                            "advanced_rag_stream"
                        )
                    return

                history = []
                if chat_request.use_history and bot.enable_chat_history:
                    history = await chat_service._get_chat_history(
                        bot_id,
                        chat_request.user_id,
                        chat_request.session_id,
                        chat_request.platform,
                        chat_request.max_history
                    )

                sources = await chat_service._retrieve_documents(bot, chat_request.message)
                
                from app.services.llm_service import get_llm_from_bot_config
                llm_provider = get_llm_from_bot_config(bot)

                messages = []
                if bot.system_prompt:
                    messages.append({"role": "system", "content": bot.system_prompt})
                
                if history:
                    for hist_msg in history[-10:]:
                        messages.append(hist_msg)
                
                context = chat_service._format_context(sources)
                rag_content = bot.rag_prompt.format(context=context, question=chat_request.message)
                messages.append({"role": "user", "content": rag_content})

                accumulated_content = ""
                async for chunk in llm_provider.stream_generate(messages):
                    accumulated_content += chunk
                    
                    stream_chunk = StreamingChunk(
                        content=chunk,
                        is_final=False
                    )
                    
                    yield f"data: {stream_chunk.model_dump_json()}\n\n"

                final_chunk = StreamingChunk(
                    content="",
                    is_final=True,
                    sources=sources,
                    metadata=chat_request.metadata
                )
                yield f"data: {final_chunk.model_dump_json()}\n\n"

                session_id = chat_request.session_id or "stream_session"
                await chat_service._save_chat_history(
                    bot_id,
                    chat_request.user_id,
                    session_id,
                    chat_request.platform,
                    chat_request.message,
                    accumulated_content,
                    sources,
                    chat_request.metadata,
                    "stream_trace"
                )
                
            except Exception as e:
                error_chunk = StreamingChunk(
                    content=f"Error: {str(e)}",
                    is_final=True,
                    metadata={"error": str(e)}
                )
                yield f"data: {error_chunk.model_dump_json()}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming chat failed: {str(e)}")


@router.get("/history", response_model=List[ChatHistoryItem])
async def get_chat_history(
    bot_id: str = Query(..., description="Bot ID"),
    user_id: str = Query(None, description="Filter by user ID"),
    session_id: str = Query(None, description="Filter by session ID"),
    limit: int = Query(default=50, le=200, description="Maximum number of messages"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        where_clause = {"botId": bot_id}
        if user_id:
            where_clause["user_id"] = user_id
        if session_id:
            where_clause["session_id"] = session_id
        
        history = await prisma.chathistory.find_many(
            where=where_clause,
            order={"createdAt": "desc"},
            take=limit
        )
        
        return [ChatHistoryItem.model_validate(item) for item in history]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/sessions")
async def get_chat_sessions(
    bot_id: str = Query(..., description="Bot ID"),
    user_id: str = Query(None, description="Filter by user ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        sessions = await chat_service.get_chat_sessions(bot_id, user_id)
        
        return {
            "bot_id": bot_id,
            "sessions": sessions,
            "total_sessions": len(sessions)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get sessions: {str(e)}")


@router.get("/sessions/{session_id}/history", response_model=List[ChatHistoryItem])
async def get_session_history(
    session_id: str,
    bot_id: str = Query(..., description="Bot ID"),
    limit: int = Query(default=50, le=200, description="Maximum number of messages"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        history = await chat_service.get_session_history(bot_id, session_id, limit)
        
        return history
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session history: {str(e)}")


@router.delete("/history")
async def clear_chat_history(
    bot_id: str = Query(..., description="Bot ID"),
    user_id: str = Query(None, description="Clear history for specific user"),
    session_id: str = Query(None, description="Clear history for specific session"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        success = await chat_service.clear_chat_history(bot_id, user_id, session_id)
        
        if success:
            return {"message": "Chat history cleared successfully"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear chat history")
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear history: {str(e)}")


@router.get("/stats")
async def get_chat_stats(
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        total_messages = await prisma.chathistory.count(where={"botId": bot_id})
        
        unique_users = await prisma.query_raw(
            "SELECT COUNT(DISTINCT user_id) as count FROM chat_history WHERE \"botId\" = $1",
            bot_id
        )
        
        unique_sessions = await prisma.query_raw(
            "SELECT COUNT(DISTINCT session_id) as count FROM chat_history WHERE \"botId\" = $1 AND session_id IS NOT NULL",
            bot_id
        )
        
        platform_stats = await prisma.query_raw(
            "SELECT platform, COUNT(*) as count FROM chat_history WHERE \"botId\" = $1 GROUP BY platform",
            bot_id
        )
        
        recent_activity = await prisma.query_raw(
            "SELECT COUNT(*) as count FROM chat_history WHERE \"botId\" = $1 AND \"createdAt\" > NOW() - INTERVAL '24 hours'",
            bot_id
        )
        
        return {
            "bot_id": bot_id,
            "total_messages": total_messages,
            "unique_users": unique_users[0]["count"] if unique_users else 0,
            "unique_sessions": unique_sessions[0]["count"] if unique_sessions else 0,
            "platform_distribution": {stat["platform"]: stat["count"] for stat in platform_stats},
            "recent_activity_24h": recent_activity[0]["count"] if recent_activity else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get chat stats: {str(e)}")


@router.get("/providers")
async def get_available_llm_providers():
    providers = LLMProviderFactory.get_available_providers()
    
    import os
    current_config = {
        "llm_provider": os.getenv("LLM_PROVIDER", "mistral"),
        "llm_model": os.getenv("LLM_MODEL", "auto"),
        "embedding_provider": os.getenv("EMBEDDING_PROVIDER", "mistral"),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "auto")
    }
    
    return {
        "llm_providers": providers,
        "current_config": current_config
    }