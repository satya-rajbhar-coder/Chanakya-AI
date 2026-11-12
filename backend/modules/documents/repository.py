from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from modules.analysis.models import UserClient
from modules.users.models import User

from .models import Document, DocumentAssignment


class DocumentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, document: Document) -> Document:
        self.db.add(document)
        return document

    def get_by_id(self, document_id: UUID) -> Document | None:
        return self.db.get(Document, document_id)

    def _visible(self, user: User):
        if user.role == "admin":
            return select(Document.id)
        assigned_clients = select(UserClient.client_id).where(
            UserClient.user_id == user.id
        )
        assigned_directly = select(DocumentAssignment.document_id).where(
            DocumentAssignment.user_id == user.id
        )
        return select(Document.id).where(
            or_(
                Document.client_id.in_(assigned_clients),
                Document.id.in_(assigned_directly),
            )
        )

    def visible_ids(self, user: User) -> list[UUID]:
        return list(self.db.scalars(self._visible(user)).all())

    def get_all(self, user: User) -> list[Document]:
        stmt = select(Document).where(Document.id.in_(self._visible(user))).order_by(
            Document.created_at.desc(), Document.id.desc()
        )
        return list(self.db.scalars(stmt).all())

    def count_visible(self, user: User) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Document).where(Document.id.in_(self._visible(user)))
        ) or 0

    def count_uploaded_by(self, user_id: UUID) -> int:
        return self.db.scalar(
            select(func.count()).select_from(Document).where(Document.user_id == user_id)
        ) or 0

    def set_assignments(self, document: Document, user_ids: list[UUID]) -> None:
        wanted = set(user_ids)
        current = {a.user_id: a for a in document.assignments}
        for user_id in current.keys() - wanted:
            self.db.delete(current[user_id])
        for user_id in wanted - current.keys():
            self.db.add(DocumentAssignment(document_id=document.id, user_id=user_id))

    def delete(self, document: Document) -> None:
        self.db.delete(document)