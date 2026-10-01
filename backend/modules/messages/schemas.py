from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

from .models import Role

Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class MessageCreate(BaseModel):
    content: Content


class MessageUpdate(BaseModel):
    content: Content


class MessageResponse(BaseModel):
    id: UUID
    user_id: UUID | None
    conversation_id: UUID
    role: Role
    content: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ChatResponse(BaseModel):
    user_message: MessageResponse
    assistant_message: MessageResponse


class MessagePage(BaseModel):
    items: list[MessageResponse]  # newest first
    next_cursor: str | None = None
