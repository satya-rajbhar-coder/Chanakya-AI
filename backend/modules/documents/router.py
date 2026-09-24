from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from sqlalchemy.orm import Session

from api.dependencies import CurrentUser
from database.session import get_db
from .schemas import DocumentResponse
from .services import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


# Plain `def` on purpose: loading + embedding is blocking work, so FastAPI
# runs these handlers in its thread pool instead of blocking the event loop.
@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_document(
    current_user: CurrentUser,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = DocumentService(db).upload(current_user, file)
    return DocumentResponse.model_validate(document)


@router.get("", response_model=list[DocumentResponse])
def get_documents(current_user: CurrentUser, db: Session = Depends(get_db)) -> list[DocumentResponse]:
    documents = DocumentService(db).get_documents(current_user)
    return [DocumentResponse.model_validate(d) for d in documents]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: UUID, current_user: CurrentUser, db: Session = Depends(get_db)) -> None:
    DocumentService(db).delete_document(current_user, document_id)
