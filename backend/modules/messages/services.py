import base64
import logging
from datetime import datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from llm.service import generate_reply, is_not_found
from modules.analysis.models import AnalysisQuery
from modules.conversations.models import DEFAULT_TITLE
from modules.conversations.services import ConversationService
from modules.documents.repository import DocumentRepository
from modules.intelligence.models import ChatAnalysisQuery
from modules.users.models import User
from rag.service import (
    RetrievedChunk,
    format_context,
    format_sources,
    retrieve,
    strip_sources,
)

from .models import Message, Role
from .repository import MessageRepository
from .schemas import MessageCreate, MessageUpdate

logger = logging.getLogger(__name__)

HISTORY_LIMIT = 20
SHORT_QUESTION_CHARS = 80
Cursor = tuple[datetime, UUID]

NO_DOCUMENTS_REPLY = "No documents are available for your assigned assemblies. Contact your administrator."
NOT_FOUND_REPLY = "I couldn't find the answer in the documents available to you."


def encode_cursor(cursor: Cursor) -> str:
    raw = f"{cursor[0].isoformat()}|{cursor[1]}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def decode_cursor(value: str) -> Cursor:
    try:
        raw = base64.urlsafe_b64decode(value.encode()).decode()
        created_at, message_id = raw.split("|", 1)
        return datetime.fromisoformat(created_at), UUID(message_id)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid cursor"
        )


