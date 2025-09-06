import os
import asyncio
from typing import List, Dict, Any, Optional
from io import BytesIO
import tempfile
import aiofiles
from pathlib import Path

import re
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader
import requests
from bs4 import BeautifulSoup

try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

from langchain_mistralai import MistralAIEmbeddings

from app.database import prisma
from app.models.document import SourceStatus
from app.services.embedding_service import get_embedding_provider


class DocumentProcessor:
    def __init__(self):
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        
    async def extract_text_from_file(self, file_path: str, file_type: str) -> str:
        if file_type == "text/plain":
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                return await f.read()
                
        elif file_type == "application/pdf":
            if not PDF_AVAILABLE:
                raise ValueError("PyPDF2 not installed. Install with: pip install PyPDF2")
            
            text = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    text += page.extract_text() + "\n"
            return text
            
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    async def extract_text_from_url(self, url: str) -> str:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')

            for script in soup(["script", "style"]):
                script.decompose()

            text = soup.get_text()

            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text
            
        except Exception as e:
            raise ValueError(f"Failed to extract text from URL: {str(e)}")
    
    def chunk_text(self, text: str) -> List[str]:
        return self.text_splitter.split_text(text)
    
    def clean_text(self, text: str) -> str:
        text = re.sub(r'\s+', ' ', text)
        
        text = text.replace('\x00', '')

        text = text.strip()
        
        return text


class EmbeddingService:
    def __init__(self, provider: str = None, model: str = None):
        self.embedding_provider = get_embedding_provider(provider, model)
    
    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        try:
            return await self.embedding_provider.embed_documents(texts)
        except Exception as e:
            raise ValueError(f"Failed to generate embeddings: {str(e)}")
    
    async def generate_single_embedding(self, text: str) -> List[float]:
        try:
            return await self.embedding_provider.embed_query(text)
        except Exception as e:
            raise ValueError(f"Failed to generate embedding: {str(e)}")


