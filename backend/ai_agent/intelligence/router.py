from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import CurrentUser
from core.rate_limit import rate_limit_dependency
from database.session import get_db
from ai_agent.intelligence.schemas import IntelligenceRequest, IntelligenceResponse
from ai_agent.intelligence.service import IntelligenceService

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])


def _service(user: CurrentUser, db=Depends(get_db)) -> IntelligenceService:
    return IntelligenceService(db, user)


@router.post("/ask", response_model=IntelligenceResponse)
def ask_intelligence(
    data: IntelligenceRequest,
    user: CurrentUser,
    conversation_id: UUID | None = Query(
        default=None,
        description="Existing conversation id to continue the chat; omitted creates a new one.",
    ),
    svc: IntelligenceService = Depends(_service),
    _rate_limit: Annotated[None, Depends(rate_limit_dependency)] = None,
):
    try:
        return svc.ask(
            data.question,
            conversation_id=conversation_id or data.conversation_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("Intelligence ask failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Could not process the question. Please try again.",
        ) from exc
