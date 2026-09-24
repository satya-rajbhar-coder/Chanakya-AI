from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=1, max_length=100)]


class UserUpdate(BaseModel):
    name: Name | None = None
    password: str | None = Field(default=None, min_length=8, max_length=128)
    current_password: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def require_current_password(self):
        if self.password is not None and not self.current_password:
            raise ValueError(
                "current_password is required to change the password"
            )
        return self


class UserResponse(BaseModel):
    id: UUID
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)
