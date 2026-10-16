from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClientCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    database_name: str = Field(min_length=1, max_length=100)
    client_identifier: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ClientResponse(ClientCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    client_ids: list[UUID] = Field(default_factory=list)


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None


class AssignmentsUpdate(BaseModel):
    client_ids: list[UUID]


class AccountResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    is_active: bool
    client_ids: list[UUID]


class DocumentAssignments(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list)