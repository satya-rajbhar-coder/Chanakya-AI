import hashlib
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from modules.users.models import User

from .executor import run_page, stream_all
from .generator import SHARED_TABLES, generate_sql
from .guard import UnsafeSQL, validate_select
from .registry import get_engine, sqlglot_dialect
from .repository import AnalysisRepository

logger = logging.getLogger(__name__)


_log_dir = Path("storage/logs")
_log_dir.mkdir(parents=True, exist_ok=True)
_log_file = _log_dir / "analysis_queries.log"

_file_handler = logging.FileHandler(_log_file, encoding="utf-8")
_file_handler.setLevel(logging.INFO)
_file_handler.setFormatter(
    logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
)
logger.addHandler(_file_handler)
logger.setLevel(logging.INFO)

OUT_OF_SCOPE = "I can only answer questions that can be answered from your databases, and I couldn't build a query for that."


class AnalysisService:
    """Business logic for analysis queries and history."""

    def __init__(self, db: Session):
        self.repo = AnalysisRepository(db)

    def assigned_database(
        self, user_id: UUID, client_id: UUID | None
    ) -> tuple[str, UUID, str]:
        """Get database name, client UUID, and client_identifier for a user's assigned client.

        Returns (database_name, client_uuid, client_identifier).
        client_identifier is the string (e.g. 'client147') used in SQL WHERE clauses.
        """

        if client_id is None:
            assigned = self.repo.get_assigned_client_ids(user_id)

            if len(assigned) == 1:
                client_id = assigned[0]
            elif not assigned:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, "You are not assigned to any client"
                )
            else:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, "Select a client for this question"
                )

        user = self.repo.db.get(User, user_id)

        if user is not None and user.role == "admin":
            name = self.repo.get_client_database_name(client_id)
            identifier = self.repo.get_client_identifier(client_id)
        else:
            name = self.repo.get_client_database_name_for_user(
                client_id, user_id, False
            )
            identifier = self.repo.get_client_identifier(client_id)

        if name is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Client is not assigned or its database is unavailable",
            )

        return name, client_id, identifier

    def plan_and_run(self, question: str, user_id: UUID, client_id: UUID | None = None):
        """
        Plan and execute a query against the user's assigned client database.
        Table schemas come from the system prompt (hardcoded). A query never
        spans multiple client databases. Only SELECT statements are allowed.
        """
        database, client_id, client_identifier = self.assigned_database(
            user_id, client_id
        )

        engine = get_engine(database)
        insp = inspect(engine)
        all_tables = insp.get_table_names()
        if not all_tables:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                f"No tables found for database {database}",
            )

        dialect = sqlglot_dialect(engine)

        schema = ""
        allowed = {table.lower() for table in all_tables}

        error = None
        sql = None
        title = None
        result = None
        llm_failed = False

        for _ in range(2):
            try:
                plan = generate_sql(
                    question, dialect, schema, client_identifier, None, error
                )
            except Exception as exc:
                # The LLM API call itself failed (network, rate limit, ...).
                # Feed it back so the loop can retry once instead of crashing.
                logger.warning("SQL generation call failed: %s", exc)
                error = "The AI service is currently unavailable. Please try again."
                sql = None
                llm_failed = True
                continue
            llm_failed = False

            if not plan.get("sql"):
                error = plan.get("reason") or (
                    "No SQL was produced. If the question can be answered "
                    "from the tables above, return the SQL; otherwise "
                    "return sql = null again."
                )
                continue

            try:
                sql = self._validate_guarded(plan["sql"], dialect, allowed)
                title = plan.get("title") or question[:80]

                result = run_page(database, sql, 0, settings.ANALYSIS_PAGE_SIZE)
                logger.info(
                    "Query generated successfully | user=%s | db=%s | question=%r | sql=%s",
                    user_id,
                    database,
                    question,
                    sql,
                )
                break

            except UnsafeSQL as exc:
                error = str(exc)
                sql = None

            except SQLAlchemyError as exc:
                error = str(getattr(exc, "orig", exc)).splitlines()[0]
                sql = None

            except Exception as exc:
                # Any other execution failure (timeouts, driver errors, ...)
                # should be retried/handled, not bubble up as a 500.
                logger.warning("Query execution failed: %s", exc)
                error = str(exc).splitlines()[0]
                sql = None

        if sql is None or result is None:
            error_msg = error or OUT_OF_SCOPE
            logger.warning(
                "Could not produce a working query for %r: %s", question, error_msg
            )

            try:
                self.repo.create_analysis_query(
                    user_id=user_id,
                    client_id=client_id,
                    database_name=database,
                    question=question,
                    title=question[:80],
                    sql="",
                    status="FAILED",
                    row_count=None,
                    page_number=None,
                    page_size=None,
                    total_time_ms=None,
                    query_hash=None,
                )
            except Exception as exc:
                logger.error("Failed to persist failed query: %s", exc)

            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY
                if llm_failed
                else status.HTTP_422_UNPROCESSABLE_CONTENT,
                error_msg,
            )

        return database, client_id, list(all_tables), title, sql, result

    def ask(self, data, user_id: UUID):
        database, client_id, tables, title, sql, result = self.plan_and_run(
            data.question, user_id, client_id=data.client_id
        )

        query = self.repo.create_analysis_query(
            user_id=user_id,
            client_id=client_id,
            database_name=database,
            question=data.question,
            title=title,
            sql=sql,
            status="SUCCESS",
            row_count=len(result["rows"]),
            page_number=result["page"],
            page_size=result["page_size"],
            total_time_ms=result.get("total_time_ms"),
            query_hash=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        )

        return {
            "title": title,
            "database": database,
            "tables": tables,
            "sql": sql,
            "analysis_query_id": query.id,
            "token": self.sign_result(user_id, database, sql, client_id),
            "result": result,
        }

    @staticmethod
    def sign_result(
        user_id: UUID, database: str, sql: str, client_id: UUID | None
    ) -> str:

        payload = {
            "type": "analysis",
            "sub": str(user_id),
            "db": database,
            "client_id": str(client_id) if client_id else "",
            "sql": sql,
            "exp": datetime.now(UTC)
            + timedelta(minutes=settings.ANALYSIS_TOKEN_MINUTES),
        }

        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    def open_result(self, token: str, user_id: UUID) -> tuple[str, str, UUID | None]:

        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            client_id_str = payload.get("client_id", "")
            client_id = UUID(client_id_str) if client_id_str else None
            database, sql = payload["db"], payload["sql"]
        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Result expired, please ask again"
            )

        if payload.get("type") != "analysis" or payload.get("sub") != str(user_id):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid result token")

        if client_id is not None:
            assigned_db, _, _ = self.assigned_database(user_id, client_id)

            if assigned_db != database:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, "Database assignment has changed"
                )

        return database, sql, client_id

    def export_rows(self, data, user_id: UUID):
        database, sql, client_id = self.open_result(data.token, user_id)
        # Verify the user is assigned to the client for this result.
        if client_id is not None:
            assigned = self.repo.get_assigned_client_ids(user_id)
            if client_id not in assigned:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "You are not assigned to this client's data",
                )
        return stream_all(database, sql)

    def list_history(self, user_id: UUID, client_id: UUID | None = None):
        rows = self.repo.list_analysis_queries(user_id, client_id)
        return [
            {
                "id": row.id,
                "question": row.question,
                "title": row.title,
                "database": row.database_name,
                "sql": row.sql,
                "client_id": row.client_id,
                "row_count": row.row_count,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def delete_history(self, query_id: UUID, user_id: UUID) -> None:
        self.repo.delete_analysis_query(query_id, user_id)

    def run_history(
        self,
        query_id: UUID,
        user_id: UUID,
        page: int = 0,
        page_size: int | None = None,
    ):
        """Re-execute a stored query using its saved SQL (no regeneration)."""
        row = self.repo.get_analysis_query(query_id, user_id)
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found")

        database, _, _ = self.assigned_database(user_id, row.client_id)
        if database != row.database_name:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "Database assignment has changed"
            )
        sql = row.sql

        # Validate the stored SQL is safe before re-executing.
        engine = get_engine(database)
        dialect = sqlglot_dialect(engine)
        insp = inspect(engine)
        allowed = {t.lower() for t in insp.get_table_names()}
        try:
            sql = self._validate_guarded(sql, dialect, allowed)
        except UnsafeSQL as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                f"Stored query is not safe to run: {exc}",
            )

        try:
            result = run_page(
                database,
                sql,
                page,
                page_size or settings.ANALYSIS_PAGE_SIZE,
            )
        except SQLAlchemyError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                str(getattr(exc, "orig", exc)).splitlines()[0],
            )

        return {
            "title": row.title or row.question[:80],
            "database": database,
            "tables": [],
            "sql": sql,
            "analysis_query_id": row.id,
            "token": self.sign_result(user_id, database, sql, row.client_id),
            "result": result,
        }

    @staticmethod
    def _validate_guarded(sql: str, dialect: str, allowed: set[str]) -> str:
        known = set(allowed)
        resolve: dict[str, str] = {}
        for shared in SHARED_TABLES:
            bare = shared.rpartition(".")[2].lower()
            known.add(bare)
            resolve[bare] = shared
        return validate_select(sql, dialect, allowed, known, resolve)
