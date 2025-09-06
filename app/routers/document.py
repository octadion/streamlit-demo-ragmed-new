from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Query, Form
from typing import List
import os
from pathlib import Path

from app.auth import get_global_auth
from app.database import prisma
from app.models.document import (
    TextUpload, UrlUpload, SourceResponse, DocumentResponse, 
    ProcessingStatus, SearchRequest, SearchResponse, SearchResult,
    SourceType, SourceStatus, DocumentUploadText, DocumentUploadURL
)
from app.services.document_service import DocumentService, save_uploaded_file
from prisma import Json

router = APIRouter()

doc_service = DocumentService()

@router.post("/upload-text")
async def upload_text(
    upload_data: DocumentUploadText,
    background_tasks: BackgroundTasks,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        text_size_mb = len(upload_data.content.encode('utf-8')) / (1024 * 1024)
        
        source = await prisma.botsource.create(
            data={
                "botId": bot_id,
                "name": upload_data.name,
                "type": "text",
                "content": upload_data.content,
                "file_size_mb": text_size_mb,
                "status": SourceStatus.PENDING,
                "metadata": Json({"medical_domain": upload_data.medical_domain if upload_data.medical_domain else None,"upload_type": "text"})
            }
        )
        
        background_tasks.add_task(
            doc_service.process_text_upload,
            bot_id,
            source.id, 
            upload_data.content
        )
        
        return {
            "message": "Text uploaded successfully, processing started",
            "source_id": source.id,
            "medical_domain": upload_data.medical_domain,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload-file")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    medical_domain: str = Form(None, description="Medical domain for advanced RAG"),
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        if not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        allowed_types = {
            "text/plain": ".txt",
            "application/pdf": ".pdf"
        }
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type. Allowed: {list(allowed_types.values())}"
            )
        
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)
        
        if file_size_mb > 10:
            raise HTTPException(status_code=400, detail="File too large (max 10MB)")
        
        file_path = await save_uploaded_file(file_content, file.filename)
        
        metadata_dict = {
            "medical_domain": medical_domain if medical_domain and medical_domain.strip() else None,
            "upload_type": "file",
            "file_type": file.content_type
        }
        
        source = await prisma.botsource.create(
            data={
                "botId": bot_id,
                "name": file.filename,
                "type": "file",
                "file_path": file_path,
                "file_size_mb": file_size_mb,
                "status": SourceStatus.PENDING,
                "metadata": Json(metadata_dict)
            }
        )
        
        background_tasks.add_task(
            doc_service.process_file_upload,
            bot_id,
            source.id,
            file_path,
            file.content_type
        )
        
        return {
            "message": "File uploaded successfully, processing started",
            "source_id": source.id,
            "filename": file.filename,
            "medical_domain": medical_domain,
            "size_mb": file_size_mb,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.post("/upload-url")
async def upload_url(
    upload_data: DocumentUploadURL,
    background_tasks: BackgroundTasks,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        source = await prisma.botsource.create(
            data={
                "botId": bot_id,
                "name": upload_data.name,
                "type": "url",
                "url": upload_data.url,
                "status": SourceStatus.PENDING,
                "metadata": Json({
                    "medical_domain": upload_data.medical_domain if upload_data.medical_domain else None,
                    "upload_type": "url"
                })
            }
        )
        
        background_tasks.add_task(
            doc_service.process_url_upload,
            bot_id,
            source.id,
            upload_data.url
        )
        
        return {
            "message": "URL upload started, processing in background", 
            "source_id": source.id,
            "url": upload_data.url,
            "medical_domain": upload_data.medical_domain,
            "status": "processing"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.get("/sources", response_model=List[SourceResponse])
async def list_sources(
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        sources = await prisma.botsource.find_many(
            where={"botId": bot_id},
            order={"createdAt": "desc"}
        )
        
        return [SourceResponse.model_validate(source) for source in sources]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch sources: {str(e)}")


@router.get("/sources/{source_id}", response_model=SourceResponse)
async def get_source(
    source_id: str,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        source = await prisma.botsource.find_first(
            where={"id": source_id, "botId": bot_id}
        )
        
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        return SourceResponse.model_validate(source)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch source: {str(e)}")


@router.get("/sources/{source_id}/status", response_model=ProcessingStatus)
async def get_processing_status(
    source_id: str,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        source = await prisma.botsource.find_first(
            where={"id": source_id, "botId": bot_id}
        )
        
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")

        total_docs = await prisma.botdocument.count(
            where={"sourceId": source_id}
        )

        progress = 1.0 if source.status == SourceStatus.COMPLETED else 0.0
        if source.status == SourceStatus.PROCESSING:
            progress = 0.5
        
        return ProcessingStatus(
            source_id=source_id,
            name=source.name,
            status=source.status,
            progress=progress,
            total_chunks=total_docs if total_docs > 0 else None,
            processed_chunks=total_docs if source.status == SourceStatus.COMPLETED else None,
            error_message=source.error_message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch status: {str(e)}")


@router.delete("/sources/{source_id}")
async def delete_source(
    source_id: str,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        source = await prisma.botsource.find_first(
            where={"id": source_id, "botId": bot_id}
        )
        
        if not source:
            raise HTTPException(status_code=404, detail="Source not found")
        
        if source.file_path and os.path.exists(source.file_path):
            os.remove(source.file_path)
        
        await prisma.botsource.delete(where={"id": source_id})
        
        return {"message": f"Source {source_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete source: {str(e)}")


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    bot_id: str = Query(..., description="Bot ID"),
    source_id: str = Query(None, description="Filter by source ID"),
    limit: int = Query(default=50, le=200, description="Maximum number of documents"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        where_clause = {"botId": bot_id}
        if source_id:
            where_clause["sourceId"] = source_id
        
        documents = await prisma.botdocument.find_many(
            where=where_clause,
            take=limit,
            order={"createdAt": "desc"}
        )
        
        return [DocumentResponse.model_validate(doc) for doc in documents]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    search_request: SearchRequest,
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")
        
        top_k = search_request.top_k or bot.top_k
        similarity_threshold = search_request.similarity_threshold or bot.similarity_threshold
        
        results = await doc_service.search_documents(
            bot_id,
            search_request.query,
            top_k,
            similarity_threshold
        )
        
        search_results = [
            SearchResult(
                content=result["content"],
                metadata=result["metadata"],
                similarity=result["similarity"],
                source_name=result["source_name"]
            )
            for result in results
        ]
        
        return SearchResponse(
            query=search_request.query,
            results=search_results,
            total_results=len(search_results)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/stats")
async def get_documents_stats(
    bot_id: str = Query(..., description="Bot ID"),
    auth=Depends(get_global_auth)
):
    try:
        bot = await prisma.bot.find_unique(where={"id": bot_id})
        if not bot:
            raise HTTPException(status_code=404, detail="Bot not found")

        total_sources = await prisma.botsource.count(where={"botId": bot_id})
        completed_sources = await prisma.botsource.count(
            where={"botId": bot_id, "status": SourceStatus.COMPLETED}
        )
        processing_sources = await prisma.botsource.count(
            where={"botId": bot_id, "status": SourceStatus.PROCESSING}
        )
        failed_sources = await prisma.botsource.count(
            where={"botId": bot_id, "status": SourceStatus.FAILED}
        )

        total_documents = await prisma.botdocument.count(where={"botId": bot_id})

        sources_with_size = await prisma.botsource.find_many(
            where={"botId": bot_id}
        )
        total_size_mb = sum(source.file_size_mb for source in sources_with_size)
        
        return {
            "bot_id": bot_id,
            "sources": {
                "total": total_sources,
                "completed": completed_sources,
                "processing": processing_sources,
                "failed": failed_sources
            },
            "documents": {
                "total": total_documents
            },
            "storage": {
                "total_size_mb": round(total_size_mb, 2)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@router.get("/providers")
async def get_available_providers():

    from app.services.embedding_service import EmbeddingProviderFactory
    
    providers = EmbeddingProviderFactory.get_available_providers()
    return {
        "providers": providers,
        "current": {
            "provider": os.getenv("EMBEDDING_PROVIDER", "mistral"),
            "model": os.getenv("EMBEDDING_MODEL", "auto")
        }
    }