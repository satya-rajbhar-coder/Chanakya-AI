from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.dependencies import AdminUser
from database.session import get_db
from modules.admin.schemas import (
    AccountCreate,
    AccountResponse,
    AccountUpdate,
    AssignmentsUpdate,
    ClientCreate,
    ClientResponse,
    ClientUpdate,
    DocumentAssignments,
)
from modules.admin.services import (
    assign_document,
    assign_user,
    create_client,
    create_user,
    list_clients,
    list_users,
    update_client,
    update_user,
)
from modules.documents.schemas import DocumentResponse

router = APIRouter(prefix="/admin", tags=["Administration"])


@router.get("/clients", response_model=list[ClientResponse])
def clients(admin: AdminUser, db: Session = Depends(get_db)):
    return list_clients(db)


@router.post("/clients", response_model=ClientResponse, status_code=201)
def create_client_endpoint(
    data: ClientCreate, admin: AdminUser, db: Session = Depends(get_db)
):
    return create_client(db, data.model_dump())


@router.patch("/clients/{client_id}", response_model=ClientResponse)
def update_client_endpoint(
    client_id: UUID, data: ClientUpdate, admin: AdminUser, db: Session = Depends(get_db)
):
    return update_client(db, client_id, data.model_dump(exclude_unset=True))


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


@router.put("/users/{user_id}/assignments", response_model=AccountResponse)
def assign_user_endpoint(
    user_id: UUID,
    data: AssignmentsUpdate,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    return assign_user(db, user_id, data.client_ids)


@router.put("/documents/{document_id}/assignments", response_model=DocumentResponse)
def assign_document_endpoint(
    document_id: UUID,
    data: DocumentAssignments,
    admin: AdminUser,
    db: Session = Depends(get_db),
):
    document = assign_document(db, document_id, data.user_ids)
    return DocumentResponse.model_validate(document)
