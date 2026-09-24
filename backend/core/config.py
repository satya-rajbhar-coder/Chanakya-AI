from pathlib import Path
from typing import Literal

from pydantic import Field
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
    MODEL_NAME: str = "qwen3.5"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    LLM_TIMEOUT_SECONDS: float = 120.0

    # --- RAG -------------------------------------------------------------
    EMBEDDING_MODEL: str = "qwen3-embedding"   # ollama pull nomic-embed-text
    VECTOR_STORE_DIR: Path = Path("storage/chroma")
    VECTOR_COLLECTION: str = "documents"
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    RETRIEVER_K: int = 5
    # Cosine distance cut-off (0 = identical, 2 = opposite). None = keep top-k.
    RAG_MAX_DISTANCE: float | None = None
    MAX_UPLOAD_MB: int = 20

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
