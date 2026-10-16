import hashlib
import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from core.config import settings
from modules.users.models import User

from .catalog import describe_table, select_tables
from .global_catalog import (
    build_global_catalog,
    classify_table_type,
    discover_logical_tables,
    find_tables_across_databases,
    list_main_tables,
    list_tables,
    logical_table_name,
    physical_scope,
    select_tables_global,
)
from .executor import run_page, stream_csv
from .generator import SHARED_TABLES, generate_sql
from .guard import UnsafeSQL, validate_select
from .models import AnalysisQuery, Client, SavedAnalysis, UserClient
from .multi_executor import run_page_multi, stream_csv_multi
from .registry import get_engine, main_schema, sqlglot_dialect

logger = logging.getLogger(__name__)

OUT_OF_SCOPE = "I can only answer questions that can be answered from your databases, and I couldn't build a query for that."


def _rank_main_tables(
    question: str, main_tables: list[str], limit: int = 4
) -> list[str]:
    """Keyword-rank shared main-database tables against the question."""
    q = question.lower()
    words = set(re.findall(r"[a-z0-9]+", q))
    scored: list[tuple[float, str]] = []

    for name in main_tables:
        bare = name.split(".")[-1].lower()
        parts = set(re.findall(r"[a-z0-9]+", bare))
        score = 0.0
        if bare in q:
            score += 10.0
        score += 3.0 * len(parts & words)
        for word in words:
            if len(word) >= 4 and (word in bare or bare in word):
                score += 2.0
        if score > 0:
            scored.append((score, name))

    scored.sort(reverse=True)
    return [name for _, name in scored[:limit]]


