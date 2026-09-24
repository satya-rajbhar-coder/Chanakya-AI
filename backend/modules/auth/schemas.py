from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, model_validator


Name = Annotated[str, StringConstraints(
    strip_whitespace=True, min_length=1, max_length=100)]


class RegisterRequest(BaseModel):
    name: Name
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    confirm_password: str = Field(min_length=8, max_length=128)

    @model_validator(mode="after")
    def passwords_match(self):
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class AuthMessage(BaseModel):
    message: str
