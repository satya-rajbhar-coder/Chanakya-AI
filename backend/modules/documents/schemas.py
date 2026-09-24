from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: UUID
    user_id: UUID
    filename: str
    content_type: str
    size_bytes: int
    chunk_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
