from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class BotCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Bot name")
    description: Optional[str] = Field(None, max_length=500, description="Bot description")

    model: str = Field(default="mistral-small-latest", description="LLM model name")
    provider: str = Field(default="mistral", description="LLM provider")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Model temperature")
    max_tokens: int = Field(default=1000, ge=100, le=4000, description="Maximum tokens")

    top_k: int = Field(default=3, ge=1, le=20, description="Number of documents to retrieve")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Similarity threshold")
    use_reranking: bool = Field(default=True, description="Enable reranking")
    use_multi_query: bool = Field(default=True, description="Enable multi-query retrieval")
    enable_chat_history: bool = Field(default=True, description="Enable chat history")

    system_prompt: str = Field(
        default="You are a helpful AI assistant.",
        description="System prompt for the bot"
    )
    rag_prompt: str = Field(
        default="Answer the question based on the following context: {context}\n\nQuestion: {question}\nAnswer:",
        description="RAG prompt template"
    )

    enable_internet_search: bool = Field(default=False, description="Enable internet search")
    use_advanced_rag: bool = Field(default=False, description="Enable advanced/agentic RAG")
    max_retries: int = Field(default=3, ge=1, le=10, description="Maximum retries for advanced RAG")


class BotUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=500)

    model: Optional[str] = None
    provider: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=100, le=4000)

    top_k: Optional[int] = Field(None, ge=1, le=20)
    similarity_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    use_reranking: Optional[bool] = None
    use_multi_query: Optional[bool] = None
    enable_chat_history: Optional[bool] = None

    system_prompt: Optional[str] = None
    rag_prompt: Optional[str] = None

    enable_internet_search: Optional[bool] = None
    use_advanced_rag: Optional[bool] = None
    max_retries: Optional[int] = Field(None, ge=1, le=10)


class BotResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    createdAt: datetime
    updatedAt: datetime

    model: str
    provider: str
    temperature: float
    max_tokens: int

    top_k: int
    similarity_threshold: float
    use_reranking: bool
    use_multi_query: bool
    enable_chat_history: bool
    
    system_prompt: str
    rag_prompt: str

    enable_internet_search: bool
    
    class Config:
        from_attributes = True

    use_advanced_rag: bool
    max_retries: int


class BotListResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    createdAt: datetime
    model: str
    provider: str
    
    class Config:
        from_attributes = True

    use_advanced_rag: bool
    max_retries: int