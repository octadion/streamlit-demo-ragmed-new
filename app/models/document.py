from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    FILE = "file"
    TEXT = "text" 
    URL = "url"


class SourceStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"


class TextUpload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Source name")
    content: str = Field(..., min_length=1, description="Text content")


class UrlUpload(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Source name")
    url: str = Field(..., description="URL to scrape")


class SourceResponse(BaseModel):
    id: str
    botId: str
    name: str
    type: str
    file_path: Optional[str]
    url: Optional[str]
    file_size_mb: float
    status: str
    error_message: Optional[str]
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True


class DocumentResponse(BaseModel):
    id: int
    botId: str
    sourceId: str
    content: str
    metadata: Dict[str, Any]
    chunk_index: int
    token_count: int
    createdAt: datetime
    
    class Config:
        from_attributes = True


class ProcessingStatus(BaseModel):
    source_id: str
    name: str
    status: str
    progress: float  # 0.0 to 1.0
    total_chunks: Optional[int]
    processed_chunks: Optional[int]
    error_message: Optional[str]


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Search query")
    top_k: Optional[int] = Field(default=None, ge=1, le=20, description="Number of results")
    similarity_threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class SearchResult(BaseModel):
    content: str
    metadata: Dict[str, Any]
    similarity: float
    source_name: str


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int


class DocumentUploadText(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    content: str = Field(..., min_length=1)
    medical_domain: Optional[str] = Field(default=None, description="Medical domain for advanced RAG")

class DocumentUploadURL(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)  
    url: str = Field(..., description="URL to fetch content from")
    medical_domain: Optional[str] = Field(default=None, description="Medical domain for advanced RAG")