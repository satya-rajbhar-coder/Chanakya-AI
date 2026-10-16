from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.dependencies import AdminUser, CurrentUser
from database.session import get_db
from modules.analysis.models import Client, UserClient
from modules.analysis.schemas import (
    AnalysisResponse,
    AskRequest,
    AskGlobalRequest,
    HistoryResponse,
    RowsRequest,
    SavedResponse,
    SaveRequest,
    TokenRequest,
    ClientResponse,
)
from .service import AnalysisService

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("/clients", response_model=list[ClientResponse])
def assigned_clients(user: CurrentUser, db: Session = Depends(get_db)):
    return list(
        db.scalars(
            select(Client)
            .join(UserClient, UserClient.client_id == Client.id)
            .where(UserClient.user_id == user.id, Client.is_active == True)
            .order_by(Client.code)
        ).all()
    )


@router.post("/query", response_model=AnalysisResponse)
def ask(data: AskRequest, user: CurrentUser, db: Session = Depends(get_db)):
    return AnalysisService.ask(data, user.id, db)


@router.post("/query/global", response_model=AnalysisResponse)
def ask_global(
    data: AskGlobalRequest, user: CurrentUser, db: Session = Depends(get_db)
):
    """Database-independent query - searches across all databases user has access to."""
    return AnalysisService.ask_global(data, user.id, db)


@router.post("/rows")
def rows(data: RowsRequest, user: CurrentUser, db: Session = Depends(get_db)):
    return AnalysisService.get_rows(data, user.id, db)


@router.post("/export")
def export(data: TokenRequest, user: CurrentUser, db: Session = Depends(get_db)):
    csv_stream = AnalysisService.export_rows(data, user.id, db)

    return StreamingResponse(
        csv_stream,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="result.csv"'},
    )


@router.post("/catalog/global/build")
def build_global_catalog(admin: AdminUser, db: Session = Depends(get_db)):
    """Build global schema catalog across all databases (admin only)."""
    count = AnalysisService.build_global_catalog()
    return {"indexed_tables": count, "status": "success"}


@router.post(
    "/saved", response_model=SavedResponse, status_code=status.HTTP_201_CREATED
)
def save(data: SaveRequest, user: CurrentUser, db: Session = Depends(get_db)):
    return AnalysisService.save_analysis(data, user.id, db)


@router.get("/saved", response_model=list[SavedResponse])
def list_saved(user: CurrentUser, db: Session = Depends(get_db)):
    return AnalysisService.list_saved(user.id, db)


@router.post("/saved/{saved_id}/run", response_model=AnalysisResponse)
def run_saved(saved_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    return AnalysisService.run_saved(saved_id, user.id, db)


@router.delete(
    "/saved/{saved_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_saved(saved_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    AnalysisService.delete_saved(saved_id, user.id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/history", response_model=list[HistoryResponse])
def history(
    user: CurrentUser, db: Session = Depends(get_db), client_id: UUID | None = None
):
    return AnalysisService.list_history(user.id, db, client_id)


@router.post("/history/{query_id}/run", response_model=AnalysisResponse)
def run_history(query_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    return AnalysisService.run_history(query_id, user.id, db)


@router.delete("/history/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_history(query_id: UUID, user: CurrentUser, db: Session = Depends(get_db)):
    AnalysisService.delete_history(query_id, user.id, db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
