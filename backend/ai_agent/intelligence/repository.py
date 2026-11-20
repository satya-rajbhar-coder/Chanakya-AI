from datetime import datetime, timedelta, UTC
from uuid import UUID

from sqlalchemy.orm import Session

from modules.conversations.schemas import ConversationCreate
from modules.conversations.services import ConversationService
from modules.messages.models import Message, Role
from modules.messages.repository import MessageRepository
from modules.users.models import User

from .models import ChatAnalysisQuery


class IntelligenceRepository:
    def __init__(self, db: Session, user: User):
        self.db = db
        self.user = user
        self.conversations = ConversationService(db)
        self.message_repo = MessageRepository(db)

    def get_or_create_conversation(self, conversation_id: UUID | None, title: str):
        if conversation_id is not None:
            return self.conversations.get_conversation(conversation_id, self.user)
        return self.conversations.create_conversation(
            self.user, ConversationCreate(title=title)
        )

    def save_chat_turn(
        self,
        conversation_id: UUID,
        user_content: str,
        assistant_content: str,
        analysis_query_id: UUID | None = None,
    ):
        now = datetime.now(UTC)
        user_message = Message(
            conversation_id=conversation_id,
            user_id=self.user.id,
            role=Role.USER,
            content=user_content,
            created_at=now,
        )
        self.message_repo.add(user_message)

        assistant_message = Message(
            conversation_id=conversation_id,
            user_id=self.user.id,
            role=Role.ASSISTANT,
            content=assistant_content,
            created_at=now + timedelta(microseconds=1),
        )
        self.message_repo.add(assistant_message)

        if analysis_query_id is not None:
            assistant_message.analysis_query_link = ChatAnalysisQuery(
                analysis_query_id=analysis_query_id,
            )

        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self.db.refresh(user_message)
        self.db.refresh(assistant_message)
        return user_message, assistant_message
