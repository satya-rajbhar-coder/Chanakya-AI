from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Conversation


class ConversationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, user_id: UUID, title: str) -> Conversation:
        obj = Conversation(user_id=user_id, title=title)
        self.db.add(obj)
        self.db.flush()

        return obj

    def get_all(self, user_id: UUID, limit: int = 50, offset: int = 0,) -> list[Conversation]:
        # Most recently active first (matches ix_conversations_user_updated).
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
            .limit(limit).offset(offset)
        )

        return list(self.db.scalars(stmt).all())

    def get_by_id(self, user_id: UUID, conversation_id: UUID) -> Conversation | None:
        stmt = select(Conversation).where(
            Conversation.user_id == user_id,
            Conversation.id == conversation_id
        )

        return self.db.scalar(stmt)

    def delete(self, obj: Conversation) -> None:
        self.db.delete(obj)
