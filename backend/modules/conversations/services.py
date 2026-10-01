from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from modules.users.models import User

from .models import Conversation
from .repository import ConversationRepository
from .schemas import ConversationCreate, ConversationUpdate


class ConversationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = ConversationRepository(db)

    def create_conversation(self, user: User, data: ConversationCreate) -> Conversation:
        try:
            conversation = self.repo.create(user_id=user.id, title=data.title)
            self.db.commit()
            self.db.refresh(conversation)
        except Exception:
            self.db.rollback()
            raise

        return conversation

    def get_conversation(self, conversation_id: UUID, user: User) -> Conversation:
        conversation = self.repo.get_by_id(
            user_id=user.id, conversation_id=conversation_id
        )

        if conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation does not exist",
            )

        return conversation

    def get_conversations(
        self, user: User, limit: int = 10, offset: int = 0
    ) -> list[Conversation]:
        return self.repo.get_all(user_id=user.id, limit=limit, offset=offset)

    def update_conversation(
        self, user: User, conversation_id: UUID, data: ConversationUpdate
    ) -> Conversation:
        conversation = self.get_conversation(conversation_id, user)
        conversation.title = data.title

        try:
            self.db.commit()
            self.db.refresh(conversation)
        except Exception:
            self.db.rollback()
            raise

        return conversation

    def delete_conversation(self, user: User, conversation_id: UUID) -> None:
        conversation = self.get_conversation(conversation_id=conversation_id, user=user)
        try:
            self.db.delete(conversation)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
