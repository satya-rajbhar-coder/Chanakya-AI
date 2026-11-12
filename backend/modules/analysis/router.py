from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from api.dependencies import CurrentUser
from database.session import get_db
from modules.analysis.schemas import (
    AnalysisResponse,
    AskRequest,
    ClientResponse,
    HistoryResponse,
    TokenRequest,
    UserHistoryResponse,
)

from .repository import AnalysisRepository
from .service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["Analysis"])


def _service(db: Session = Depends(get_db)) -> AnalysisService:
    return AnalysisService(db)


@router.get("/clients", response_model=list[ClientResponse])
def assigned_clients(user: CurrentUser, db: Session = Depends(get_db)):
    repo = AnalysisRepository(db)
    clients = repo.get_active_clients_for_user(user.id)
    return [ClientResponse.model_validate(c) for c in clients]


@router.post("/query", response_model=AnalysisResponse)
def ask(data: AskRequest, user: CurrentUser, svc: AnalysisService = Depends(_service)):
    return svc.ask(data, user.id)


@router.post("/export")
def export(
    data: TokenRequest, user: CurrentUser, svc: AnalysisService = Depends(_service)
):
    """Export ALL rows for a token (no pagination) as CSV."""
    csv_generator = svc.export_rows(data, user.id)

    def csv_stream():
        yield from csv_generator

    return StreamingResponse(
        csv_stream(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="export.csv"'},
    )


@router.get("/history", response_model=list[UserHistoryResponse])
def history(
    user: CurrentUser,
    svc: AnalysisService = Depends(_service),
    client_id: UUID | None = None,
):
    """History for regular users - excludes SQL."""
    return svc.list_history(user.id, client_id)


@router.get("/admin/history", response_model=list[HistoryResponse])
def admin_history(
    user: CurrentUser,
    svc: AnalysisService = Depends(_service),
    client_id: UUID | None = None,
):
    """History for admin users - includes SQL."""
    if user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return svc.list_history(user.id, client_id)


@router.delete("/history/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(
    query_id: UUID, user: CurrentUser, svc: AnalysisService = Depends(_service)
):
    svc.delete_history(query_id, user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/history/{query_id}/run", response_model=AnalysisResponse)
def run_history(
    query_id: UUID,
    user: CurrentUser,
    page: int = Query(default=0, ge=0),
    page_size: int = Query(default=100, ge=1, le=500),
    svc: AnalysisService = Depends(_service),
):
    """Re-execute a stored query using its saved SQL, optionally by page."""
    return svc.run_history(query_id, user.id, page=page, page_size=page_size)
