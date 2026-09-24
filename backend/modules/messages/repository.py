from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .models import Message


class MessageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def add(self, message: Message) -> Message:
        self.db.add(message)
        return message

    def get_by_id(self, conversation_id: UUID, message_id: UUID) -> Message | None:
        stmt = select(Message).where(
            Message.id == message_id,
            Message.conversation_id == conversation_id
        )
        return self.db.scalar(stmt)

    def delete(self, message: Message) -> None:
        self.db.delete(message)

    def get_all_by_conversation(
        self, conversation_id: UUID, limit: int = 20,
        cursor: tuple[datetime, UUID] | None = None,
    ) -> tuple[list[Message], tuple[datetime, UUID] | None]:
        """Newest first. Returns (messages, cursor for the next older page)."""
        stmt = select(Message).where(
            Message.conversation_id == conversation_id
        )

        if cursor is not None:
            cursor_created_at, cursor_id = cursor
            stmt = stmt.where(
                or_(
                    Message.created_at < cursor_created_at,
                    and_(
                        Message.created_at == cursor_created_at,
                        Message.id < cursor_id
                    ),
                )
            )

        stmt = (
            stmt.order_by(Message.created_at.desc(), Message.id.desc())
            .limit(limit + 1)
        )
        messages = list(self.db.scalars(stmt).all())

        next_cursor = None
        if len(messages) > limit:
            messages = messages[:limit]
            last = messages[-1]
            next_cursor = (last.created_at, last.id)
        return messages, next_cursor
