import os
from typing import List, Dict, Any
from abc import ABC, abstractmethod
import asyncio

try:
    from langchain_mistralai import MistralAIEmbeddings
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

try:
    from langchain_openai import OpenAIEmbeddings
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_google_genai import GoogleGenerativeAIEmbeddings
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class BaseEmbeddingProvider(ABC):
    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model
        self.embeddings = self._initialize_embeddings()
    
    @abstractmethod
    def _initialize_embeddings(self):
        pass
    
    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, 
            self.embeddings.embed_documents,
            texts
        )
    
    async def embed_query(self, text: str) -> List[float]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.embeddings.embed_query,
            text
        )


class MistralEmbeddingProvider(BaseEmbeddingProvider):
    def _initialize_embeddings(self):
        if not MISTRAL_AVAILABLE:
            raise ImportError("MistralAI not available. Install: pip install langchain-mistralai")
        
        return MistralAIEmbeddings(
            model=self.model,
            mistral_api_key=self.api_key
        )


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    def _initialize_embeddings(self):
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI not available. Install: pip install langchain-openai")
        
        return OpenAIEmbeddings(
            model=self.model,
            openai_api_key=self.api_key
        )


class GeminiEmbeddingProvider(BaseEmbeddingProvider):
    def _initialize_embeddings(self):
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini not available. Install: pip install langchain-google-genai")
        
        return GoogleGenerativeAIEmbeddings(
            model=self.model,
            google_api_key=self.api_key
        )


class EmbeddingProviderFactory:
    PROVIDERS = {
        "mistral": {
            "class": MistralEmbeddingProvider,
            "default_model": "mistral-embed",
            "available": MISTRAL_AVAILABLE
        },
        "openai": {
            "class": OpenAIEmbeddingProvider,
            "default_model": "text-embedding-ada-002",
            "available": OPENAI_AVAILABLE
        },
        "gemini": {
            "class": GeminiEmbeddingProvider,
            "default_model": "models/embedding-001",
            "available": GEMINI_AVAILABLE
        }
    }
    
    @classmethod
    def get_available_providers(cls) -> Dict[str, Dict]:
        return {
            name: {
                "default_model": config["default_model"],
                "available": config["available"]
            }
            for name, config in cls.PROVIDERS.items()
            if config["available"]
        }
    
    @classmethod
    def create_provider(cls, provider_name: str, api_key: str, model: str = None) -> BaseEmbeddingProvider:
        if provider_name not in cls.PROVIDERS:
            available = list(cls.PROVIDERS.keys())
            raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")
        
        provider_config = cls.PROVIDERS[provider_name]
        
        if not provider_config["available"]:
            raise ImportError(f"Provider '{provider_name}' is not available. Install required dependencies.")
        
        if not model:
            model = provider_config["default_model"]
        
        provider_class = provider_config["class"]
        return provider_class(api_key, model)


def get_embedding_provider(provider: str = None, model: str = None) -> BaseEmbeddingProvider:
    if not provider:
        provider = os.getenv("EMBEDDING_PROVIDER", "mistral").lower()
    
    if not model:
        model = os.getenv("EMBEDDING_MODEL")

    api_key_map = {
        "mistral": "MISTRAL_API_KEY",
        "openai": "OPENAI_API_KEY", 
        "gemini": "GEMINI_API_KEY"
    }
    
    api_key_env = api_key_map.get(provider)
    if not api_key_env:
        raise ValueError(f"Unknown provider: {provider}")
    
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ValueError(f"{api_key_env} environment variable is required for {provider}")
    
    return EmbeddingProviderFactory.create_provider(provider, api_key, model)


def get_embeddings_service(provider: str = None, model: str = None):
    return get_embedding_provider(provider, model)