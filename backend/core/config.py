from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    CORS_ORIGINS: str = ""
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    SQL_ECHO: bool = False

    GROQ_MODEL_NAME: str = "openai/gpt-oss-120b"
    GROQ_API_KEY: SecretStr
    GOOGLE_API_KEY: SecretStr
    LLM_TIMEOUT_SECONDS: float = 120.0

    GOOGLE_EMBEDDING_MODEL: str
    VECTOR_STORE_URL: str
    VECTOR_COLLECTION: str = "vector_documents"
    VECTOR_DIMENSION: int = 3072
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    RETRIEVER_K: int = 5
    RAG_MAX_DISTANCE: float | None = None
    MAX_UPLOAD_MB: int = 20

    ANALYSIS_DB_URL_TEMPLATE: str
    # Foreign schema (postgres_fdw) present in EVERY client database that
    # exposes the shared main-database tables. All database communication
    # happens through the client connections only.
    ANALYSIS_MAIN_DB_SCHEMA: str = "pollmatrix"
    ANALYSIS_MAX_COLUMNS: int = 0
    ANALYSIS_SCHEMA_TABLE: str = "schema_catalog"
    ANALYSIS_NOTES_FILE: Path = Path("storage/schema_notes.json")
    ANALYSIS_TOP_TABLES: int = 3
    ANALYSIS_PAGE_SIZE: int = 100
    ANALYSIS_MAX_PAGE_SIZE: int = 500
    ANALYSIS_TIMEOUT_MS: int = 15_000
    ANALYSIS_EXPORT_TIMEOUT_MS: int = 300_000
    ANALYSIS_EXPORT_MAX_ROWS: int = 1_000_000
    ANALYSIS_TOKEN_MINUTES: int = 120

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