class MessageService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = MessageRepository(db)
        self.conversations = ConversationService(db)
        self.documents = DocumentRepository(db)

    def _history(self, conversation_id: UUID) -> list[tuple[str, str]]:
        rows, _ = self.repo.get_all_by_conversation(
            conversation_id, limit=HISTORY_LIMIT
        )
        rows.reverse()
        return [(m.role.value, strip_sources(m.content)) for m in rows]

    def _has_documents(self, user: User) -> bool:
        try:
            return self.documents.count_visible(user) > 0
        except Exception:
            logger.exception("Failed to check documents for user %s", user.id)
            return False

    @staticmethod
    def _previous_user_message(history: list[tuple[str, str]]) -> str | None:
        return next((c for role, c in reversed(history) if role == "user"), None)

    def _build_retrieval_query(
        self, question: str, history: list[tuple[str, str]]
    ) -> str:
        query = question.strip()
        if len(query) >= SHORT_QUESTION_CHARS:
            return query
        previous = self._previous_user_message(history)
        return f"{previous[:500]} {query}" if previous else query

    def _retrieve_context(
        self, user: User, question: str, history: list[tuple[str, str]]
    ) -> list[RetrievedChunk]:
        query = self._build_retrieval_query(question, history)
        try:
            return retrieve(self.documents.visible_ids(user), query)
        except Exception:
            # Strict scope: an empty list would look like "not found", so fail loudly.
            logger.exception("Document retrieval failed for user %s", user.id)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Document search is currently unavailable",
            )

    def _commit(self) -> None:
        try:
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def create_and_reply(self, user: User, conversation_id: UUID, data: MessageCreate):
        conversation = self.conversations.get_conversation(conversation_id, user)
        content = data.content.strip()
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Message cannot be empty",
            )

        history = self._history(conversation.id)

        user_message = Message(
            conversation_id=conversation.id,
            user_id=user.id,
            role=Role.USER,
            content=content,
        )
        self.repo.add(user_message)
        conversation.updated_at = func.now()
        self._commit()
        self.db.refresh(user_message)

        has_documents = self._has_documents(user)
        chunks = self._retrieve_context(user, content, history) if has_documents else []

        if not has_documents:
            answer = NO_DOCUMENTS_REPLY
        elif not chunks:
            # Nothing relevant retrieved: the LLM is not even called.
            answer = NOT_FOUND_REPLY
        else:
            try:
                raw = generate_reply(
                    history=history,
                    user_content=content,
                    context=format_context(chunks),
                ).strip()
                if not raw:
                    raise ValueError("Empty LLM response")
            except Exception:
                logger.exception(
                    "LLM request failed for conversation %s", conversation.id
                )
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="The language model is currently unavailable",
                )

            answer = (
                NOT_FOUND_REPLY if is_not_found(raw) else raw + format_sources(chunks)
            )

        assistant_message = Message(
            conversation_id=conversation.id,
            user_id=user.id,
            role=Role.ASSISTANT,
            content=answer,
        )
        self.repo.add(assistant_message)

        if conversation.title == DEFAULT_TITLE:
            conversation.title = content[:60]
        conversation.updated_at = func.now()

        self._commit()
        self.db.refresh(assistant_message)
        return user_message, assistant_message

    def get_message(
        self, conversation_id: UUID, message_id: UUID, user: User
    ) -> Message:
        self.conversations.get_conversation(conversation_id, user)
        message = self.repo.get_by_id(conversation_id, message_id)
        if message is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Message does not exist"
            )
        return message

    def get_messages(
        self,
        conversation_id: UUID,
        user: User,
        limit: int = 50,
        cursor: str | None = None,
    ) -> tuple[list[Message], str | None]:
        self.conversations.get_conversation(conversation_id, user)
        decoded = decode_cursor(cursor) if cursor else None
        messages, next_cursor = self.repo.get_all_by_conversation(
            conversation_id=conversation_id,
            limit=min(max(limit, 1), 100),
            cursor=decoded,
        )
        turns_by_timestamp: dict[datetime, list[Message]] = {}
        for message in messages:
            turns_by_timestamp.setdefault(message.created_at, []).append(message)

        claimed_query_ids: set[UUID] = set()
        linked_legacy_query = False
        for turn_messages in turns_by_timestamp.values():
            user_messages = [
                message for message in turn_messages if message.role == Role.USER
            ]
            assistant_messages = [
                message
                for message in turn_messages
                if message.role == Role.ASSISTANT
            ]
            if len(user_messages) != 1 or len(assistant_messages) != 1:
                continue

            user_message = user_messages[0]
            assistant_message = assistant_messages[0]
            if assistant_message.analysis_query_id is not None:
                continue

            candidates = list(
                self.db.scalars(
                    select(AnalysisQuery).where(
                        AnalysisQuery.user_id == user.id,
                        AnalysisQuery.status == "SUCCESS",
                        AnalysisQuery.question == user_message.content,
                        AnalysisQuery.created_at
                        >= user_message.created_at - timedelta(minutes=15),
                        AnalysisQuery.created_at <= user_message.created_at,
                        AnalysisQuery.id.not_in(
                            select(ChatAnalysisQuery.analysis_query_id)
                        ),
                    )
                ).all()
            )
            candidates = [
                item for item in candidates if item.id not in claimed_query_ids
            ]
            if len(candidates) == 1:
                query = candidates[0]
                assistant_message.analysis_query_link = ChatAnalysisQuery(
                    analysis_query_id=query.id,
                )
                claimed_query_ids.add(query.id)
                linked_legacy_query = True

        if linked_legacy_query:
            self._commit()
        return messages, encode_cursor(next_cursor) if next_cursor else None

    def _get_own_user_message(
        self, user: User, conversation_id: UUID, message_id: UUID, action: str
    ) -> Message:
        message = self.get_message(conversation_id, message_id, user)
        if message.role != Role.USER:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Assistant messages cannot be {action}",
            )
        if message.user_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You cannot {action.rstrip('d')} this message",
            )
        return message

    def update_message(
        self, user: User, conversation_id: UUID, message_id: UUID, data: MessageUpdate
    ) -> Message:
        message = self._get_own_user_message(
            user, conversation_id, message_id, "edited"
        )
        message.content = data.content
        self._commit()
        self.db.refresh(message)
        return message

    def delete_message(
        self, user: User, conversation_id: UUID, message_id: UUID
    ) -> None:
        message = self._get_own_user_message(
            user, conversation_id, message_id, "deleted"
        )
        self.repo.delete(message)
        self._commit()
