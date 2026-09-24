import base64
import logging
from datetime import datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from llm.service import generate_reply
from modules.conversations.models import DEFAULT_TITLE
from modules.conversations.services import ConversationService
from modules.documents.repository import DocumentRepository
from modules.users.models import User
from rag.service import (
    RetrievedChunk, format_context, format_sources, retrieve, strip_sources,
)
from .models import Message, Role
from .repository import MessageRepository
from .schemas import MessageCreate, MessageUpdate


logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20
SHORT_QUESTION_CHARS = 80
Cursor = tuple[datetime, UUID]


def encode_cursor(cursor: Cursor) -> str:
    raw = f"{cursor[0].isoformat()}|{cursor[1]}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(value: str) -> Cursor:
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        created_at, message_id = raw.split("|", 1)
        return datetime.fromisoformat(created_at), UUID(message_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid cursor"
        )


class MessageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MessageRepository(db)
        self.conversations = ConversationService(db)
        self.documents = DocumentRepository(db)

    # ----------------------------------------------------------- helpers
    def _history(self, conversation_id: UUID) -> list[tuple[str, str]]:
        """Last HISTORY_LIMIT messages in chronological order.

        The repository returns newest-first; the previous code passed that
        straight to the LLM, so the model saw the conversation backwards.
        """
        rows, _ = self.repo.get_all_by_conversation(
            conversation_id, limit=HISTORY_LIMIT
        )
        rows.reverse()
        return [(m.role.value, strip_sources(m.content)) for m in rows]

    def _retrieve_context(
        self, user: User, question: str, history: list[tuple[str, str]],
    ) -> list[RetrievedChunk]:
        if self.documents.count_for_user(user.id) == 0:
            return []

        # Short follow-ups ("and the second one?") embed poorly on their own,
        # so borrow the previous user turn for the search query.
        query = question
        if len(question) < SHORT_QUESTION_CHARS:
            previous = next(
                (c for role, c in reversed(history) if role == "user"), None
            )
            if previous:
                query = f"{previous[:300]} {question}"

        try:
            return retrieve(user.id, query)
        except Exception:
            # Retrieval problems must never take the whole chat down.
            logger.exception("Document retrieval failed for user %s", user.id)
            return []

    def _commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    # ------------------------------------------------------------- create
    def create_and_reply(self, user: User, conversation_id: UUID, data: MessageCreate):
        conversation = self.conversations.get_conversation(
            conversation_id, user
        )
        content = data.content

        history = self._history(conversation.id)

        user_message = Message(
            conversation_id=conversation.id, user_id=user.id,
            role=Role.USER, content=content
        )
        self.repo.add(user_message)
        conversation.updated_at = func.now()
        self._commit()
        self.db.refresh(user_message)

        chunks = self._retrieve_context(user, content, history)

        try:
            answer = generate_reply(
                history, content,
                context=format_context(chunks) if chunks else None,
            ).strip()
            if not answer:
                raise ValueError("Empty LLM response")
        except Exception:
            logger.exception(
                "LLM request failed for conversation %s", conversation.id)
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY,
                "The language model is currently unavailable",
            )

        if chunks:
            answer += format_sources(chunks)

        assistant_message = Message(
            conversation_id=conversation.id, user_id=user.id,
            role=Role.ASSISTANT, content=answer
        )
        self.repo.add(assistant_message)

        if conversation.title == DEFAULT_TITLE:
            conversation.title = content[:60]
        conversation.updated_at = func.now()

        self._commit()
        self.db.refresh(assistant_message)

        return user_message, assistant_message

    # --------------------------------------------------------------- read
    def get_message(self, conversation_id: UUID, message_id: UUID, user: User) -> Message:
        self.conversations.get_conversation(conversation_id, user)

        message = self.repo.get_by_id(conversation_id, message_id)
        if message is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Message does not exist"
            )

        return message

    def get_messages(self, conversation_id: UUID, user: User, limit: int = 50, cursor: str | None = None) -> tuple[list[Message], str | None]:
        self.conversations.get_conversation(conversation_id, user)

        decoded = decode_cursor(cursor) if cursor else None
        messages, next_cursor = self.repo.get_all_by_conversation(
            conversation_id=conversation_id,
            limit=min(max(limit, 1), 100), cursor=decoded
        )
        return messages, encode_cursor(next_cursor) if next_cursor else None

    # ------------------------------------------------------ update/delete
    def _get_own_user_message(self, user: User, conversation_id: UUID, message_id: UUID, action: str) -> Message:
        message = self.get_message(conversation_id, message_id, user)
        if message.role != Role.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Assistant messages cannot be {action}"
            )

        if message.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You cannot {action.rstrip('d')} this message"
            )

        return message

    def update_message(self, user: User, conversation_id: UUID, message_id: UUID, data: MessageUpdate) -> Message:
        message = self._get_own_user_message(
            user, conversation_id, message_id, "edited"
        )
        message.content = data.content
        self._commit()
        self.db.refresh(message)
        return message

    def delete_message(self, user: User, conversation_id: UUID, message_id: UUID) -> None:
        message = self._get_own_user_message(
            user, conversation_id, message_id, "deleted")
        self.repo.delete(message)
        self._commit()
