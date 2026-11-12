from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama

from core.config import settings

groq_llm = ChatGroq(
    model=settings.GROQ_MODEL_NAME, api_key=settings.GROQ_API_KEY, temperature=0.3
)


ollama_llm = ChatOllama(
    model="qwen3.5", base_url="http://192.168.1.84:11434", temperature=0.3
)
