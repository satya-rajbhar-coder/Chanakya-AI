from functools import lru_cache

from langchain_google_genai.embeddings import GoogleGenerativeAIEmbeddings
from langchain_ollama.embeddings import OllamaEmbeddings

from core.config import settings


@lru_cache(maxsize=1)
def get_google_embeddings() -> GoogleGenerativeAIEmbeddings:
    return GoogleGenerativeAIEmbeddings(
        model=settings.GOOGLE_EMBEDDING_MODEL,
        api_key=settings.GOOGLE_API_KEY,
        output_dimensionality=settings.VECTOR_DIMENSION,
    )


@lru_cache(maxsize=1)
def get_ollama_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model="qwen3-embedding",
        dimensions=settings.VECTOR_DIMENSION,
        base_url="http://192.168.1.59:11434",
    )
