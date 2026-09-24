from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from api.dependencies import CurrentUser
from database.session import get_db
from .schemas import ConversationCreate, ConversationResponse, ConversationUpdate
from .services import ConversationService


router = APIRouter(prefix="/conversations", tags=["Conversations"],)


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED,)
def create_conversation(data: ConversationCreate, current_user: CurrentUser, db: Session = Depends(get_db)) -> ConversationResponse:
    conversation = ConversationService(db).create_conversation(
        user=current_user, data=data,
    )
    return ConversationResponse.model_validate(conversation)


@router.get("", response_model=list[ConversationResponse])
def get_conversations(current_user: CurrentUser, db: Session = Depends(get_db), limit: Annotated[int, Query(ge=1, le=100)] = 50, offset: Annotated[int, Query(ge=0)] = 0,) -> list[ConversationResponse]:
    conversations = ConversationService(db).get_conversations(
        user=current_user, limit=limit, offset=offset,
    )
    return [ConversationResponse.model_validate(c) for c in conversations]


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: UUID, current_user: CurrentUser, db: Session = Depends(get_db)) -> ConversationResponse:
    conversation = ConversationService(db).get_conversation(
        user=current_user, conversation_id=conversation_id,
    )
    return ConversationResponse.model_validate(conversation)


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(conversation_id: UUID, data: ConversationUpdate, current_user: CurrentUser, db: Session = Depends(get_db)) -> ConversationResponse:
    conversation = ConversationService(db).update_conversation(
        user=current_user, conversation_id=conversation_id, data=data,
    )
    return ConversationResponse.model_validate(conversation)


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: UUID, current_user: CurrentUser, db: Session = Depends(get_db)) -> None:
    ConversationService(db).delete_conversation(current_user, conversation_id)
