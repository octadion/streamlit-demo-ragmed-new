import os
from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod
import asyncio

try:
    from langchain_mistralai import ChatMistralAI
    MISTRAL_AVAILABLE = True
except ImportError:
    MISTRAL_AVAILABLE = False

try:
    from langchain_openai import ChatOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.language_models import BaseChatModel


class BaseLLMProvider(ABC):
    def __init__(self, api_key: str, model: str, temperature: float = 0.7, max_tokens: int = 1000):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.llm = self._initialize_llm()
    
    @abstractmethod
    def _initialize_llm(self) -> BaseChatModel:
        pass
    
    async def generate(self, messages: List[Dict[str, str]]) -> str:
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            self.llm.invoke,
            langchain_messages
        )
        
        return response.content
    
    async def stream_generate(self, messages: List[Dict[str, str]]):
        langchain_messages = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "system":
                langchain_messages.append(SystemMessage(content=content))
            elif role == "assistant":
                langchain_messages.append(AIMessage(content=content))
            else:
                langchain_messages.append(HumanMessage(content=content))

        try:
            async for chunk in self.llm.astream(langchain_messages):
                yield chunk.content
        except Exception as e:
            response = await self.generate(messages)
            yield response


class MistralLLMProvider(BaseLLMProvider):
    def _initialize_llm(self) -> BaseChatModel:
        if not MISTRAL_AVAILABLE:
            raise ImportError("MistralAI not available. Install: pip install langchain-mistralai")
        
        return ChatMistralAI(
            model=self.model,
            mistral_api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )


class OpenAILLMProvider(BaseLLMProvider):
    def _initialize_llm(self) -> BaseChatModel:
        if not OPENAI_AVAILABLE:
            raise ImportError("OpenAI not available. Install: pip install langchain-openai")
        
        return ChatOpenAI(
            model=self.model,
            openai_api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )


class GeminiLLMProvider(BaseLLMProvider):
    def _initialize_llm(self) -> BaseChatModel:
        if not GEMINI_AVAILABLE:
            raise ImportError("Gemini not available. Install: pip install langchain-google-genai")
        
        return ChatGoogleGenerativeAI(
            model=self.model,
            google_api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )


class LLMProviderFactory:
    PROVIDERS = {
        "mistral": {
            "class": MistralLLMProvider,
            "default_model": "mistral-small-latest",
            "available": MISTRAL_AVAILABLE
        },
        "openai": {
            "class": OpenAILLMProvider,
            "default_model": "gpt-3.5-turbo",
            "available": OPENAI_AVAILABLE
        },
        "gemini": {
            "class": GeminiLLMProvider,
            "default_model": "gemini-pro",
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
    def create_provider(
        cls, 
        provider_name: str, 
        api_key: str, 
        model: str = None,
        temperature: float = 0.7,
        max_tokens: int = 1000
    ) -> BaseLLMProvider:
        
        if provider_name not in cls.PROVIDERS:
            available = list(cls.PROVIDERS.keys())
            raise ValueError(f"Unknown provider '{provider_name}'. Available: {available}")
        
        provider_config = cls.PROVIDERS[provider_name]
        
        if not provider_config["available"]:
            raise ImportError(f"Provider '{provider_name}' is not available. Install required dependencies.")

        if not model:
            model = provider_config["default_model"]
        
        provider_class = provider_config["class"]
        return provider_class(api_key, model, temperature, max_tokens)


def get_llm_provider(
    provider: str = None, 
    model: str = None,
    temperature: float = None,
    max_tokens: int = None
) -> BaseLLMProvider:
    
    if not provider:
        provider = os.getenv("LLM_PROVIDER", "mistral").lower()
    
    if not model:
        model = os.getenv("LLM_MODEL")

    if temperature is None:
        temperature = float(os.getenv("LLM_TEMPERATURE", "0.7"))

    if max_tokens is None:
        max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1000"))

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
    
    return LLMProviderFactory.create_provider(
        provider, api_key, model, temperature, max_tokens
    )


def get_llm_from_bot_config(bot) -> BaseLLMProvider:
    api_key_map = {
        "mistral": "MISTRAL_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY"
    }
    
    api_key_env = api_key_map.get(bot.provider.lower())
    if not api_key_env:
        raise ValueError(f"Unknown provider: {bot.provider}")
    
    api_key = os.getenv(api_key_env)
    if not api_key:
        raise ValueError(f"{api_key_env} environment variable is required for {bot.provider}")
    
    return LLMProviderFactory.create_provider(
        bot.provider.lower(),
        api_key,
        bot.model,
        bot.temperature,
        bot.max_tokens
    )