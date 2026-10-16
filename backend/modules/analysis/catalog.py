"""Database-scoped schema catalog. Built automatically when an admin creates a
client; every table NAME is indexed (cheap), but the prompt stays bounded:
only the top-k relevant tables with at most ANALYSIS_MAX_COLUMNS columns each.
"""

import json
import logging
import re
from functools import lru_cache
from uuid import NAMESPACE_URL, uuid5

from langchain_core.documents import Document
from langchain_postgres import Column
from langchain_postgres.v2.vectorstores import PGVectorStore
from sqlalchemy import inspect, text

from core.config import settings
from database.session import engine
from rag.embeddings import get_google_embeddings
from rag.vector_store import get_pg_engine

from .registry import get_engine

logger = logging.getLogger(__name__)
_store: PGVectorStore | None = None
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_db_name(db: str) -> str:
    if not _IDENTIFIER.fullmatch(db):
        raise LookupError(f"Invalid database name: {db}")
    return db


def get_schema_store() -> PGVectorStore:
    global _store
    if _store is None:
        _store = PGVectorStore.create_sync(
            engine=get_pg_engine(),
            table_name=settings.ANALYSIS_SCHEMA_TABLE,
            embedding_service=get_google_embeddings(),
            metadata_columns=["db", "table_name"],
        )
    return _store


def build_catalog(db: str) -> int:
    """Index every table NAME of one client database plus the shared main
    database tables (exposed through the pollmatrix foreign schema). Column
    reflection stays lazy, so the prompt size never grows with the number of
    tables or columns."""
    global _store
    _validate_db_name(db)
    table = settings.ANALYSIS_SCHEMA_TABLE
    if not _IDENTIFIER.fullmatch(table):
        raise ValueError("Invalid catalog table name")
    notes_path = settings.ANALYSIS_NOTES_FILE
    try:
        notes = json.loads(notes_path.read_text("utf-8")) if notes_path.exists() else {}
    except (OSError, ValueError):
        logger.warning("Ignoring unreadable schema notes file: %s", notes_path)
        notes = {}

    from .registry import main_schema

    schema = main_schema()
    source = inspect(get_engine(db))
    names = sorted(source.get_table_names())
    # Shared main-DB tables are reachable through the client connection as
    # <main_schema>.<table>; index them with their qualified name.
    main_names = sorted(source.get_table_names(schema=schema))
    qualified = [f"{schema}.{n}" for n in main_names]
    all_names = names + qualified
    if not all_names:
        raise LookupError(f"Database {db} has no tables")

    if not inspect(engine).has_table(table):
        try:
            get_pg_engine().init_vectorstore_table(
                table_name=table,
                vector_size=settings.VECTOR_DIMENSION,
                metadata_columns=[Column("db", "TEXT"), Column("table_name", "TEXT")],
            )
        except Exception as exc:
            if "already exists" not in str(exc):
                raise
            logger.info("Schema catalog table already exists: %s", table)
    _store = None
    store = get_schema_store()

    docs: list[Document] = []
    ids: list[str] = []
    for table_name in all_names:
        note = notes.get(f"{db}.{table_name}", "")
        docs.append(
            Document(
                page_content=f"Table {table_name}. {note}",
                metadata={"db": db, "table_name": table_name},
            )
        )
        ids.append(str(uuid5(NAMESPACE_URL, f"{db}.{table_name}")))

    with engine.begin() as conn:
        conn.execute(text(f'DELETE FROM "{table}" WHERE db = :db'), {"db": db})
    for i in range(0, len(docs), 32):
        store.add_documents(docs[i : i + 32], ids=ids[i : i + 32])

    logger.info("Indexed %s tables for %s", len(docs), db)
    describe_table.cache_clear()
    return len(docs)


@lru_cache(maxsize=512)
def describe_table(
    db: str, table: str, question: str = ""
) -> tuple[str, tuple[str, ...]]:
    """Lazy bounded schema: keys and question-related columns take priority.

    `table` may be schema-qualified (`pollmatrix.some_table`) for shared
    main-database tables, which are read through the client connection.
    """
    _validate_db_name(db)
    insp = inspect(get_engine(db))

    from .registry import main_schema

    schema = None
    if "." in table:
        prefix, table = table.split(".", 1)
        if prefix.lower() != main_schema().lower():
            raise LookupError("Table is not available")
        schema = prefix

    if not insp.has_table(table, schema=schema):
        raise LookupError("Table is not available")
    pk = set(
        (insp.get_pk_constraint(table, schema=schema) or {}).get(
            "constrained_columns"
        )
        or []
    )
    fks = insp.get_foreign_keys(table, schema=schema) or []
    fk_map = {
        c: f"{fk['referred_table']}.{rc}"
        for fk in fks
        for c, rc in zip(fk["constrained_columns"], fk["referred_columns"])
    }
    words = set(re.findall(r"[a-z0-9]+", question.lower()))
    columns = insp.get_columns(table, schema=schema)

    def rank(col):
        name = col["name"]
        parts = set(name.lower().split("_"))
        return (name in pk or name in fk_map, len(words & parts), name.lower() in words)

    columns = sorted(columns, key=rank, reverse=True)
    if settings.ANALYSIS_MAX_COLUMNS > 0:
        columns = columns[: settings.ANALYSIS_MAX_COLUMNS]
    cols = []
    for c in columns:
        name = c["name"]
        part = f"{name} {str(c['type']).split('(')[0].lower()}"
        if name in pk:
            part += " PK"
        if name in fk_map:
            part += f" FK->{fk_map[name]}"
        cols.append(part)
    related = tuple(
        sorted({fk["referred_table"] for fk in fks} & set(insp.get_table_names()))
    )
    qualified = f"{schema}.{table}" if schema else table
    return f"{qualified}({', '.join(cols)})", related


def select_tables(question: str, db: str) -> tuple[str, list[str]]:
    _validate_db_name(db)
    hits = get_schema_store().similarity_search_with_score(
        question, k=settings.ANALYSIS_TOP_TABLES, filter={"db": db}
    )
    tables = list(
        dict.fromkeys(
            d.metadata["table_name"] for d, _ in hits if d.metadata.get("db") == db
        )
    )
    if not tables:
        raise LookupError(
            f"No indexed tables for {db}. Re-create the client or run: "
            "python -m modules.analysis.catalog"
        )
    for table in list(tables):
        for related in describe_table(db, table)[1]:
            if related not in tables and len(tables) < 5:
                tables.append(related)
    return db, tables


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m modules.analysis.catalog <database_name>")
    count = build_catalog(sys.argv[1])
    logger.info("Indexed %s tables", count)
