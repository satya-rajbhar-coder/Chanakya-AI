from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from database.session import get_db

from .schemas import AuthMessage, LoginRequest, RegisterRequest
from .services import AuthService

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _unauthorized(detail: str) -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": detail}
    )
    clear_auth_cookies(response)
    return response


@router.post(
    "/register", response_model=AuthMessage, status_code=status.HTTP_201_CREATED
)
def register(data: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    access, refresh_token = AuthService(db).register(
        str(data.email), data.name, data.password
    )
    set_auth_cookies(response, access, refresh_token)
    return {"message": "Registration successful"}


@router.post("/login", response_model=AuthMessage)
def login(data: LoginRequest, response: Response, db: Session = Depends(get_db)):
    access, refresh_token = AuthService(db).login(str(data.email), data.password)
    set_auth_cookies(response, access, refresh_token)
    return {"message": "Login successful"}


@router.post("/refresh", response_model=AuthMessage)
def refresh(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
    db: Session = Depends(get_db),
):
    if not refresh_token:
        return _unauthorized("Refresh token missing")
    try:
        new_access, new_refresh = AuthService(db).refresh_token(refresh_token)
    except HTTPException as exc:
        return _unauthorized(str(exc.detail))

    set_auth_cookies(response, new_access, new_refresh)
    return {"message": "Token refreshed"}


# The cookie now has a default: previously a missing cookie produced a 422
# instead of a clean logout.
@router.post("/logout", response_model=AuthMessage)
def logout(
    response: Response,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
    db: Session = Depends(get_db),
):
    AuthService(db).logout(refresh_token)
    clear_auth_cookies(response)
    return {"message": "Logged out successfully"}
