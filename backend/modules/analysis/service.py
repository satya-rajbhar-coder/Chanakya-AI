import hashlib
import logging
from datetime import UTC, datetime, timedelta
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

# Columns that indicate ward/assembly scope in voter and activity tables.
# Only columns that actually exist in the schema are included:
#   - ward_no exists in dw_voters_info and voter_details_corp
#   - booth_ac_no exists in dw_voters_info (assembly associated with a booth)
#   - ac_no exists in voter_details_corp
# assembly_name_eng / assembly_name_mar do NOT exist in any table and were removed.
_SCOPE_COLUMNS = {
    "ward": ("ward_no",),
    "assembly": ("booth_ac_no", "ac_no"),
}


def _scope_filter_clause(scope: dict, dialect: str) -> str | None:
    """Build a SQL WHERE fragment restricting rows to the user's scope.

    Returns None when no filter applies (e.g. admin). The caller is
    responsible for AND-ing this into the generated SQL.
    """
    ward = scope.get("ward_no")
    assembly = scope.get("assembly_no")
    pc = scope.get("parliamentary_constituency")

    conditions = []
    if ward:
        conditions.append(f"ward_no = '{ward}'")
    if assembly:
        conditions.append(
            " OR ".join(
                f"{col} = '{assembly}'" for col in _SCOPE_COLUMNS["assembly"]
            )
        )
    if pc:
        # Parliamentary constituency is not a column in voter tables;
        # it is enforced at the client/database level instead.
        pass

    if not conditions:
        return None
    return "(" + " OR ".join(conditions) + ")"


def _sql_respects_scope(sql: str, scope_clause: str) -> bool:
    """Check that the generated SQL includes the required scope filter.

    This is a best-effort check: we look for the ward_no or assembly
    columns being referenced in the WHERE clause. The LLM may use
    different column names or table aliases, so we check for the
    presence of the scope column names anywhere in the SQL.
    """
    sql_upper = sql.upper()
    # Check for ward_no reference
    if "WARD_NO" in sql_upper:
        return True
    # Check for booth_ac_no (used as assembly scope in dw_voters_info)
    if "BOOTH_AC_NO" in sql_upper:
        return True
    # Check for ac_no (used as assembly scope in voter_details_corp)
    if "AC_NO" in sql_upper:
        return True
    return False


# Tables most relevant to common political campaign questions. Used to
# prioritize schema context when the database has many tables.
_PRIORITY_TABLES = {
    "dw_voters_info",
    "voter_details_corp",
    "activity_details_corp",
    "activity_details_sir",
    "contact_sync_corp",
    "contact_sync_sir",
    "client_master",
    "executive_master",
    "user_master",
    "karyakarni_master_pollmatrix_new",
    "hitchintak_master_pollmatrix_new",
}

# Question keywords -> likely tables. Used to prune schema context.
_QUESTION_TABLE_KEYWORDS = {
    "voter": {"dw_voters_info", "voter_details_corp"},
    "elector": {"dw_voters_info"},
    "panel": {"dw_voters_info"},
    "worker": {"karyakarni_master_pollmatrix_new", "executive_master"},
    "karyakarta": {"karyakarni_master_pollmatrix_new"},
    "executive": {"executive_master"},
    "activity": {"activity_details_corp", "activity_details_sir"},
    "contact": {"contact_sync_corp", "contact_sync_sir"},
    "phonebook": {"contact_sync_corp", "contact_sync_sir"},
    "client": {"client_master"},
    "user": {"user_master"},
    "hitchintak": {"hitchintak_master_pollmatrix_new"},
}

# Columns always worth showing (small, high-signal). For other tables we
# show all columns but cap the count.
_ESSENTIAL_COLUMNS = {
    "voter_cd", "fullname", "age", "gender", "mobileno", "ward_no", "booth_id",
    "status_type", "ac_no", "idcard_no", "colour_code", "executive_id",
    "full_name", "mobile_no", "client_id", "karyakarni_id", "first_name",
    "activity_detail_id", "visit_datetime", "screen_name", "contact_sync_id",
    "contact_name", "contact_number", "hitchintak_id",
}


