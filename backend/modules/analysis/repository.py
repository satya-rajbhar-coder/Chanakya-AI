from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.users.models import User

from .models import AnalysisQuery, Client, UserClient


class AnalysisRepository:
    """Data access layer for analysis queries, saved analyses, clients, and
    user-client assignments. Contains only raw database operations — no
    business logic, no HTTP concerns."""

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Client / assignment lookups
    # ------------------------------------------------------------------

    def get_client_database_name(self, client_id: UUID) -> str | None:
        return self.db.scalar(
            select(Client.database_name).where(Client.id == client_id)
        )

    def get_client_identifier(self, client_id: UUID) -> str | None:
        """Return the client_identifier string (e.g. 'client147') for a client UUID."""
        return self.db.scalar(
            select(Client.client_identifier).where(Client.id == client_id)
        )

    def get_client_database_name_for_user(
        self, client_id: UUID, user_id: UUID, is_admin: bool
    ) -> str | None:
        if is_admin:
            return self.db.scalar(
                select(Client.database_name).where(Client.id == client_id)
            )
        return self.db.scalar(
            select(Client.database_name)
            .join(UserClient, UserClient.client_id == Client.id)
            .where(UserClient.user_id == user_id, Client.id == client_id)
        )

    def get_assigned_client_ids(self, user_id: UUID) -> list[UUID]:
        return list(
            self.db.scalars(
                select(UserClient.client_id).where(UserClient.user_id == user_id)
            ).all()
        )

    def get_assigned_databases(
        self, user_id: UUID, client_ids: list[UUID] | None = None
    ) -> list[tuple[str, UUID]]:
        """Return [(database_name, client_id), ...] for the user's assigned
        clients. If client_ids is None, all assigned clients are returned."""
        if client_ids is None:
            client_ids = self.get_assigned_client_ids(user_id)
            if not client_ids:
                return []

        user = self.db.get(User, user_id)
        is_admin = user is not None and user.role == "admin"

        results: list[tuple[str, UUID]] = []
        for cid in client_ids:
            name = self.get_client_database_name_for_user(cid, user_id, is_admin)
            if name is None:
                continue
            results.append((name, cid))
        return results

    def get_active_clients_for_user(self, user_id: UUID) -> list[Client]:
        return list(
            self.db.scalars(
                select(Client)
                .join(UserClient, UserClient.client_id == Client.id)
                .where(
                    UserClient.user_id == user_id, Client.is_active == True
                )  # noqa: E712
                .order_by(Client.code)
            ).all()
        )

    # ------------------------------------------------------------------
    # AnalysisQuery (history)
    # ------------------------------------------------------------------

    def create_analysis_query(
        self,
        user_id: UUID,
        client_id: UUID | None,
        database_name: str,
        question: str,
        title: str,
        sql: str,
        status: str,
        row_count: int | None,
        page_number: int | None,
        page_size: int | None,
        total_time_ms: float | None,
        query_hash: str,
    ) -> AnalysisQuery:
        row = AnalysisQuery(
            user_id=user_id,
            client_id=client_id,
            database_name=database_name,
            question=question,
            title=title,
            sql=sql,
            status=status,
            row_count=row_count,
            page_number=page_number,
            page_size=page_size,
            total_time_ms=total_time_ms,
            query_hash=query_hash,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def get_analysis_query(self, query_id: UUID, user_id: UUID) -> AnalysisQuery | None:
        return self.db.scalar(
            select(AnalysisQuery).where(
                AnalysisQuery.id == query_id, AnalysisQuery.user_id == user_id
            )
        )

    def list_analysis_queries(
        self, user_id: UUID, client_id: UUID | None = None, limit: int = 50
    ) -> list[AnalysisQuery]:
        stmt = (
            select(AnalysisQuery)
            .where(
                AnalysisQuery.user_id == user_id,
                AnalysisQuery.status == "SUCCESS",
            )
            .order_by(AnalysisQuery.created_at.desc())
            .limit(limit)
        )
        if client_id is not None:
            stmt = stmt.where(AnalysisQuery.client_id == client_id)
        return list(self.db.scalars(stmt).all())

    def delete_analysis_query(self, query_id: UUID, user_id: UUID) -> None:
        row = self.get_analysis_query(query_id, user_id)
        if row is not None:
            self.db.delete(row)
            self.db.commit()
