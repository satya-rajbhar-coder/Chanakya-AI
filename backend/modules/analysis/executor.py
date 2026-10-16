import csv
import io
from collections.abc import Iterator
from time import perf_counter

from fastapi.encoders import jsonable_encoder
from sqlalchemy import Connection, text

from core.config import settings

from .registry import get_engine


def _prepare(conn: Connection, timeout_ms: int) -> None:
    """Read-only transaction + statement timeout where the database supports it."""
    dialect = conn.dialect.name
    if dialect == "postgresql":
        conn.execute(text("SET TRANSACTION READ ONLY"))
        conn.execute(text(f"SET LOCAL statement_timeout = {int(timeout_ms)}"))
    # SQL Server has no plain read-only transaction: the configured analysis
    # login MUST be restricted in the database itself.


def _stmt(sql: str, suffix: str = ""):
    return text(f"SELECT * FROM ({sql}) AS q {suffix}".replace(":", "\\:"))


def run_page(db: str, sql: str, page: int, page_size: int) -> dict:
    page = max(page, 0)
    page_size = min(max(page_size, 1), settings.ANALYSIS_MAX_PAGE_SIZE)
    offset = page * page_size

    engine = get_engine(db)
    with engine.connect() as conn:
        _prepare(conn, settings.ANALYSIS_TIMEOUT_MS)
        if engine.dialect.name == "mssql":
            statement = text(sql.replace(":", "\\:"))
        else:
            statement = _stmt(sql, f"LIMIT {page_size + 1} OFFSET {offset}")

        started = perf_counter()
        result = conn.execute(statement)
        if engine.dialect.name == "mssql":
            # SQL Server needs ORDER BY for OFFSET/FETCH, which generated SQL does
            # not reliably contain. Buffer only one page after skipping requested rows.
            if offset:
                result.fetchmany(offset)
            skipped = result.fetchmany(page_size + 1)
            rows = [tuple(row) for row in skipped]
        else:
            rows = [tuple(row) for row in result.fetchall()]
        total_time_ms = (perf_counter() - started) * 1000
        columns = list(result.keys())

    return {
        "columns": columns,
        "rows": jsonable_encoder(rows[:page_size]),
        "page": page,
        "page_size": page_size,
        "has_more": len(rows) > page_size,
        "total_time_ms": total_time_ms,
    }


def stream_csv(db: str, sql: str) -> Iterator[str]:
    with get_engine(db).connect() as conn:
        _prepare(conn, settings.ANALYSIS_EXPORT_TIMEOUT_MS)
        conn = conn.execution_options(stream_results=True, max_row_buffer=1000)
        result = conn.execute(_stmt(sql))

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(result.keys())
        yield buf.getvalue()

        sent = 0
        for chunk in result.partitions(1000):
            buf.seek(0)
            buf.truncate()
            writer.writerows(chunk)
            yield buf.getvalue()
            sent += len(chunk)
            if sent >= settings.ANALYSIS_EXPORT_MAX_ROWS:
                break
