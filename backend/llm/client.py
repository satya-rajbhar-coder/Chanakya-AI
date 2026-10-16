from langchain_groq import ChatGroq

from core.config import settings

groq_llm = ChatGroq(
    model=settings.GROQ_MODEL_NAME, api_key=settings.GROQ_API_KEY, temperature=0.3
)