def _tables_for_question(question: str, all_tables: list[str]) -> list[str]:
    """Return table names likely relevant to the question, prioritized."""
    q = question.lower()
    matched: set[str] = set()
    for keyword, tables in _QUESTION_TABLE_KEYWORDS.items():
        if keyword in q:
            matched.update(tables)

    # Start with priority tables that exist, then question-matched, then rest.
    ordered: list[str] = []
    for t in all_tables:
        tl = t.lower()
        if tl in _PRIORITY_TABLES and tl in matched:
            ordered.append(t)
    for t in all_tables:
        tl = t.lower()
        if tl in _PRIORITY_TABLES and tl not in matched and t not in ordered:
            ordered.append(t)
    for t in all_tables:
        if t not in ordered:
            ordered.append(t)
    return ordered


def _build_schema_context(
    insp,
    all_tables: list[str],
    max_tables: int = 12,
    max_columns_per_table: int = 14,
    question: str = "",
) -> str:
    """Reflect the real database schema and return a concise, LLM-friendly
    description of tables and their columns.

    Only the most relevant tables are included (based on question keywords
    and priority list), and column lists are capped to keep the prompt small
    enough to fit within the LLM's token limits.
    """
    parts: list[str] = []
    ordered = _tables_for_question(question, all_tables)
    tables_to_show = ordered[:max_tables]
    for table_name in tables_to_show:
        try:
            columns = insp.get_columns(table_name)
        except Exception:
            parts.append(f"TABLE: {table_name}  (columns: unavailable)")
            continue
        col_names = [c["name"] for c in columns]
        if not col_names:
            parts.append(f"TABLE: {table_name}  (columns: none)")
            continue
        # Show essential columns first, then others, capped.
        essential = [c for c in col_names if c in _ESSENTIAL_COLUMNS]
        rest = [c for c in col_names if c not in _ESSENTIAL_COLUMNS]
        selected = essential + rest
        if len(selected) > max_columns_per_table:
            selected = selected[:max_columns_per_table]
            selected.append(f"...+{len(col_names) - max_columns_per_table} more")
        cols_str = ", ".join(selected)
        parts.append(f"TABLE: {table_name}  COLUMNS: {cols_str}")
    if len(all_tables) > max_tables:
        parts.append(f"... and {len(all_tables) - max_tables} more table(s)")
    return "\n".join(parts)


logger = logging.getLogger(__name__)

