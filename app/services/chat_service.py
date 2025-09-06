import time
import uuid
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.database import prisma
from app.models.chat import ChatRequest, ChatResponse, ChatHistoryItem, Platform
from app.services.llm_service import get_llm_from_bot_config
from app.services.document_service import DocumentService
from app.services.embedding_service import get_embedding_provider
from app.services.advanced_rag_service import AdvancedRagService
from prisma import Json

class ChatService:
    def __init__(self):
        self.document_service = DocumentService()
        self.advanced_rag_service = AdvancedRagService(self.document_service)  # NEW
    
    async def chat_with_bot(self, bot_id: str, chat_request: ChatRequest) -> ChatResponse:
        start_time = time.time()
        trace_id = str(uuid.uuid4())
        
        try:
            bot = await prisma.bot.find_unique(where={"id": bot_id})
            if not bot:
                raise ValueError("Bot not found")
            
            if bot.use_advanced_rag:
                return await self._chat_with_advanced_rag(bot, chat_request, trace_id, start_time)
            else:
                return await self._chat_with_simple_rag(bot, chat_request, trace_id, start_time)
                
        except Exception as e:
            session_id = chat_request.session_id or str(uuid.uuid4())
            return ChatResponse(
                message=f"Maaf, terjadi kesalahan dalam memproses pesan Anda: {str(e)}",
                sources=[],
                session_id=session_id,
                trace_id=trace_id,
                metadata={"error": str(e)},
                processing_time=time.time() - start_time
            )
    
    async def _chat_with_advanced_rag(self, bot, chat_request: ChatRequest, trace_id: str, start_time: float) -> ChatResponse:
        advanced_result = await self.advanced_rag_service.process_query(
            bot=bot,
            query=chat_request.message,
            user_id=chat_request.user_id
        )
        
        session_id = chat_request.session_id or str(uuid.uuid4())

        chat_saved = False
        if bot.enable_chat_history:
            try:
                await self._save_chat_history(
                    bot.id,
                    chat_request.user_id,
                    session_id,
                    chat_request.platform,
                    chat_request.message,
                    advanced_result["message"],
                    advanced_result["sources"],
                    {**chat_request.metadata, **advanced_result["metadata"]},
                    trace_id
                )
                chat_saved = True
            except Exception as e:
                print(f"Failed to save chat: {e}")
                chat_saved = False
        
        processing_time = time.time() - start_time
        
        return ChatResponse(
            message=advanced_result["message"],
            sources=advanced_result["sources"],
            session_id=session_id,
            trace_id=trace_id,
            metadata={
                **chat_request.metadata, 
                **advanced_result["metadata"],
                "saved": chat_saved
            },
            processing_time=processing_time
        )
    
    async def _chat_with_simple_rag(self, bot, chat_request: ChatRequest, trace_id: str, start_time: float) -> ChatResponse:
        history = []
        if chat_request.use_history and bot.enable_chat_history:
            history = await self._get_chat_history(
                bot.id, 
                chat_request.user_id,
                chat_request.session_id,
                chat_request.platform,
                chat_request.max_history
            )

        sources = await self._retrieve_documents(bot, chat_request.message)

        response_text = await self._generate_response(
            bot, 
            chat_request.message, 
            sources, 
            history
        )
        
        session_id = chat_request.session_id or str(uuid.uuid4())

        await self._save_chat_history(
            bot.id,
            chat_request.user_id,
            session_id,
            chat_request.platform,
            chat_request.message,
            response_text,
            sources,
            chat_request.metadata,
            trace_id
        )
        
        processing_time = time.time() - start_time
        
        return ChatResponse(
            message=response_text,
            sources=sources,
            session_id=session_id,
            trace_id=trace_id,
            metadata=chat_request.metadata,
            processing_time=processing_time
        )
    
    async def _retrieve_documents(self, bot, query: str) -> List[Dict[str, Any]]:
        try:
            results = await self.document_service.search_documents(
                bot.id,
                query,
                bot.top_k,
                bot.similarity_threshold
            )
            
            sources = []
            for i, result in enumerate(results):
                sources.append({
                    "index": i + 1,
                    "content": result["content"],
                    "similarity": result["similarity"],
                    "source_name": result["source_name"],
                    "metadata": result["metadata"]
                })
            
            return sources
            
        except Exception as e:
            print(f"Document retrieval error: {e}")
            return []
    
    async def _generate_response(
        self, 
        bot, 
        query: str, 
        sources: List[Dict[str, Any]], 
        history: List[Dict[str, str]]
    ) -> str:
        try:
            llm_provider = get_llm_from_bot_config(bot)
            
            context = self._format_context(sources)

            messages = []

            if bot.system_prompt:
                messages.append({
                    "role": "system",
                    "content": bot.system_prompt
                })
            
            if history:
                for hist_msg in history[-10:]:
                    messages.append(hist_msg)
            
            rag_content = bot.rag_prompt.format(
                context=context,
                question=query
            )
            
            messages.append({
                "role": "user",
                "content": rag_content
            })
            
            response = await llm_provider.generate(messages)
            
            return response
            
        except Exception as e:
            print(f"Response generation error: {e}")
            return f"Maaf, saya tidak dapat menemukan informasi yang relevan untuk menjawab pertanyaan Anda. Error: {str(e)}"
    
    def _format_context(self, sources: List[Dict[str, Any]]) -> str:
        if not sources:
            return "Tidak ada informasi yang ditemukan."
        
        context_parts = []
        for source in sources:
            similarity = source.get("similarity", 0)
            content = source.get("content", "")
            source_name = source.get("source_name", "Unknown")
            
            context_parts.append(
                f"[Sumber: {source_name}, Relevansi: {similarity:.2f}]\n{content}"
            )
        
        return "\n\n".join(context_parts)
    
    async def _get_chat_history(
        self,
        bot_id: str,
        user_id: str,
        session_id: Optional[str],
        platform: Platform,
        max_history: Optional[int]
    ) -> List[Dict[str, str]]:
        
        try:
            where_clause = {
                "botId": bot_id,
                "user_id": user_id,
                "platform": platform.value
            }
            
            if session_id:
                where_clause["session_id"] = session_id

            limit = max_history or 20
            history_records = await prisma.chathistory.find_many(
                where=where_clause,
                order={"createdAt": "desc"},
                take=limit
            )

            messages = []
            for record in reversed(history_records):
                messages.extend([
                    {"role": "user", "content": record.human_message},
                    {"role": "assistant", "content": record.ai_message}
                ])
            
            return messages
            
        except Exception as e:
            print(f"Chat history retrieval error: {e}")
            return []
    
    async def _save_chat_history(
        self,
        bot_id: str,
        user_id: str,
        session_id: str,
        platform: Platform,
        human_message: str,
        ai_message: str,
        sources: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        trace_id: str
    ):
        try:
            bot = await prisma.bot.find_unique(where={"id": bot_id})
            if not bot:
                print(f"❌ Bot {bot_id} not found!")
                return

            sources_json = Json(sources) if sources else Json([])
            metadata_json = Json(metadata) if metadata else Json({})
            
            result = await prisma.chathistory.create(
                data={
                    "botId": bot_id,
                    "user_id": user_id,
                    "session_id": session_id,
                    "platform": platform.value,
                    "human_message": human_message,
                    "ai_message": ai_message,
                    "sources": sources_json,
                    "metadata": metadata_json,
                    "trace_id": trace_id
                }
            )
            print(f"✅ Chat saved successfully with ID: {result.id}")
            
        except Exception as e:
            print(f"❌ Save error: {e}")
            import traceback
            traceback.print_exc()
    
    async def get_chat_sessions(self, bot_id: str, user_id: str = None) -> List[Dict[str, Any]]:
        try:
            where_clause = {"botId": bot_id}
            if user_id:
                where_clause["user_id"] = user_id
            
            sessions = await prisma.query_raw(
                """
                SELECT 
                    session_id,
                    user_id,
                    platform,
                    COUNT(*) as message_count,
                    MAX("createdAt") as last_activity,
                    MIN("createdAt") as first_activity
                FROM chat_history 
                WHERE "botId" = $1
                AND session_id IS NOT NULL
                GROUP BY session_id, user_id, platform
                ORDER BY last_activity DESC
                """,
                bot_id
            )
            
            return [
                {
                    "session_id": session["session_id"],
                    "user_id": session["user_id"],
                    "platform": session["platform"],
                    "message_count": session["message_count"],
                    "last_activity": session["last_activity"],
                    "first_activity": session["first_activity"]
                }
                for session in sessions
            ]
            
        except Exception as e:
            print(f"Failed to get chat sessions: {e}")
            return []
    
    async def get_session_history(
        self,
        bot_id: str,
        session_id: str,
        limit: int = 50
    ) -> List[ChatHistoryItem]:
        
        try:
            history = await prisma.chathistory.find_many(
                where={
                    "botId": bot_id,
                    "session_id": session_id
                },
                order={"createdAt": "asc"},
                take=limit
            )
            
            return [ChatHistoryItem.model_validate(item) for item in history]
            
        except Exception as e:
            print(f"Failed to get session history: {e}")
            return []
    
    async def clear_chat_history(
        self,
        bot_id: str,
        user_id: str = None,
        session_id: str = None
    ) -> bool:

        try:
            where_clause = {"botId": bot_id}
            
            if user_id:
                where_clause["user_id"] = user_id
            
            if session_id:
                where_clause["session_id"] = session_id
            
            await prisma.chathistory.delete_many(where=where_clause)
            return True
            
        except Exception as e:
            print(f"Failed to clear chat history: {e}")
            return False