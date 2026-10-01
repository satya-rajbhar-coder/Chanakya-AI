from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from core.config import settings

ollama_llm = ChatOllama(
    model=settings.OLLAMA_MODEL_NAME,
    base_url=settings.OLLAMA_BASE_URL,
    temperature=0.3,
    client_kwargs={"timeout": settings.LLM_TIMEOUT_SECONDS},
)

groq_llm = ChatGroq(
    model=settings.GROQ_MODEL_NAME, api_key=settings.GROQ_API_KEY, temperature=0.3
)