OUT_OF_SCOPE = "I can only answer questions that can be answered from your databases, and I couldn't build a query for that."

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

    def plan_and_run(
        self,
        question: str,
        user_id: UUID,
        client_id: UUID | None = None,
        user: User | None = None,
        user_scope: dict | None = None,
    ):
        """
        Plan and execute a query against the user's assigned client database.
        The actual database schema is reflected and sent to the LLM so it
        generates SQL against real tables/columns instead of hallucinating.
        A query never spans multiple client databases. Only SELECT statements
        are allowed. Role-based scope (ward/assembly/constituency) is injected
        into the generated SQL so users only see data they are authorized for.
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

        # Reflect the real schema so the LLM doesn't hallucinate columns/tables
        # that don't exist in this client's database. Only relevant tables
        # and a capped column list are sent to keep the prompt small.
        schema = _build_schema_context(
            insp, all_tables, question=question,
        )
        allowed = {table.lower() for table in all_tables}

        # Build scope context for the LLM and for server-side validation.
        scope = user_scope or {}
        if user is not None:
            scope = {
                "ward_no": user.ward_no,
                "assembly_no": user.assembly_no,
                "parliamentary_constituency": user.parliamentary_constituency,
                "role": user.role,
                **scope,
            }

        scope_clause = _scope_filter_clause(scope, dialect)
        scope_context = ""
        if scope_clause:
            scope_context = (
                f"\n\nDATA ACCESS RESTRICTION: You must only return rows where "
                f"{scope_clause}. Every query must include this filter in the "
                f"WHERE clause. Do not return data outside the user's assigned "
                f"ward/assembly/constituency."
            )

        error = None
        sql = None
        title = None
        result = None
        llm_failed = False

        for _ in range(2):
            try:
                plan = generate_sql(
                    question,
                    dialect,
                    schema,
                    client_identifier,
                    None,
                    error,
                    scope_context=scope_context,
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

                # Server-side enforcement: non-admin queries must include the
                # scope filter so users cannot read data outside their ward/assembly.
                if scope_clause and user is not None and user.role != "admin":
                    if not _sql_respects_scope(sql, scope_clause):
                        raise UnsafeSQL(
                            "Query does not respect your data access scope "
                            "(ward/assembly/constituency filter missing)"
                        )

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

            # Persist the failed query for audit/history.
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

            # Instead of raising an error, return a restructured question
            # suggestion that the user can try.
            restructured = self._restructure_question(question, error_msg)
            return {
                "success": False,
                "restructured_question": restructured,
                "error": error_msg,
                "database": database,
                "client_id": client_id,
            }

        return {
            "success": True,
            "database": database,
            "client_id": client_id,
            "tables": list(all_tables),
            "title": title,
            "sql": sql,
            "result": result,
        }

    def _restructure_question(
        self, question: str, error_msg: str
    ) -> str:
        """Return a simpler, more specific rephrasing of the user's question
        that is more likely to produce a working SQL query.

        Uses simple template-based transformations so it never depends on
        another LLM call (which might also fail under rate limits).
        """
        q = question.strip()
        q_lower = q.lower()

        # Common patterns -> simpler rephrasings
        patterns = [
            (r"\bgive me a total\s+(\w+)\s+count\b", r"Total count of \1"),
            (r"\bhow many\s+(\w+)\s+(?:are\s+there\s+)?(?:in\s+)?(?:ward\s+)?(\w+)?\b",
             r"Count of \1" + (f" in ward \2" if r"\2" else "")),
            (r"\bshow\s+me\s+(\w+)\s+(?:in\s+)?(?:ward\s+)?(\w+)?\b",
             r"List of \1" + (f" in ward \2" if r"\2" else "")),
            (r"\blist\s+(\w+)\s+(?:in\s+)?(?:ward\s+)?(\w+)?\b",
             r"List of \1" + (f" in ward \2" if r"\2" else "")),
            (r"\bvoters?\s+(?:in\s+)?(?:ward\s+)?(\w+)?\b",
             r"Voters" + (f" in ward \1" if r"\1" else "")),
            (r"\bcount\s+(\w+)\b", r"Count of \1"),
        ]

        import re as _re
        for pattern, replacement in patterns:
            m = _re.search(pattern, q_lower)
            if m:
                try:
                    return replacement.format(*m.groups())
                except (IndexError, KeyError):
                    pass

        # Fallback: suggest a simpler phrasing
        if "count" in q_lower:
            return "What is the total count of voters?"
        if "list" in q_lower or "show" in q_lower:
            return "Show me a list of voters in my ward."
        if "voter" in q_lower:
            return "Show me voter details for my ward."

        return "Please try rephrasing your question with more specific details (e.g., ward number, booth, or voter category)."

    def ask(self, data, user_id: UUID, user: User | None = None):
        planned = self.plan_and_run(
            data.question,
            user_id,
            client_id=data.client_id,
            user=user,
        )

        if not planned.get("success", True):
            # Database query failed: return the restructured question suggestion
            # instead of raising an error.
            return {
                "success": False,
                "restructured_question": planned["restructured_question"],
                "error": planned.get("error", ""),
                "database": planned.get("database", ""),
                "client_id": planned.get("client_id"),
            }

        database = planned["database"]
        client_id = planned["client_id"]
        tables = planned["tables"]
        title = planned["title"]
        sql = planned["sql"]
        result = planned["result"]

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
            "success": True,
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
