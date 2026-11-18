from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from modules.messages.models import Message


class ChatAnalysisQuery(Base):
    __tablename__ = "chat_analysis_queries"

    assistant_message_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    analysis_query_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("analysis_queries.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    message: Mapped[Message] = relationship(
        "Message", back_populates="analysis_query_link"
    )
