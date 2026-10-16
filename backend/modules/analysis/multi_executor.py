"""
Multi-database query executor for joining results across multiple PostgreSQL databases.
"""
import csv
import io
import logging
from collections.abc import Iterator
from time import perf_counter
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Connection, text

from core.config import settings
from .registry import get_engine

logger = logging.getLogger(__name__)


def _prepare(conn: Connection, timeout_ms: int) -> None:
    """Read-only transaction + statement timeout where the database supports it."""
    dialect = conn.dialect.name
    if dialect == "postgresql":
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_ms)}"))


def _stmt(sql: str, suffix: str = "") -> text:
    return text(f"SELECT * FROM ({sql}) AS q {suffix}".replace(":", "\\:"))


def run_page_multi(
    databases: list[str],
    sql: str,
    page: int,
    page_size: int,
    join_key: str | None = None,
    join_type: str = "outer",
) -> dict[str, Any]:
    """
    Run the same query across multiple databases and optionally merge results.
    
    Args:
        databases: List of database names to query
        sql: SQL query to execute on each database
        page: Page number
        page_size: Page size
        join_key: Column name to join results on (optional)
        join_type: Type of join (inner, left, right, outer)
    
    Returns:
        Dictionary with per-database results and merged result
    """
    page = max(page, 0)
    page_size = min(max(page_size, 1), settings.ANALYSIS_MAX_PAGE_SIZE)
    offset = page * page_size

    per_db_results = {}
    all_rows_by_db = {}
    columns_by_db: dict[str, list[str]] = {}

    # Execute query on each database
    for db_name in databases:
        engine = get_engine(db_name)
        try:
            with engine.connect() as conn:
                _prepare(conn, settings.ANALYSIS_TIMEOUT_MS)
                
                if engine.dialect.name == "mssql":
                    statement = text(sql.replace(":", "\\:"))
                else:
                    statement = _stmt(sql, f"LIMIT {page_size + 1} OFFSET {offset}")

                started = perf_counter()
                result = conn.execute(statement)
                
                if engine.dialect.name == "mssql":
                    if offset:
                        result.fetchmany(offset)
                    skipped = result.fetchmany(page_size + 1)
                    rows = [tuple(row) for row in skipped]
                else:
                    rows = [tuple(row) for row in result.fetchall()]
                
                total_time_ms = (perf_counter() - started) * 1000
                columns = list(result.keys())
                
                all_rows_by_db[db_name] = rows
                columns_by_db[db_name] = columns
                per_db_results[db_name] = {
                    "columns": columns,
                    "rows": jsonable_encoder(rows[:page_size]),
                    "page": page,
                    "page_size": page_size,
                    "has_more": len(rows) > page_size,
                    "total_time_ms": total_time_ms,
                }
        except Exception as e:
            # Table might not exist in this database, record error and continue
            logger.warning("Query failed on database %s: %s", db_name, e)
            per_db_results[db_name] = {
                "columns": [],
                "rows": [],
                "page": page,
                "page_size": page_size,
                "has_more": False,
                "total_time_ms": 0,
                "error": str(e),
            }
            all_rows_by_db[db_name] = []
            columns_by_db[db_name] = []

    merged_result = None
    if join_key and len(databases) > 1:
        merged_result = _merge_results(
            all_rows_by_db, columns_by_db, databases, page, page_size
        )

    return {
        "databases": per_db_results,
        "merged_result": merged_result,
        "join_key": join_key,
        "join_type": join_type,
    }


def _merge_results(
    all_rows_by_db: dict[str, list[tuple]],
    columns_by_db: dict[str, list[str]],
    databases: list[str],
    page: int,
    page_size: int,
) -> dict[str, Any] | None:
    """Concatenate per-database rows with a leading source_database column."""
    if not all_rows_by_db:
        return None

    base_columns: list[str] = []
    for db_name in databases:
        if columns_by_db.get(db_name):
            base_columns = columns_by_db[db_name]
            break
    if not base_columns:
        return None

    all_rows = []
    for db_name, rows in all_rows_by_db.items():
        for row in rows:
            all_rows.append((db_name,) + tuple(row))
    
    # Add source_database to columns
    merged_columns = ["source_database"] + list(base_columns)

    # Apply pagination
    offset = page * page_size
    paginated_rows = all_rows[offset:offset + page_size]
    has_more = len(all_rows) > offset + page_size

    return {
        "columns": merged_columns,
        "rows": jsonable_encoder(paginated_rows),
        "page": page,
        "page_size": page_size,
        "has_more": has_more,
        "total_time_ms": 0,
    }


def stream_csv_multi(databases: list[str], sql: str) -> Iterator[str]:
    """
    Stream CSV results from multiple databases.
    Adds a 'source_database' column.
    """
    first = True
    buf = io.StringIO()
    writer = csv.writer(buf)
    
    for db_name in databases:
        engine = get_engine(db_name)
        with engine.connect() as conn:
            _prepare(conn, settings.ANALYSIS_EXPORT_TIMEOUT_MS)
            conn = conn.execution_options(stream_results=True, max_row_buffer=1000)
            result = conn.execute(_stmt(sql))
            
            columns = list(result.keys())
            if first:
                writer.writerow(["source_database"] + columns)
                yield buf.getvalue()
                buf.seek(0)
                buf.truncate()
                first = False
            
            for chunk in result.partitions(1000):
                buf.seek(0)
                buf.truncate()
                for row in chunk:
                    writer.writerow([db_name] + list(row))
                yield buf.getvalue()
                
                # Check export limit
                # Note: This doesn't perfectly track global count across databases
      