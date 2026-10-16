import re
from functools import lru_cache

from sqlalchemy import Engine, create_engine

from core.config import settings

_DIALECTS = {"postgresql": "postgres", "mssql": "tsql"}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def main_schema() -> str:
    """Schema inside each client DB that exposes the main DB tables (FDW)."""
    return settings.ANALYSIS_MAIN_DB_SCHEMA


@lru_cache(maxsize=None)
def get_engine(name: str) -> Engine:
    if not _IDENTIFIER.fullmatch(name):
        raise KeyError(f"Invalid database name: {name}")
    template = settings.ANALYSIS_DB_URL_TEMPLATE
    if "{name}" not in template:
        raise KeyError("ANALYSIS_DB_URL_TEMPLATE must contain the {name} placeholder")
    kwargs = (
        {} if template.startswith("sqlite") else {"pool_size": 3, "max_overflow": 2}
    )
    return create_engine(template.format(name=name), pool_pre_ping=True, **kwargs)


def sqlglot_dialect(engine: Engine) -> str:
    return _DIALECTS.get(engine.dialect.name, engine.dialect.name)


def get_all_database_names() -> list[str]:
    from database.session import SessionLocal
    from modules.analysis.models import Client
    from sqlalchemy import select

    with SessionLocal() as session:
        names = session.scalars(
            select(Client.database_name)
            .where(Client.database_name.isnot(None), Client.is_active == True)
        ).all()
    return [str(n) for n in names if n]