from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.users.models import User

from .models import AnalysisQuery


class AnalysisRepository:
    """Data access layer for analysis queries and saved analyses.
    Contains only raw database operations — no business logic, no HTTP concerns."""

    def __init__(self, db: Session):
        self.db = db

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
