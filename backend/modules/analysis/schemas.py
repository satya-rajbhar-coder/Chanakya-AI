from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

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


class ResultPage(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    page: int
    page_size: int
    has_more: bool
    total_time_ms: float | None = None


class TokenRequest(BaseModel):
    token: str


class AnalysisResponse(BaseModel):
    title: str
    database: str
    tables: list[str]
    sql: str
    analysis_query_id: UUID | None = None
    token: str
    result: ResultPage


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


class UserHistoryResponse(BaseModel):
    """History response for regular users (politicians) - excludes SQL."""
    id: UUID
    question: str
    title: str | None
    database: str
    client_id: UUID | None
    row_count: int | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)