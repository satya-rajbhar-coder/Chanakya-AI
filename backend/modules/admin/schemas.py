from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ClientCreate(BaseModel):
    code: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    client_identifier: str = Field(min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    database_name: str = Field(min_length=1, max_length=100)


class ClientResponse(ClientCreate):
    id: UUID
    is_active: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ClientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=500)
    is_active: bool | None = None
    database_name: str | None = Field(default=None, min_length=1, max_length=100)


class AvailableDatabase(BaseModel):
    name: str
    is_assigned: bool
    assigned_client_id: UUID | None = None
    assigned_client_name: str | None = None


# Political role hierarchy (lowest to highest authority)
ROLE_HIERARCHY: dict[str, int] = {
    "karyakarta": 1,
    "corporator": 2,
    "aamdar": 3,
    "khasdar": 4,
    "user": 5,
    "admin": 6,
}

VALID_HIERARCHY_ROLES = frozenset(ROLE_HIERARCHY)


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="user", min_length=1, max_length=20)
    party_name: str | None = Field(default=None, max_length=100)
    ward_no: int | None = Field(default=None)
    assembly_no: str | None = Field(default=None, max_length=50)
    parliamentary_constituency: str | None = Field(default=None, max_length=100)
    client_ids: list[UUID] = Field(default_factory=list)
    database_name: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_role_and_scope(self):
        if self.role not in VALID_HIERARCHY_ROLES:
            raise ValueError(
                f"Invalid role '{self.role}'. Must be one of: {', '.join(sorted(VALID_HIERARCHY_ROLES))}"
            )
        level = ROLE_HIERARCHY[self.role]
        if level <= ROLE_HIERARCHY["corporator"]:
            if not self.ward_no:
                raise ValueError(f"ward_no is required for {self.role} role")
        elif level <= ROLE_HIERARCHY["aamdar"]:
            if not self.assembly_no:
                raise ValueError(f"assembly_no is required for {self.role} role")
        elif level <= ROLE_HIERARCHY["khasdar"]:
            if not self.parliamentary_constituency:
                raise ValueError(
                    f"parliamentary_constituency is required for {self.role} role"
                )
        return self


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None
    role: str | None = Field(default=None, min_length=1, max_length=20)
    party_name: str | None = Field(default=None, max_length=100)
    ward_no: int | None = Field(default=None)
    assembly_no: str | None = Field(default=None, max_length=50)
    parliamentary_constituency: str | None = Field(default=None, max_length=100)


class AssignmentsUpdate(BaseModel):
    client_ids: list[UUID]


class AccountResponse(BaseModel):
    id: UUID
    name: str
    email: str
    role: str
    hierarchy_level: int | None = None
    is_active: bool
    party_name: str | None = None
    ward_no: int | None = None
    assembly_no: str | None = None
    parliamentary_constituency: str | None = None
    client_ids: list[UUID]


class DocumentAssignments(BaseModel):
    user_ids: list[UUID] = Field(default_factory=list)
