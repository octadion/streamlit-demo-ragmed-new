# -- IMPORT --

# llm langchain import
from mistralai.client import ChatMistralAI, MistralAIEmbeddings

# env import
from config import MISTRAL_API_KEY  

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

def get_llm_json(llm, output_schema):
    """Return LLM with structured output enabled."""
    return llm.with_structured_output(output_schema)