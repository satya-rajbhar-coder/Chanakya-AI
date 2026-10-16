import os

# Dummy settings so `core.config.Settings()` can load without a real .env
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_app.db")
os.environ.setdefault("SECRET_KEY", "x" * 40)
os.environ.setdefault("GROQ_API_KEY", "dummy")
os.environ.setdefault("GOOGLE_API_KEY", "dummy")
os.environ.setdefault("GOOGLE_EMBEDDING_MODEL", "models/gemini-embedding-001")
os.environ.setdefault("VECTOR_STORE_URL", "postgresql+asyncpg://x:x@localhost/x")

import pytest
import sqlalchemy as sa


@pytest.fixture
def demo_db(tmp_path):
    """A throw-away SQLite database registered as analysis database 'demo'."""
    from core.config import settings
    from modules.analysis import registry

    url = f"sqlite:///{tmp_path / 'demo.db'}"
    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)"))
        conn.execute(
            sa.text("INSERT INTO items (id, name) VALUES (:id, :name)"),
            [{"id": i, "name": f"item{i}"} for i in range(1, 251)],
        )
    engine.dispose()

    previous_template = settings.ANALYSIS_DB_URL_TEMPLATE
    settings.ANALYSIS_DB_URL_TEMPLATE = f"sqlite:///{tmp_path}/{{name}}.db"
    registry.get_engine.cache_clear()
    yield "demo"
    settings.ANALYSIS_DB_URL_TEMPLATE = previous_template
    registry.get_engine.cache_clear()
