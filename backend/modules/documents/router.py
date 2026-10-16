import json
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from api.dependencies import AdminUser, CurrentUser
from database.session import get_db

from .schemas import DocumentResponse
from .services import DocumentService

router = APIRouter(prefix="/documents", tags=["Documents"])


def _parse_user_ids(raw: str | None) -> list[UUID]:
    if not raw:
        return []
    try:
        values = json.loads(raw)
        return [UUID(str(value)) for value in values]
    except (ValueError, TypeError, json.JSONDecodeError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_ids must be a JSON array of UUIDs")


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    current_user: AdminUser,
    file: UploadFile = File(...),
    user_ids: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> DocumentResponse:
    document = await DocumentService(db).upload(
        current_user, file, _parse_user_ids(user_ids)
    )
    return DocumentResponse.model_validate(document)


@router.get("", response_model=list[DocumentResponse])
def get_documents(
    current_user: CurrentUser, db: Session = Depends(get_db)
) -> list[DocumentResponse]:
    documents = DocumentService(db).get_documents(current_user)
    return [DocumentResponse.model_validate(d) for d in documents]


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID, current_user: AdminUser, db: Session = Depends(get_db)
) -> None:
    await DocumentService(db).delete_document(current_user, document_id)
