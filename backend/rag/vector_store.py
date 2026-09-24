from functools import lru_cache

from langchain_chroma import Chroma

from core.config import settings
from .embeddings import get_embeddings


@lru_cache(maxsize=1)
def get_vector_store() -> Chroma:
    settings.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)

    return Chroma(
        collection_name=settings.VECTOR_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(settings.VECTOR_STORE_DIR),
        collection_metadata={"hnsw:space": "cosine"},
    )
