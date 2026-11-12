from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

Question = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]


class ChartAxis(BaseModel):
    field: str
    label: str | None = None


class ChartConfig(BaseModel):
    type: Literal["bar", "line", "pie", "table", "none"] = "bar"
    x_axis: ChartAxis | None = None
    y_axis: ChartAxis | None = None
    label_field: str | None = None
    value_field: str | None = None
    limit: int | None = None


class DatabaseResult(BaseModel):
    title: str | None = None
    database: str | None = None
    tables: list[str] = []
    sql: str | None = None
    analysis_query_id: UUID | None = None
    token: str
    columns: list[str] = []
    rows: list[list[Any]] = []
    row_count: int | None = None
    total_time_ms: float | None = None
    page: int = 0
    page_size: int = 0
    has_more: bool = False


class DocumentSource(BaseModel):
    filename: str
    page: int | None = None
    score: float | None = None


class DocumentResult(BaseModel):
    answer: str | None = None
    sources: list[DocumentSource] = []


class IntelligenceRequest(BaseModel):
    question: Question
    client_id: UUID | None = None
    conversation_id: UUID | None = None


class IntelligenceResponse(BaseModel):
    intent: Literal["database", "document", "hybrid", "general"]
    answer: str
    database: DatabaseResult | None = None
    document: DocumentResult | None = None
    chart: ChartConfig | None = None
    sources: list[DocumentSource] = []
    conversation_id: UUID | None = None
    user_message_id: UUID | None = None
    assistant_message_id: UUID | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
