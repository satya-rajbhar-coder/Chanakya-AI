from datetime import datetime
from enum import Enum as PyEnum
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as SQLEnum, ForeignKey, Index, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database.base import Base

if TYPE_CHECKING:
    from modules.conversations.models import Conversation
    from modules.users.models import User


class Role(PyEnum):
    USER = "user"
    ASSISTANT = "assistant"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    conversation_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Was `Mapped[UUID | None]` + nullable=False + ondelete="SET NULL", which
    # contradict each other (deleting a user would violate NOT NULL).
    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )

    role: Mapped[Role] = mapped_column(
        SQLEnum(
            Role,
            values_callable=lambda enum_cls: [m.value for m in enum_cls],
            name="message_role",
        ),
        nullable=False, default=Role.USER,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        server_default=func.now(), onupdate=func.now(),
    )

    conversation: Mapped["Conversation"] = relationship(
        "Conversation", back_populates="messages"
    )

    user: Mapped["User"] = relationship("User", back_populates="messages")

    __table_args__ = (
        Index(
            "ix_messages_conversation_created_id",
            "conversation_id", "created_at", "id",
        ),
    )
