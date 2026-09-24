from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Document


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, document: Document) -> Document:
        self.db.add(document)
        return document

    def get_by_id(self, user_id: UUID, document_id: UUID) -> Document | None:
        stmt = select(Document).where(
            Document.user_id == user_id,
            Document.id == document_id,
        )
        return self.db.scalar(stmt)

    def get_all(self, user_id: UUID) -> list[Document]:
        stmt = (
            select(Document)
            .where(Document.user_id == user_id)
            .order_by(Document.created_at.desc(), Document.id.desc())
        )
        return list(self.db.scalars(stmt).all())

    def count_for_user(self, user_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(Document)
            .where(Document.user_id == user_id)
        )
        return self.db.scalar(stmt) or 0

    def delete(self, document: Document) -> None:
        self.db.delete(document)
