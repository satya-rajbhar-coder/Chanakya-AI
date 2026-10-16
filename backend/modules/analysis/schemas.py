from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from core.config import settings

Question = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class ClientResponse(BaseModel):
    id: UUID
    code: str
    name: str
    client_identifier: str
    database_name: str
    description: str | None
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class AskRequest(BaseModel):
    question: Question
    client_id: UUID | None = None
    client_ids: list[UUID] | None = None  # For multi-client queries
    previous_sql: str | None = Field(default=None, max_length=8000)
    join_key: str | None = None  # Column to join results on across clients
    join_type: str = Field(default="outer", pattern="^(inner|left|right|outer)$")


class AskGlobalRequest(BaseModel):
    """Database-independent query - searches across all accessible databases."""
    question: Question
    table_type_filter: str | None = None  # Filter by table type (e.g., 'contact_sync')
    client_ids: list[UUID] | None = None  # Optional filter by specific clients
    join_key: str | None = None  # Column to join results on across clients
    join_type: str = Field(default="outer", pattern="^(inner|left|right|outer)$")


class RowsRequest(BaseModel):
    token: str
    page: int = Field(default=0, ge=0)
    page_size: int = Field(default=settings.ANALYSIS_PAGE_SIZE, ge=1)


class TokenRequest(BaseModel):
    token: str


class SaveRequest(BaseModel):
    token: str
    question: Question
    title: str = Field(min_length=1, max_length=200)


class ResultPage(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    page: int
    page_size: int
    has_more: bool
    total_time_ms: float | None = None


class MultiClientResult(BaseModel):
    """Result from querying multiple clients"""
    clients: dict[str, ResultPage]  # client_identifier -> ResultPage
    merged_result: ResultPage | None = None
    join_key: str | None = None
    join_type: str = "outer"


class AnalysisResponse(BaseModel):
    title: str
    database: str
    tables: list[str]
    sql: str
    token: str
    result: ResultPage
    # Multi-client fields
    multi_result: MultiClientResult | None = None


class SavedResponse(BaseModel):
    id: UUID
    title: str
    question: str
    database: str
    sql: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HistoryResponse(BaseModel):
    id: UUID
    question: str
    title: str | None
    database: str
    sql: str
    client_id: UUID | None
    row_count: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)