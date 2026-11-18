from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_xai import ChatXAI

from core.config import settings

groq_llm = ChatGroq(
    model=settings.GROQ_MODEL_NAME,
    api_key=settings.GROQ_API_KEY.get_secret_value(),
    temperature=0.3,
)


ollama_llm = ChatOllama(
    model="qwen3.5", base_url="http://192.168.59.:11434", temperature=0.3
)


def get_xai_llm() -> ChatXAI | None:
    """Get XAI LLM instance if API key is configured."""
    if not settings.XAI_API_KEY:
        return None
    return ChatXAI(
        model=settings.XAI_MODEL_NAME,
        api_key=settings.XAI_API_KEY.get_secret_value(),
        base_url=settings.XAI_BASE_URL,
        temperature=0.3,
    )


xai_llm = get_xai_llm()
