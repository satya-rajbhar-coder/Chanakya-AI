from langchain_ollama import ChatOllama

from core.config import settings

llm = ChatOllama(
    model=settings.MODEL_NAME,
    base_url=settings.OLLAMA_BASE_URL,
    temperature=0.3,
    client_kwargs={"timeout": settings.LLM_TIMEOUT_SECONDS},
)
