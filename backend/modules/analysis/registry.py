import re
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text

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
    """Get all database names from the PostgreSQL server using the analysis DB URL template.
    
    This connects to the PostgreSQL server (using the template with a default database)
    and queries for all available databases, excluding system databases.
    """
    template = settings.ANALYSIS_DB_URL_TEMPLATE
    if "{name}" not in template:
        raise KeyError("ANALYSIS_DB_URL_TEMPLATE must contain the {name} placeholder")
    
    # Create a connection URL to the default 'postgres' database to list all databases
    # Replace {name} with 'postgres' to connect to the default database
    default_db_url = template.format(name="postgres")
    
    try:
        engine = create_engine(default_db_url, pool_pre_ping=True)
        with engine.connect() as conn:
            # Query all databases from PostgreSQL - exclude system databases
            result = conn.execute(text("""
                SELECT datname 
                FROM pg_database 
                WHERE datistemplate = false 
                AND datname NOT IN ('postgres', 'template0', 'template1', 'rdsadmin')
                ORDER BY datname
            """))
            db_names = [row[0] for row in result.fetchall()]
        return db_names
    except Exception as e:
        # Fallback: if we can't connect to the server, return databases from clients table
        from sqlalchemy import select
        from database.session import SessionLocal
        from modules.analysis.models import Client
        
        with SessionLocal() as session:
            names = session.scalars(
                select(Client.database_name)
                .where(Client.database_name.isnot(None), Client.is_active == True)
            ).all()
        return [str(n) for n in names if n]