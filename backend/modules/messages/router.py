from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from api.dependencies import CurrentUser
from database.session import get_db

from .schemas import (
    ChatResponse,
    MessageCreate,
    MessagePage,
    MessageResponse,
    MessageUpdate,
)
from .services import MessageService

router = APIRouter(
    prefix="/conversations/{conversation_id}/messages", tags=["Messages"]
)


# The reply is generated synchronously, so this is 201 (created), not 202.
@router.post("", response_model=ChatResponse, status_code=status.HTTP_201_CREATED)
def create_message(
    conversation_id: UUID,
    data: MessageCreate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> ChatResponse:
    user_msg, assistant_msg = MessageService(db).create_and_reply(
        conversation_id=conversation_id, user=current_user, data=data
    )

    return ChatResponse(
        user_message=MessageResponse.model_validate(user_msg),
        assistant_message=MessageResponse.model_validate(assistant_msg),
    )


@router.get("", response_model=MessagePage)
def get_messages(
    conversation_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: str | None = None,
) -> MessagePage:
    messages, next_cursor = MessageService(db).get_messages(
        conversation_id=conversation_id, user=current_user, limit=limit, cursor=cursor
    )

    return MessagePage(
        items=[MessageResponse.model_validate(m) for m in messages],
        next_cursor=next_cursor,
    )


@router.get("/{message_id}", response_model=MessageResponse)
def get_message(
    conversation_id: UUID,
    message_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> MessageResponse:
    message = MessageService(db).get_message(
        conversation_id=conversation_id, message_id=message_id, user=current_user
    )
    return MessageResponse.model_validate(message)


@router.patch("/{message_id}", response_model=MessageResponse)
def update_message(
    conversation_id: UUID,
    message_id: UUID,
    data: MessageUpdate,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> MessageResponse:
    message = MessageService(db).update_message(
        conversation_id=conversation_id,
        message_id=message_id,
        user=current_user,
        data=data,
    )

    return MessageResponse.model_validate(message)


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    conversation_id: UUID,
    message_id: UUID,
    current_user: CurrentUser,
    db: Session = Depends(get_db),
) -> None:
    MessageService(db).delete_message(
        conversation_id=conversation_id, message_id=message_id, user=current_user
    )
