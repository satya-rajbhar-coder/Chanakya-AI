from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from api.dependencies import AdminUser
from database.session import get_db
from modules.admin.schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AssignmentsUpdate,
    AvailableDatabase,
    DocumentAssignments,
)
from modules.admin.services import (
    assign_document,
    assign_user,
    create_user,
    delete_user,
    deactivate_user,
    get_available_databases,
    list_users,
    update_user,
)
from modules.documents.schemas import DocumentResponse

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/databases", response_model=list[AvailableDatabase])
def available_databases(admin: AdminUser, db: Session = Depends(get_db)):
    """Get all available databases from the analysis DB URL template with assignment status."""
    return get_available_databases(db)


@router.get("/users", response_model=list[AccountResponse])
def users(admin: AdminUser, db: Session = Depends(get_db)):
    return list_users(db)


@router.post("/users", response_model=AccountResponse, status_code=201)
def create_user_endpoint(
    data: AccountCreate, admin: AdminUser, db: Session = Depends(get_db)
):
    return create_user(db, data.model_dump())


@router.patch("/users/{user_id}", response_model=AccountResponse)
def update_user_endpoint(
    user_id: UUID, data: AccountUpdate, admin: AdminUser, db: Session = Depends(get_db)
):
    return update_user(db, user_id, data.model_dump(exclude_unset=True), admin.id)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_endpoint(
    user_id: UUID,
    admin: AdminUser,
    confirm: bool = Query(default=False, description="Confirm deletion"),
    db: Session = Depends(get_db),
):
    delete_user(db, user_id, admin.id, confirm=confirm)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/users/{user_id}/deactivate", response_model=AccountResponse)
def deactivate_user_endpoint(
    user_id: UUID, admin: AdminUser, db: Session = Depends(get_db)
):
    return deactivate_user(db, user_id, admin.id)


@router.put("/users/{user_id}/assignments", response_model=AccountResponse)
def assign_user_endpoint(
    user_id: UUID,
    data: AssignmentsUpdate,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    return assign_user(db, user_id, data.database_name)


@router.put("/documents/{document_id}/assignments", response_model=DocumentResponse)
def assign_document_endpoint(
    document_id: UUID,
    data: DocumentAssignments,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    document = assign_document(db, document_id, data.user_ids)
    return DocumentResponse.model_validate(document)
