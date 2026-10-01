import logging
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from core.config import settings
from modules.users.models import User
from rag.loader import SUPPORTED_EXTENSIONS, EmptyDocumentError, UnsupportedFileError
from rag.service import delete_document_chunks, ingest_document
from .models import Document
from .repository import DocumentRepository

logger = logging.getLogger(__name__)


class DocumentService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = DocumentRepository(db)

    async def upload(self, user: User, file: UploadFile) -> Document:
        filename = Path(file.filename or "").name
        extension = Path(filename).suffix.lower()

        if not filename or extension not in SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=f"Unsupported file type. Allowed: {allowed}",
            )

        max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        data = await file.read(max_bytes + 1)

        if not data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The uploaded file is empty",
            )
        if len(data) > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File is larger than {settings.MAX_UPLOAD_MB} MB",
            )

        document = Document(
            user_id=user.id,
            filename=filename[:255],
            content_type=(file.content_type or "application/octet-stream")[:100],
            size_bytes=len(data),
        )
        self.repo.add(document)
        self.db.flush()

        try:
            document.chunk_count = await run_in_threadpool(
                ingest_document,
                user_id=user.id,
                document_id=document.id,
                filename=document.filename,
                data=data,
            )
        except (UnsupportedFileError, EmptyDocumentError) as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            )
        except Exception:
            self.db.rollback()
            logger.exception("Indexing failed for %s", filename)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Could not index the document. Check the vector database connection and embedding model settings.",
            )

        try:
            self.db.commit()
            self.db.refresh(document)
        except Exception:
            self.db.rollback()
            await run_in_threadpool(delete_document_chunks, document.id)
            raise

        return document

    def get_documents(self, user: User) -> list[Document]:
        return self.repo.get_all(user.id)

    async def delete_document(self, user: User, document_id: UUID) -> None:
        document = self.repo.get_by_id(user.id, document_id)
        if document is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document does not exist"
            )
        try:
            await run_in_threadpool(delete_document_chunks, document.id)
            self.repo.delete(document)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
