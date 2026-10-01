from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- database / auth -------------------------------------------------
    DATABASE_URL: str
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SQL_ECHO: bool = False

    # --- LLM (Ollama) ----------------------------------------------------
    OLLAMA_MODEL_NAME: str = "qwen3.5"
    GROQ_MODEL_NAME: str = "openai/gpt-oss-120b"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    GROQ_API_KEY: SecretStr
    GOOGLE_API_KEY: SecretStr
    LLM_TIMEOUT_SECONDS: float = 120.0

    # --- RAG -------------------------------------------------------------
    OLLAMA_EMBEDDING_MODEL: str = "qwen3-embedding"
    GOOGLE_EMBEDDING_MODEL: str
    VECTOR_STORE_DIR: Path = Path("storage/chroma")
    VECTOR_STORE_URL: str
    VECTOR_COLLECTION: str = "vector_documents"
    VECTOR_DIMENSION: int = 4096
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    RETRIEVER_K: int = 5
    RAG_MAX_DISTANCE: float | None = None
    MAX_UPLOAD_MB: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
