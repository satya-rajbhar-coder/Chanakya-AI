from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.dependencies import CurrentUser
from database.session import get_db
from modules.intelligence.schemas import IntelligenceRequest, IntelligenceResponse
from modules.intelligence.service import IntelligenceService

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
):
    """Hybrid question-answering: routes to database (SQL), documents (RAG),
    both, or indicates the question cannot be answered from available sources.
    Chats are persisted to the conversations/messages tables."""
    try:
        return svc.ask(
            data.question,
            client_id=data.client_id,
            conversation_id=conversation_id or data.conversation_id,
        )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - log and return 502
        logger = __import__("logging").getLogger(__name__)
        logger.exception("Intelligence ask failed")
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail="Could not process the question. Please try again.",
        ) from exc
