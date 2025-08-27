# -- IMPORT --

# state scheme import
from pydantic import BaseModel, Field, SecretStr
from typing import List, Dict, Any, Annotated, Optional
from typing_extensions import TypedDict

# llm langchain import
from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_openai import ChatOpenAI

# env import
from config import MISTRAL_API_KEY, OPENROUTER_API_KEY, HF_TOKEN 

# langchain import
from langchain_core.utils.utils import secret_from_env

# -- SETUP SCHEMA STATE --

# Define the state schema for the pipeline
class ChatState(BaseModel):
    messages: List[Dict[str, Any]]

    
# Define OpenRouter integration with langchain
class ChatOpenRouter(ChatOpenAI):
    openai_api_key: Optional[SecretStr] = Field(
        alias="api_key", default_factory=secret_from_env("OPENROUTER_API_KEY", default=None)
    )
    
    @property
    def lc_secrets(self) -> dict[str, str]:
        return {"openai_api_key": "OPENROUTER_API_KEY"}

    def __init__(self,
                 openai_api_key: Optional[str] = None,
                 **kwargs):
        openai_api_key = openai_api_key or os.environ.get("OPENROUTER_API_KEY")
        super().__init__(base_url="https://openrouter.ai/api/v1", openai_api_key=openai_api_key, **kwargs)
        
        
# -- SETUP DOCUMENT RELEVANCE --

# Setup document relevance & hallucination grader
class Grader(BaseModel):
    binary_score: str = Field(..., description="Either 'yes' or 'no'") # document relevance

    
# -- SETUP LLM --

def get_llm():
    """Setup the base LLM (MistralAI)."""
    return ChatMistralAI(
        model="mistral-small-latest",
        api_key=MISTRAL_API_KEY,
        temperature=0,
    )


def get_embedding_models():
    """Setup the embedding LLM (Mistral AI Embeddings)."""
    return MistralAIEmbeddings(
        model="mistral-embed",
        api_key=MISTRAL_API_KEY
    )


def get_llm_json(llm):
    """Return LLM with structured output enabled."""
    return llm.with_structured_output(Grader)