class AnalysisService:

    @staticmethod
    def _guard_scope(databases: list[str]) -> tuple[set[str], dict[str, str]]:
        """Scope for the SQL guard: reflected client tables + shared tables.

        Shared main-DB tables come from live FDW reflection first, then fall
        back to the tables documented in the system prompt (SHARED_TABLES), so
        a model question is never rejected just because FDW reflection was
        unavailable at that moment.
        """
        known, resolve = physical_scope(databases)
        # Documented shared main-DB tables (executive_master, client_master, ...)
        # are reachable through every client connection as bare names and resolve
        # directly through the connection. Accept them as-is and NEVER rewrite
        # them to a qualified <main_schema>.<table> form — that qualified
        # relation does not exist on client connections and breaks queries.
        known.update(SHARED_TABLES)
        return known, resolve

    @staticmethod
    def _validate_guarded(
        sql: str, dialect: str, allowed: set[str], databases: list[str]
    ) -> str:
        """Guard-check model SQL against real database tables.

        The prompt only shows the top-k tables, but the model may correctly
        reach for another real table (or a logical base name). Scope is
        therefore checked against live reflection, not just the prompt set.
        On a "not available" rejection the reflection cache is cleared and
        checked once more, so tables created after the last catalog build
        are not wrongly rejected.
        """
        known, resolve = AnalysisService._guard_scope(databases)
        try:
            return validate_select(sql, dialect, allowed, known, resolve)
        except UnsafeSQL as exc:
            if not str(exc).startswith("Table not available"):
                raise
            list_tables.cache_clear()
            list_main_tables.cache_clear()
            known, resolve = AnalysisService._guard_scope(databases)
            return validate_select(sql, dialect, allowed, known, resolve)

    @staticmethod
    def assigned_database(
        db_session: Session, user_id: UUID, client_id: UUID | None
    ) -> tuple[str, UUID]:
        """Get database name and client_id for a user's assigned client."""

        if client_id is None:
            assigned = list(
                db_session.scalars(
                    select(UserClient.client_id).where(UserClient.user_id == user_id)
                ).all()
            )

            if len(assigned) == 1:
                client_id = assigned[0]
            elif not assigned:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "You are not assigned to any client",
                )
            else:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "Select a client for this question",
                )

        user = db_session.get(User, user_id)

        if user is not None and user.role == "admin":
            name = db_session.scalar(
                select(Client.database_name).where(Client.id == client_id)
            )
        else:
            name = db_session.scalar(
                select(Client.database_name)
                .join(
                    UserClient,
                    UserClient.client_id == Client.id,
                )
                .where(
                    UserClient.user_id == user_id,
                    Client.id == client_id,
                )
            )

        if name is None:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Client is not assigned or its database is unavailable",
            )

        return name, client_id

    @staticmethod
    def assigned_databases(
        db_session: Session, user_id: UUID, client_ids: list[UUID] | None
    ) -> list[tuple[str, UUID]]:
        """
        Get database names for multiple client IDs.
        Returns list of (database_name, client_id) tuples.
        """
        if not client_ids:
            # Get all assigned clients for the user
            assigned = list(
                db_session.scalars(
                    select(UserClient.client_id).where(UserClient.user_id == user_id)
                ).all()
            )
            if not assigned:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "You are not assigned to any client",
                )
            client_ids = assigned

        results = []
        user = db_session.get(User, user_id)
        is_admin = user is not None and user.role == "admin"
        for cid in client_ids:
            if is_admin:
                name = db_session.scalar(
                    select(Client.database_name).where(Client.id == cid)
                )
            else:
                name = db_session.scalar(
                    select(Client.database_name)
                    .join(
                        UserClient,
                        UserClient.client_id == Client.id,
                    )
                    .where(
                        UserClient.user_id == user_id,
                        Client.id == cid,
                    )
                )
            if name is None:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    f"Client {cid} is not assigned or its database is unavailable",
                )
            results.append((name, cid))

        return results

    @staticmethod
    def build_global_catalog() -> int:
        """Build global catalog across all databases."""
        return build_global_catalog()

    @staticmethod
    def find_tables_global(
        question: str,
        table_type_filter: str | None = None,
        client_ids: list[UUID] | None = None,
        k: int = 10,
    ) -> list[dict]:
        """Find relevant tables across all databases for a question, optionally filtered by clients."""
        return find_tables_across_databases(
            question,
            k=k,
            table_type_filter=table_type_filter,
        )

    @staticmethod
    def plan_and_run_global(
        question: str,
        user_id: UUID,
        db_session: Session,
        table_type_filter: str | None = None,
        client_ids: list[UUID] | None = None,
    ):
        """
        Plan and execute a database-independent query across all relevant databases.
        Handles different table names across databases by building UNION ALL queries
        with exact table names per database.
        """
        # Get databases for the specified clients or all assigned clients
        if client_ids:
            db_assignments = AnalysisService.assigned_databases(
                db_session, user_id, client_ids
            )
        else:
            # Get all assigned clients
            assigned_clients = list(
                db_session.scalars(
                    select(UserClient.client_id).where(UserClient.user_id == user_id)
                ).all()
            )
            if not assigned_clients:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "You are not assigned to any client",
                )
            db_assignments = AnalysisService.assigned_databases(
                db_session, user_id, assigned_clients
            )

        databases = [db for db, _ in db_assignments]
        client_ids_result = [cid for _, cid in db_assignments]

        # Find tables across all databases
        tables = select_tables_global(
            question, table_type_filter=table_type_filter, databases=databases
        )

        if not tables:
            # Try to auto-build global catalog if it doesn't exist
            try:
                logger.info("Global catalog empty, attempting auto-build...")
                build_global_catalog()
                tables = select_tables_global(
                    question, table_type_filter=table_type_filter, databases=databases
                )
            except Exception as e:
                logger.warning("Auto-build failed: %s", e)

        # Shared main-DB tables, reachable THROUGH the first client
        # connection (pollmatrix foreign schema). These are identical for every
        # client and must be queried once, never per-database.
        main_tables = _rank_main_tables(
            question, list(list_main_tables(databases[0]) or [])
        )

        if not tables and not main_tables:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "No relevant tables found across databases. "
                "Please run: POST /analysis/catalog/global/build (admin only) "
                "to build the global schema catalog first.",
            )

        # Group tables by database and table type
        db_tables = {}
        for db, table in tables:
            if db not in db_tables:
                db_tables[db] = {}
            table_type = classify_table_type(table)
            if table_type not in db_tables[db]:
                db_tables[db][table_type] = []
            db_tables[db][table_type].append(table)

        # Use first database for schema planning
        first_db = databases[0]
        first_table_types = db_tables.get(first_db, {})

        # Get all table names from first database
        first_tables = []
        for t_list in first_table_types.values():
            first_tables.extend(t_list)

        dialect = sqlglot_dialect(get_engine(first_db))

        # Build schema with table availability info across databases
        schema_parts = []
        for table in first_tables:
            table_schema, _ = describe_table(first_db, table, question)
            # Add info about which databases have this table type
            table_type = None
            for db, table_types in db_tables.items():
                for ttype, tlist in table_types.items():
                    if table in tlist:
                        table_type = ttype
                        break
                if table_type:
                    break

            # Get databases that have this table type
            dbs_with_type = []
            for db, table_types in db_tables.items():
                if (
                    table_type
                    and table_type in table_types
                    and table in table_types[table_type]
                ):
                    dbs_with_type.append(db)

            if dbs_with_type:
                table_schema += (
                    f"  -- Available in databases: {', '.join(dbs_with_type)}"
                )

            schema_parts.append(table_schema)

        # Shared main-DB tables: described once through the client connection.
        for main_table in main_tables:
            try:
                table_schema, _ = describe_table(first_db, main_table, question)
            except Exception as exc:
                logger.warning("Cannot describe main table %s: %s", main_table, exc)
                continue
            schema_parts.append(
                table_schema + "  -- Shared pollmatrix database (common to all clients)"
            )

        schema = "\n".join(schema_parts)
        allowed = {table.lower() for table in first_tables}

        # Add tables from other databases to allowed set
        for db, table_types in db_tables.items():
            if db != first_db:
                for t_list in table_types.values():
                    for t in t_list:
                        allowed.add(t.lower())

        # Shared main-DB tables are NOT added to `allowed` as bare names: a
        # bare reference would pass the guard but fail at execution. The guard
        # instead rewrites shared names to their qualified FDW form via the
        # resolve mapping from physical_scope().

        error = None
        sql = None
        title = None
        result = None
        tables_used = None
        final_sql = None

        for _ in range(2):
            plan = generate_sql(question, dialect, schema, None, error)

            if not plan.get("sql"):
                error = plan.get("reason") or (
                    "No SQL was produced. If the question can be answered "
                    "from the tables above, return the SQL; otherwise "
                    "return sql = null again."
                )
                continue

            try:
                sql = AnalysisService._validate_guarded(
                    plan["sql"], dialect, allowed, databases
                )
                title = plan.get("title") or question[:80]
                tables_used = [*first_tables, *main_tables]

                # Build UNION ALL query with exact table names per database
                final_sql = AnalysisService._build_union_sql(
                    sql, db_tables, question, dialect
                )

                # Execute on all databases
                result = run_page_multi(
                    databases,
                    final_sql,
                    0,
                    settings.ANALYSIS_PAGE_SIZE,
                )
                break

            except UnsafeSQL as exc:
                error = str(exc)
                sql = None

            except SQLAlchemyError as exc:
                error = str(getattr(exc, "orig", exc)).splitlines()[0]
                sql = None

        if sql is None or result is None:
            logger.warning(
                "Could not produce a working query for %r: %s",
                question,
                error,
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                OUT_OF_SCOPE,
            )

        primary_result = result["databases"].get(first_db, {})
        return (
            first_db,
            None,
            tables_used,
            title,
            final_sql,
            primary_result,
            result,
            databases,
            client_ids_result,
        ), result

    @staticmethod
    def _build_union_sql(
        base_sql: str, db_tables: dict, question: str, dialect: str
    ) -> str:
        """
        Build a UNION ALL query with exact table names for each database.
        Replaces table names in the base SQL with actual physical table names per
        database. Shared main-DB references (pollmatrix.<table>) are left
        untouched: they resolve to the same shared data through every client
        connection and must never be duplicated per database.
        """
        from .registry import main_schema

        # Find all table names referenced in the SQL
        table_refs = set(re.findall(r"\b(from|join)\s+(\w+)", base_sql, re.IGNORECASE))
        base_table_names = {t[1] for t in table_refs} - {main_schema().lower()}

        if not base_table_names:
            return base_sql

        # Use global_catalog to discover logical->physical mapping
        databases = list(db_tables.keys())
        logical_map = discover_logical_tables(databases)

        subqueries = []
        replaced_any = False
        for db in databases:
            subquery = base_sql

            # For each base table name in the SQL, replace with physical name for this db
            for base_table in base_table_names:
                # Find the logical name that maps to this base table
                # The base_table from SQL could be either logical or physical
                logical_name = logical_table_name(base_table)

                # Find physical table name for this database
                physical_table = None
                if logical_name in logical_map and db in logical_map[logical_name]:
                    physical_table = logical_map[logical_name][db]
                elif base_table in logical_map and db in logical_map[base_table]:
                    physical_table = logical_map[base_table][db]

                if physical_table:
                    replaced_any = True
                    # Replace table reference with exact physical name for this database
                    pattern = rf"\b{re.escape(base_table)}\b"
                    subquery = re.sub(
                        pattern, physical_table, subquery, flags=re.IGNORECASE
                    )

            subqueries.append(f"({subquery})")

        # Nothing client-owned was referenced (question touches only shared
        # main-DB tables): run once through the client connection, no union.
        if not replaced_any:
            return base_sql

        if not subqueries:
            return base_sql

        return " UNION ALL ".join(subqueries)

    @staticmethod
    def ask_global(data, user_id: UUID, db_session: Session):
        """Handle database-independent query across all assigned clients."""
        plan_result, multi_result = AnalysisService.plan_and_run_global(
            data.question,
            user_id,
            db_session,
            data.table_type_filter,
            data.client_ids,
        )

        (
            database,
            client_id,
            tables,
            title,
            sql,
            primary_result,
            multi_result,
            databases,
            client_ids,
        ) = plan_result

        analysis = AnalysisQuery(
            user_id=user_id,
            client_id=None,
            database_name=database,
            question=data.question,
            title=title,
            sql=sql,
            status="SUCCESS",
            row_count=len(primary_result.get("rows", [])),
            page_number=primary_result.get("page", 0),
            page_size=primary_result.get("page_size", settings.ANALYSIS_PAGE_SIZE),
            total_time_ms=primary_result.get("total_time_ms"),
            query_hash=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        )

        db_session.add(analysis)
        db_session.commit()

        # Build client info for multi_result
        client_info = {}
        if hasattr(multi_result, "get") and "databases" in multi_result:
            # Map databases to client identifiers
            client_map = {}
            for db, cid in zip(databases, client_ids):
                client = db_session.get(Client, cid)
                if client:
                    client_map[db] = client.client_identifier

            client_info = {
                "clients": {
                    client_map.get(db, db): page_data
                    for db, page_data in multi_result["databases"].items()
                },
                "merged_result": multi_result.get("merged_result"),
                "join_key": multi_result.get("join_key"),
                "join_type": multi_result.get("join_type", "outer"),
            }

        return {
            "title": title,
            "database": database,
            "tables": tables,
            "sql": sql,
            "token": AnalysisService.sign_result(
                user_id,
                database,
                sql,
                None,
                databases=databases,
                client_ids=client_ids,
                join_key=data.join_key,
                join_type=data.join_type,
            ),
            "result": primary_result,
            "multi_result": client_info if client_info else None,
        }

    @staticmethod
    def sign_result(
        user_id: UUID,
        database: str,
        sql: str,
        client_id: UUID | None,
        databases: list[str] | None = None,
        client_ids: list[UUID] | None = None,
        join_key: str | None = None,
        join_type: str = "outer",
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

        # Add multi-client info if provided
        if databases and len(databases) > 1:
            payload["multi_db"] = True
            payload["databases"] = databases
            if client_ids:
                payload["client_ids"] = [str(c) for c in client_ids]
            payload["join_key"] = join_key
            payload["join_type"] = join_type

        return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def open_result(
        token: str,
        user_id: UUID,
        db_session: Session,
    ) -> tuple[str, str, UUID | None]:

        try:
            payload = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
            client_id_str = payload.get("client_id", "")
            client_id = UUID(client_id_str) if client_id_str else None
            database, sql = payload["db"], payload["sql"]

        except (jwt.PyJWTError, ValueError, KeyError, TypeError):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Result expired, please ask again",
            )

        if payload.get("type") != "analysis" or payload.get("sub") != str(user_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Invalid result token",
            )

        # For multi-client queries, client_id may be None
        if client_id is not None:
            assigned_db, _ = AnalysisService.assigned_database(
                db_session, user_id, client_id
            )

            if assigned_db != database:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Database assignment has changed",
                )

        return database, sql, client_id

    @staticmethod
    def plan_and_run(
        question: str,
        client_id: UUID | None,
        previous_sql: str | None,
        user_id: UUID,
        db_session: Session,
    ):

        database, client_id = AnalysisService.assigned_database(
            db_session, user_id, client_id
        )

        try:
            database, tables = select_tables(question, database)
        except LookupError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                str(exc),
            )

        dialect = sqlglot_dialect(get_engine(database))

        schema = "\n".join(
            describe_table(database, table, question)[0] for table in tables
        )
        allowed = {table.lower() for table in tables}

        error = None
        sql = None
        title = None
        result = None

        for _ in range(2):
            plan = generate_sql(question, dialect, schema, previous_sql, error)

            if not plan.get("sql"):
                error = plan.get("reason") or (
                    "No SQL was produced. If the question can be answered "
                    "from the tables above, return the SQL; otherwise "
                    "return sql = null again."
                )
                continue

            try:
                sql = AnalysisService._validate_guarded(
                    plan["sql"], dialect, allowed, [database]
                )
                title = plan.get("title") or question[:80]

                result = run_page(
                    database,
                    sql,
                    0,
                    settings.ANALYSIS_PAGE_SIZE,
                )
                break

            except UnsafeSQL as exc:
                error = str(exc)
                sql = None

            except SQLAlchemyError as exc:
                error = str(getattr(exc, "orig", exc)).splitlines()[0]
                sql = None

        if sql is None or result is None:
            logger.warning(
                "Could not produce a working query for %r: %s",
                question,
                error,
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                OUT_OF_SCOPE,
            )

        return database, client_id, tables, title, sql, result

    @staticmethod
    def plan_and_run_multi(
        question: str,
        client_ids: list[UUID] | None,
        previous_sql: str | None,
        user_id: UUID,
        db_session: Session,
        join_key: str | None = None,
        join_type: str = "outer",
    ):
        """
        Plan and execute query across multiple clients.
        """
        # Get all assigned databases for the clients
        db_assignments = AnalysisService.assigned_databases(
            db_session, user_id, client_ids
        )

        if len(db_assignments) == 1:
            # Single client - use existing logic
            database, client_id = db_assignments[0]
            return (
                AnalysisService.plan_and_run(
                    question, client_id, previous_sql, user_id, db_session
                ),
                None,
            )

        # Multiple clients - use first database for schema planning
        first_db, first_cid = db_assignments[0]
        databases = [db for db, _ in db_assignments]
        client_ids_result = [cid for _, cid in db_assignments]

        try:
            first_db, tables = select_tables(question, first_db)
        except LookupError as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                str(exc),
            )

        dialect = sqlglot_dialect(get_engine(first_db))

        schema = "\n".join(
            describe_table(first_db, table, question)[0] for table in tables
        )
        allowed = {table.lower() for table in tables}

        error = None
        sql = None
        title = None
        multi_result = None

        for _ in range(2):
            plan = generate_sql(question, dialect, schema, previous_sql, error)

            if not plan.get("sql"):
                error = plan.get("reason") or (
                    "No SQL was produced. If the question can be answered "
                    "from the tables above, return the SQL; otherwise "
                    "return sql = null again."
                )
                continue

            try:
                sql = AnalysisService._validate_guarded(
                    plan["sql"], dialect, allowed, databases
                )
                title = plan.get("title") or question[:80]

                # Execute on all databases
                multi_result = run_page_multi(
                    databases,
                    sql,
                    0,
                    settings.ANALYSIS_PAGE_SIZE,
                    join_key,
                    join_type,
                )
                break

            except UnsafeSQL as exc:
                error = str(exc)
                sql = None

            except SQLAlchemyError as exc:
                error = str(getattr(exc, "orig", exc)).splitlines()[0]
                sql = None

        if sql is None or multi_result is None:
            logger.warning(
                "Could not produce a working query for %r: %s",
                question,
                error,
            )
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                OUT_OF_SCOPE,
            )

        # Return primary result (from first db) for backward compatibility
        primary_result = multi_result["databases"].get(first_db, {})
        return (
            first_db,
            first_cid,
            tables,
            title,
            sql,
            primary_result,
            multi_result,
            databases,
            client_ids_result,
        ), multi_result

    @staticmethod
    def ask(data, user_id: UUID, db_session: Session):
        # Check if multi-client query requested
        if data.client_ids and len(data.client_ids) > 1:
            return AnalysisService.ask_multi(data, user_id, db_session)

        database, client_id, tables, title, sql, result = AnalysisService.plan_and_run(
            data.question,
            data.client_id,
            data.previous_sql,
            user_id,
            db_session,
        )

        analysis = AnalysisQuery(
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

        db_session.add(analysis)
        db_session.commit()

        return {
            "title": title,
            "database": database,
            "tables": tables,
            "sql": sql,
            "token": AnalysisService.sign_result(user_id, database, sql, client_id),
            "result": result,
        }

    @staticmethod
    def ask_multi(data, user_id: UUID, db_session: Session):
        """Handle multi-client query."""
        (
            database,
            client_id,
            tables,
            title,
            sql,
            primary_result,
            multi_result,
            databases,
            client_ids,
        ) = AnalysisService.plan_and_run_multi(
            data.question,
            data.client_ids,
            data.previous_sql,
            user_id,
            db_session,
            data.join_key,
            data.join_type,
        )[
            0
        ]

        # Store the query for the first client
        analysis = AnalysisQuery(
            user_id=user_id,
            client_id=client_id,
            database_name=database,
            question=data.question,
            title=title,
            sql=sql,
            status="SUCCESS",
            row_count=len(primary_result.get("rows", [])),
            page_number=primary_result.get("page", 0),
            page_size=primary_result.get("page_size", settings.ANALYSIS_PAGE_SIZE),
            total_time_ms=primary_result.get("total_time_ms"),
            query_hash=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        )

        db_session.add(analysis)
        db_session.commit()

        # Build client info for multi_result
        client_info = {}
        if multi_result and "databases" in multi_result:
            # Map databases to client identifiers
            client_map = {}
            for db, cid in zip(databases, client_ids):
                client = db_session.get(Client, cid)
                if client:
                    client_map[db] = client.client_identifier

            client_info = {
                "clients": {
                    client_map.get(db, db): page_data
                    for db, page_data in multi_result["databases"].items()
                },
                "merged_result": multi_result.get("merged_result"),
                "join_key": multi_result.get("join_key"),
                "join_type": multi_result.get("join_type", "outer"),
            }

        return {
            "title": title,
            "database": database,
            "tables": tables,
            "sql": sql,
            "token": AnalysisService.sign_result(
                user_id,
                database,
                sql,
                client_id,
                databases=databases,
                client_ids=client_ids,
                join_key=data.join_key,
                join_type=data.join_type,
            ),
            "result": primary_result,
            "multi_result": client_info if client_info else None,
        }

    @staticmethod
    def get_rows(data, user_id: UUID, db_session: Session):
        try:
            payload = jwt.decode(
                data.token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Result expired, please ask again",
            )

        if payload.get("type") != "analysis" or payload.get("sub") != str(user_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Invalid result token",
            )

        if payload.get("multi_db"):
            databases = payload.get("databases", [])
            sql = payload["sql"]
            join_key = payload.get("join_key")
            join_type = payload.get("join_type", "outer")
            AnalysisService._check_multi_access(db_session, user_id, payload)
            return run_page_multi(
                databases, sql, data.page, data.page_size, join_key, join_type
            )

        database, sql, _ = AnalysisService.open_result(data.token, user_id, db_session)
        return run_page(database, sql, data.page, data.page_size)

    @staticmethod
    def export_rows(data, user_id: UUID, db_session: Session):
        try:
            payload = jwt.decode(
                data.token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
            )
        except jwt.PyJWTError:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Result expired, please ask again",
            )

        if payload.get("type") != "analysis" or payload.get("sub") != str(user_id):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Invalid result token",
            )

        if payload.get("multi_db"):
            databases = payload.get("databases", [])
            sql = payload["sql"]
            AnalysisService._check_multi_access(db_session, user_id, payload)
            return stream_csv_multi(databases, sql)

        database, sql, _ = AnalysisService.open_result(data.token, user_id, db_session)
        return stream_csv(database, sql)

    @staticmethod
    def _check_multi_access(db_session: Session, user_id: UUID, payload: dict) -> None:
        databases = payload.get("databases", [])
        client_id_strs = payload.get("client_ids") or []
        if not databases:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid result token")
        if client_id_strs:
            try:
                client_ids = [UUID(str(c)) for c in client_id_strs]
            except ValueError:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid result token")
            assigned = AnalysisService.assigned_databases(
                db_session, user_id, client_ids
            )
            allowed = {db for db, _ in assigned}
            if set(databases) - allowed:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, "Database assignment has changed"
                )
        else:
            assigned = AnalysisService.assigned_databases(db_session, user_id, None)
            allowed = {db for db, _ in assigned}
            if set(databases) - allowed:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN, "Database assignment has changed"
                )

    @staticmethod
    def list_history(
        user_id: UUID,
        db_session: Session,
        client_id: UUID | None = None,
    ):
        stmt = (
            select(AnalysisQuery)
            .where(
                AnalysisQuery.user_id == user_id,
                AnalysisQuery.status == "SUCCESS",
            )
            .order_by(AnalysisQuery.created_at.desc())
            .limit(50)
        )

        if client_id is not None:
            stmt = stmt.where(AnalysisQuery.client_id == client_id)

        rows = db_session.scalars(stmt).all()
        # Convert to dict format that matches HistoryResponse schema
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

    @staticmethod
    def get_history(
        query_id: UUID,
        user_id: UUID,
        db_session: Session,
    ) -> AnalysisQuery:
        row = db_session.scalar(
            select(AnalysisQuery).where(
                AnalysisQuery.id == query_id,
                AnalysisQuery.user_id == user_id,
            )
        )

        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Analysis not found",
            )

        return row

    @staticmethod
    def run_history(query_id: UUID, user_id: UUID, db_session: Session):
        row = AnalysisService.get_history(query_id, user_id, db_session)

        # For global queries, client_id may be None
        if row.client_id is not None:
            database, _ = AnalysisService.assigned_database(
                db_session, user_id, row.client_id
            )

            if database != row.database_name:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Database assignment has changed",
                )
        else:
            # For global queries, use the stored database_name directly
            database = row.database_name

        try:
            result = run_page(
                database,
                row.sql,
                0,
                settings.ANALYSIS_PAGE_SIZE,
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
            "sql": row.sql,
            "token": AnalysisService.sign_result(
                user_id, database, row.sql, row.client_id
            ),
            "result": result,
        }

    @staticmethod
    def delete_history(query_id: UUID, user_id: UUID, db_session: Session) -> None:
        row = AnalysisService.get_history(query_id, user_id, db_session)
        db_session.delete(row)
        db_session.commit()

    @staticmethod
    def save_analysis(data, user_id: UUID, db_session: Session):
        database, sql, client_id = AnalysisService.open_result(
            data.token, user_id, db_session
        )

        row = SavedAnalysis(
            user_id=user_id,
            client_id=client_id,
            title=data.title,
            question=data.question,
            database=database,
            sql=sql,
        )

        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        return row

    @staticmethod
    def list_saved(user_id: UUID, db_session: Session):
        permitted = select(UserClient.client_id).where(UserClient.user_id == user_id)

        stmt = (
            select(SavedAnalysis)
            .outerjoin(
                Client,
                Client.id == SavedAnalysis.client_id,
            )
            .where(
                SavedAnalysis.user_id == user_id,
                (SavedAnalysis.client_id.is_(None))
                | (
                    SavedAnalysis.client_id.in_(permitted)
                    & (SavedAnalysis.database == Client.database_name)
                ),
            )
            .order_by(SavedAnalysis.created_at.desc())
        )

        return list(db_session.scalars(stmt).all())

    @staticmethod
    def get_saved(saved_id: UUID, user_id: UUID, db_session: Session) -> SavedAnalysis:
        row = db_session.scalar(
            select(SavedAnalysis).where(
                SavedAnalysis.id == saved_id,
                SavedAnalysis.user_id == user_id,
            )
        )

        if row is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Saved analysis not found",
            )

        return row

    @staticmethod
    def run_saved(saved_id: UUID, user_id: UUID, db_session: Session):
        row = AnalysisService.get_saved(saved_id, user_id, db_session)

        # For global queries, client_id may be None
        if row.client_id is not None:
            database, _ = AnalysisService.assigned_database(
                db_session, user_id, row.client_id
            )

            if database != row.database:
                raise HTTPException(
                    status.HTTP_403_FORBIDDEN,
                    "Database assignment has changed",
                )
        else:
            # For global queries, use the stored database directly
            database = row.database

        try:
            result = run_page(
                database,
                row.sql,
                0,
                settings.ANALYSIS_PAGE_SIZE,
            )
        except (SQLAlchemyError, KeyError) as exc:
            message = (
                str(getattr(exc, "orig", exc)).splitlines()[0]
                if isinstance(exc, SQLAlchemyError)
                else str(exc)
            )
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, message)

        return {
            "title": row.title,
            "database": database,
            "tables": [],
            "sql": row.sql,
            "token": AnalysisService.sign_result(
                user_id, database, row.sql, row.client_id
            ),
            "result": result,
        }

    @staticmethod
    def delete_saved(saved_id: UUID, user_id: UUID, db_session: Session) -> None:
        row = AnalysisService.get_saved(saved_id, user_id, db_session)
        db_session.delete(row)
        db_session.commit()
