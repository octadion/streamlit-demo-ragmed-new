from typing import List, Dict, Any, Optional
from langchain.schema import Document
from app.services.document_service import DocumentService


class PgVectorRetrieverAdapter:
    def __init__(self, bot_id: str, document_service: DocumentService, domain: str = None):
        self.bot_id = bot_id
        self.document_service = document_service
        self.domain = domain
        
    async def invoke(self, query: str, **kwargs) -> List[Document]:
        results = await self.document_service.search_documents_with_domain(
            bot_id=self.bot_id,
            query=query,
            top_k=kwargs.get('k', 3),
            similarity_threshold=kwargs.get('similarity_threshold', 0.7),
            domain=self.domain
        )
 
        documents = []
        for result in results:
            doc = Document(
                page_content=result["content"],
                metadata={
                    "source": result["source_name"],
                    "similarity": result["similarity"],
                    "medical_domain": self.domain,
                    **result.get("metadata", {})
                }
            )
            documents.append(doc)
            
        return documents


def create_domain_retrievers(bot_id: str, document_service: DocumentService) -> List[Dict]:
    domains = [
        {
            "name": "RA", 
            "description": "Information about rheumatoid arthritis (RA).",
            "domain": "RA"
        },
        {
            "name": "SLE",
            "description": "General information about Systemic Lupus Erythematosus (SLE).", 
            "domain": "SLE"
        },
        {
            "name": "Arthritis",
            "description": "General information about arthritis.",
            "domain": "Arthritis"
        },
        {
            "name": "Spondyloarthritis", 
            "description": "General information about Spondyloarthritis.",
            "domain": "Spondyloarthritis"
        },
        {
            "name": "Vasculitis",
            "description": "General information about Vasculitis.", 
            "domain": "Vasculitis"
        }
    ]
    
    retrievers = []
    for domain_config in domains:
        retriever = PgVectorRetrieverAdapter(
            bot_id=bot_id,
            document_service=document_service,
            domain=domain_config["domain"]
        )
        
        retrievers.append({
            "name": domain_config["name"],
            "description": domain_config["description"], 
            "retriever": retriever
        })
    
    return retrievers