class DocumentService:
    def __init__(self, embedding_provider: str = None, embedding_model: str = None):
        self.processor = DocumentProcessor()
        self.embedding_service = EmbeddingService(embedding_provider, embedding_model)
    
    async def process_file_upload(self, bot_id: str, source_id: str, file_path: str, file_type: str):
        try:
            await prisma.botsource.update(
                where={"id": source_id},
                data={"status": SourceStatus.PROCESSING}
            )

            text = await self.processor.extract_text_from_file(file_path, file_type)
            text = self.processor.clean_text(text)
            
            if not text.strip():
                raise ValueError("No text content found in file")

            chunks = self.processor.chunk_text(text)

            embeddings = await self.embedding_service.generate_embeddings(chunks)

            await self._store_documents(bot_id, source_id, chunks, embeddings)

            await prisma.botsource.update(
                where={"id": source_id},
                data={"status": SourceStatus.COMPLETED}
            )
            
        except Exception as e:
            await prisma.botsource.update(
                where={"id": source_id},
                data={
                    "status": SourceStatus.FAILED,
                    "error_message": str(e)
                }
            )
            raise
    
    async def process_text_upload(self, bot_id: str, source_id: str, text: str):
        try:
            await prisma.botsource.update(
                where={"id": source_id},
                data={"status": SourceStatus.PROCESSING}
            )

            text = self.processor.clean_text(text)
            
            if not text.strip():
                raise ValueError("No text content provided")

            chunks = self.processor.chunk_text(text)

            embeddings = await self.embedding_service.generate_embeddings(chunks)

            await self._store_documents(bot_id, source_id, chunks, embeddings)

            await prisma.botsource.update(
                where={"id": source_id},
                data={"status": SourceStatus.COMPLETED}
            )
            
        except Exception as e:
            await prisma.botsource.update(
                where={"id": source_id},
                data={
                    "status": SourceStatus.FAILED,
                    "error_message": str(e)
                }
            )
            raise
    
    async def process_url_upload(self, bot_id: str, source_id: str, url: str):
        try:
            await prisma.botsource.update(
                where={"id": source_id},
                data={"status": SourceStatus.PROCESSING}
            )
            text = await self.processor.extract_text_from_url(url)
            text = self.processor.clean_text(text)
            
            if not text.strip():
                raise ValueError("No text content found at URL")
            
            chunks = self.processor.chunk_text(text)
            
            embeddings = await self.embedding_service.generate_embeddings(chunks)
            
            await self._store_documents(bot_id, source_id, chunks, embeddings)

            await prisma.botsource.update(
                where={"id": source_id},
                data={"status": SourceStatus.COMPLETED}
            )
            
        except Exception as e:
            await prisma.botsource.update(
                where={"id": source_id},
                data={
                    "status": SourceStatus.FAILED,
                    "error_message": str(e)
                }
            )
            raise
    
    async def _store_documents(self, bot_id: str, source_id: str, chunks: List[str], embeddings: List[List[float]]):
        source = await prisma.botsource.find_unique(where={"id": source_id})
        source_metadata = source.metadata if source and source.metadata else {}
        medical_domain = source_metadata.get("medical_domain")
        
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            vector_str = f"[{','.join(map(str, embedding))}]"
            token_count = len(chunk.split())
            
            chunk_metadata = {
                "chunk_index": i,
                "total_chunks": len(chunks),
                "medical_domain": medical_domain,
                "source_type": source_metadata.get("upload_type", "unknown")
            }
            
            await prisma.execute_raw(
                """
                INSERT INTO bot_documents ("botId", "sourceId", content, embedding, metadata, chunk_index, token_count)
                VALUES ($1, $2, $3, $4::vector, $5, $6, $7)
                """,
                bot_id, source_id, chunk, vector_str, chunk_metadata, i, token_count
            )
    
    async def search_documents(self, bot_id: str, query: str, top_k: int = 5, similarity_threshold: float = 0.7) -> List[Dict[str, Any]]:
        try:
            query_embedding = await self.embedding_service.generate_single_embedding(query)
            query_vector = f"[{','.join(map(str, query_embedding))}]"

            results = await prisma.query_raw(
                f"""
                SELECT * FROM vector_similarity_search(
                    '{query_vector}'::vector,
                    '{bot_id}'::text,
                    {top_k}::int,
                    {similarity_threshold}::float
                )
                """
            )
            
            search_results = []
            for result in results:
                source = await prisma.botsource.find_unique(
                    where={"id": result["source_id"]},
                    select={"name": True}
                )
                
                search_results.append({
                    "content": result["content"],
                    "metadata": result["metadata"],
                    "similarity": result["similarity"],
                    "source_name": source.name if source else "Unknown"
                })
            
            return search_results
            
        except Exception as e:
            raise ValueError(f"Search failed: {str(e)}")
        
    
    async def search_documents_with_domain(
        self, 
        bot_id: str, 
        query: str, 
        top_k: int = 5, 
        similarity_threshold: float = 0.7,
        domain: str = None
    ) -> List[Dict[str, Any]]:
        
        try:
            query_embedding = await self.embedding_service.generate_single_embedding(query)
            query_vector = f"[{','.join(map(str, query_embedding))}]"

            base_query = f"""
            SELECT * FROM vector_similarity_search(
                '{query_vector}'::vector,
                '{bot_id}'::text,
                {top_k}::int,
                {similarity_threshold}::float
            )
            """

            if domain:
                full_query = f"""
                {base_query}
                WHERE (metadata->>'medical_domain' = '{domain}' OR metadata->>'medical_domain' IS NULL)
                """
            else:
                full_query = base_query

            results = await prisma.query_raw(full_query)
            
            search_results = []
            for result in results:
                source = await prisma.botsource.find_unique(
                    where={"id": result["source_id"]},
                    select={"name": True}
                )
                
                search_results.append({
                    "content": result["content"],
                    "metadata": result["metadata"],
                    "similarity": result["similarity"],
                    "source_name": source.name if source else "Unknown"
                })
            
            return search_results
            
        except Exception as e:
            raise ValueError(f"Domain search failed: {str(e)}")


async def save_uploaded_file(file_content: bytes, filename: str) -> str:
    upload_dir = Path("uploads")
    upload_dir.mkdir(exist_ok=True)
    
    file_path = upload_dir / filename
    
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(file_content)
    
    return str(file_path)